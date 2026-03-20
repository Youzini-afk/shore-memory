"""
AgentPostHandler
================
Agent 对话后处理层。

在 ReAct 循环结束后，负责：
1. 运行后处理器管道（清理 NIT 标签等）
2. 通过 Gateway 广播 LLM 响应并触发 TTS（文本模式）
3. 提取并持久化用户上传的图片
4. 保存对话日志对（user + assistant）
5. 调度 Scorer 批量分析任务
6. 按概率触发后台梦境任务
"""

import asyncio
import base64
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession


class AgentPostHandler:
    """对话后处理器：负责日志持久化、评分调度、梦境触发等副作用。"""

    def __init__(self, session: AsyncSession, memory_service, postprocessor_manager):
        self.session = session
        self.memory_service = memory_service
        self.postprocessor_manager = postprocessor_manager

    async def handle(
        self,
        full_response_text: str,
        raw_full_text: str,
        user_message: str,
        user_text_override: Optional[str],
        source: str,
        session_id: str,
        pair_id: str,
        current_agent_id: str,
        messages: List[Dict],
        skip_save: bool,
        is_voice_mode: bool,
        mcp_clients: List,
    ) -> str:
        """
        执行所有后处理步骤，返回经后处理器清理后的最终文本。

        Returns:
            post-processed full_response_text（供调用方决定是否再次使用）
        """
        # 1. 后处理器管道（清理协议标记，获得干净文本）
        if full_response_text:
            try:
                full_response_text = await self.postprocessor_manager.process(
                    full_response_text,
                    context={"source": source, "session_id": session_id},
                )
            except Exception as pp_e:
                print(f"[PostHandler] 后处理器失败: {pp_e}。使用原始文本。")

        # 2. 通过 Gateway 广播 + 触发 TTS（仅文本桌面模式）
        if not is_voice_mode and source in ["desktop", "ide"]:
            from services.agent._background_tasks import AgentBackgroundTasks
            from services.core.gateway_client import gateway_client

            await gateway_client.broadcast_text_response(full_response_text)
            asyncio.create_task(
                AgentBackgroundTasks.generate_and_stream_tts(full_response_text)
            )

        # 3. 回退提取 user_message（健壮性）
        if not user_message:
            user_message = self._extract_user_message(messages, user_text_override)

        # 4. 持久化用户图片
        user_metadata = self._extract_and_save_user_images(messages)

        # 5. 保存对话日志对
        should_save = not skip_save and user_message and full_response_text
        print(
            f"[PostHandler] 日志保存检查: 是否保存={should_save} "
            f"(跳过保存={skip_save}, 有用户消息={bool(user_message)}, "
            f"响应长度={len(full_response_text) if full_response_text else 0})"
        )

        if should_save:
            final_user_msg = user_text_override if user_text_override else user_message
            try:
                await self.memory_service.save_log_pair(
                    self.session,
                    source,
                    session_id,
                    final_user_msg,
                    full_response_text,
                    pair_id,
                    assistant_raw_content=raw_full_text,
                    user_metadata=user_metadata,
                    agent_id=current_agent_id,
                )
                print(f"[PostHandler] 对话日志对已保存 (pair_id: {pair_id})")
            except Exception as e:
                print(f"[PostHandler] 保存日志对失败: {e}")
        else:
            if not skip_save:
                print(
                    f"[PostHandler] 跳过保存。原因: "
                    f"有用户消息={bool(user_message)}, "
                    f"响应有效={bool(full_response_text and not full_response_text.startswith('Error:'))}"
                )

        # 6. 调度 Scorer 批量分析（非社交/移动模式）
        is_error_response = (
            full_response_text.startswith("Error:")
            or full_response_text.startswith("Network Error")
            or full_response_text.startswith("⚠️")
        )

        if (
            not skip_save
            and user_message
            and full_response_text
            and not is_error_response
        ):
            if source in ["social", "mobile"]:
                print(f"[PostHandler] 跳过 {source} 模式的后台分析。")
            else:
                if len(full_response_text) > 5:
                    from services.agent._background_tasks import AgentBackgroundTasks

                    asyncio.create_task(
                        AgentBackgroundTasks.schedule_scorer_batch(
                            agent_id=current_agent_id
                        )
                    )

        # 8. 显式提交
        await self.session.commit()

        # 9. 按概率触发梦境（3%，非社交/移动模式）
        import random

        if source not in ["social", "mobile"] and random.random() < 0.03:
            from services.agent._background_tasks import AgentBackgroundTasks

            asyncio.create_task(
                AgentBackgroundTasks.trigger_dream(agent_id=current_agent_id)
            )

        return full_response_text

    async def handle_error(
        self,
        full_response_text: str,
        error_msg: str,
        user_message: str,
        user_text_override: Optional[str],
        source: str,
        session_id: str,
        pair_id: str,
        current_agent_id: str,
    ):
        """处理 chat() 异常路径的日志保存。"""
        try:
            final_u_msg = user_message or user_text_override
            final_response = full_response_text + f"\n\n[System Error]: {error_msg}"

            if final_u_msg:
                await self.memory_service.save_log_pair(
                    self.session,
                    source,
                    session_id,
                    final_u_msg,
                    final_response,
                    pair_id,
                    agent_id=current_agent_id,
                )
                print(f"[PostHandler] 错误日志已保存 (pair_id: {pair_id})")
        except Exception as save_err:
            print(f"[PostHandler] 保存错误日志失败: {save_err}")

    # ─────────────────────────────────────────────
    # 私有辅助方法
    # ─────────────────────────────────────────────

    def _extract_user_message(
        self, messages: List[Dict], user_text_override: Optional[str]
    ) -> str:
        """从消息列表中回退提取用户消息。"""
        if user_text_override:
            print(
                f"[PostHandler] 用户消息已从覆盖中恢复: '{user_text_override[:20]}...'"
            )
            return user_text_override

        print(f"[PostHandler] 用户消息缺失。正在 {len(messages)} 条输入消息中搜索...")
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    texts = [
                        item["text"] for item in content if item.get("type") == "text"
                    ]
                    return " ".join(texts)

        print("[PostHandler] 严重: 无法从输入中提取用户消息。日志将不会被保存。")
        return ""

    def _extract_and_save_user_images(self, messages: List[Dict]) -> Dict:
        """持久化用户上传的 base64 图片，返回 user_metadata 字典。"""
        user_metadata = {}
        try:
            target_msg = None
            for m in reversed(messages):
                if m.get("role") == "user":
                    target_msg = m
                    break

            if target_msg and isinstance(target_msg.get("content"), list):
                images = []
                for item in target_msg["content"]:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        if url.startswith("data:image"):
                            try:
                                header, encoded = url.split(",", 1)
                                ext = "png"
                                if "jpeg" in header:
                                    ext = "jpg"
                                elif "gif" in header:
                                    ext = "gif"
                                elif "webp" in header:
                                    ext = "webp"

                                img_data = base64.b64decode(encoded)

                                # _post_handler.py 位于 services/agent/ 下，backend/ 在三级 dirname 处
                                current_dir = os.path.dirname(os.path.abspath(__file__))
                                services_dir = os.path.dirname(current_dir)
                                backend_dir = os.path.dirname(services_dir)
                                data_dir = os.environ.get(
                                    "PERO_DATA_DIR",
                                    os.path.join(backend_dir, "data"),
                                )

                                date_str = datetime.now().strftime("%Y-%m-%d")
                                upload_dir = os.path.join(data_dir, "uploads", date_str)
                                os.makedirs(upload_dir, exist_ok=True)

                                filename = f"{uuid.uuid4()}.{ext}"
                                file_path = os.path.join(upload_dir, filename)

                                with open(file_path, "wb") as f:
                                    f.write(img_data)

                                rel_path = f"uploads/{date_str}/{filename}"
                                images.append(rel_path)
                            except Exception as img_e:
                                print(f"[PostHandler] 保存图片失败: {img_e}")

                if images:
                    user_metadata["images"] = images
                    print(f"[PostHandler] 已持久化 {len(images)} 张图片用于显示。")
        except Exception as e:
            print(f"[PostHandler] 图片处理错误: {e}")

        return user_metadata
