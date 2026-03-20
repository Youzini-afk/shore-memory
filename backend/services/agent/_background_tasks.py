"""
AgentBackgroundTasks
====================
Agent 服务的后台异步任务集合。
将所有不阻塞主流程的副作用操作集中在此模块。

包含：
- run_scorer_background  : 单次对话触发 Scorer 分析
- schedule_scorer_batch  : 批量 Scorer 调度
- trigger_dream          : 后台梦境（记忆整理）机制
- generate_and_stream_tts: TTS 合成并通过 Gateway 推送
"""

import random
import re
import time
import uuid
from datetime import datetime


class AgentBackgroundTasks:
    """Agent 后台任务静态工具类，所有方法均为独立异步任务，使用独立 DB Session。"""

    @staticmethod
    async def run_scorer_background(
        user_msg: str,
        assistant_msg: str,
        source: str,
        pair_id: str = None,
        agent_id: str = "pero",
    ):
        """后台运行 Scorer 服务，使用独立 Session 避免阻塞主请求。"""
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        from database import engine
        from services.memory.scorer_service import ScorerService

        try:
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                scorer = ScorerService(session)
                await scorer.process_interaction(
                    user_msg, assistant_msg, source, pair_id=pair_id, agent_id=agent_id
                )
        except Exception as e:
            print(f"[Agent] 后台秘书服务失败: {e}")

    @staticmethod
    async def schedule_scorer_batch(agent_id: str = "pero"):
        """后台调度 Scorer 批量处理，当待处理日志达到阈值时触发。"""
        from sqlalchemy.orm import sessionmaker
        from sqlmodel import func, select
        from sqlmodel.ext.asyncio.session import AsyncSession

        from core.config_manager import get_config_manager
        from database import engine
        from models import ConversationLog
        from services.memory.scorer_service import ScorerService

        try:
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                # 1. 获取批量大小配置
                config_manager = get_config_manager()
                memory_config = config_manager.get_json("memory_config")
                batch_size = memory_config.get("summary_batch_size", 10)

                # 2. 查询待处理日志数量
                stmt = (
                    select(func.count(ConversationLog.id))
                    .where(ConversationLog.analysis_status == "pending")
                    .where(ConversationLog.agent_id == agent_id)
                )
                count = (await session.exec(stmt)).one()

                print(
                    f"[Agent] 当前待处理日志数: {count} / {batch_size} (Agent: {agent_id})"
                )

                if count >= batch_size:
                    # 3. 触发批量处理：获取最早的 N 条
                    logs_stmt = (
                        select(ConversationLog)
                        .where(ConversationLog.analysis_status == "pending")
                        .where(ConversationLog.agent_id == agent_id)
                        .order_by(ConversationLog.created_at)
                        .limit(batch_size)
                    )
                    logs = (await session.exec(logs_stmt)).all()

                    if logs:
                        scorer = ScorerService(session)
                        await scorer.process_batch(logs, agent_id=agent_id)
        except Exception as e:
            print(f"[Agent] 后台批量调度失败: {e}")

    @staticmethod
    async def trigger_dream(agent_id: str = "pero"):
        """后台触发梦境机制：记忆整理、孤独记忆扫描、关联挖掘、记忆压缩。"""
        try:
            from sqlalchemy.orm import sessionmaker
            from sqlmodel.ext.asyncio.session import AsyncSession

            from database import engine
            from models import Config
            from services.memory.reflection_service import ReflectionService

            print(f"[Agent] 启动后台梦境任务 (agent_id={agent_id})...", flush=True)
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                # 更新上次触发时间（按 agent_id 区分键）
                config_key = f"last_dream_trigger_time_{agent_id}"
                now_str = datetime.now().isoformat()
                config_last_dream = await session.get(Config, config_key)

                # 回退至全局键（兼容性或首次运行）
                if not config_last_dream and agent_id == "pero":
                    config_last_dream = await session.get(
                        Config, "last_dream_trigger_time"
                    )

                if not config_last_dream:
                    config_last_dream = Config(key=config_key, value=now_str)
                    session.add(config_last_dream)
                else:
                    config_last_dream.value = now_str
                    config_last_dream.updated_at = datetime.now()
                await session.commit()

                service = ReflectionService(session)

                # 1. 补录记忆（优先修复失败）
                await service.backfill_failed_scorer_tasks(agent_id=agent_id)

                # 2. 孤独记忆扫描（每次梦境周期扫描 3 个孤独记忆）
                await service.scan_lonely_memories(limit=3, agent_id=agent_id)

                # 3. 关联挖掘（高优先级）
                await service.dream_and_associate(limit=10, agent_id=agent_id)

                # 4. 记忆压缩（低优先级，10% 概率）
                if random.random() < 0.1:
                    await service.consolidate_memories(
                        lookback_days=3, importance_threshold=4, agent_id=agent_id
                    )

        except Exception as e:
            print(f"[Agent] 后台梦境失败: {e}")

    @staticmethod
    async def generate_and_stream_tts(text: str):
        """生成 TTS 音频并通过 Gateway 流式推送到前端（文本模式专用）。"""
        try:
            # 清理文本（移除表情符号、思考标签等）
            cleaned_text = re.sub(r"[\U00010000-\U0010ffff]", "", text)  # 移除表情符号
            cleaned_text = re.sub(r"【.*?】", "", cleaned_text)  # 移除思考标签
            cleaned_text = re.sub(r"<.*?>", "", cleaned_text)  # 移除 HTML 标签
            cleaned_text = re.sub(r"\*.*?\*", "", cleaned_text)  # 移除动作描述
            cleaned_text = cleaned_text.strip()

            if not cleaned_text:
                return

            from core.config_manager import get_config_manager
            from peroproto import perolink_pb2
            from services.core.gateway_client import gateway_client
            from services.interaction.tts_service import get_tts_service

            # 检查 TTS 是否启用
            if not get_config_manager().get("tts_enabled", True):
                return

            tts_service = get_tts_service()
            audio_path = await tts_service.synthesize(cleaned_text)

            if audio_path:
                # 通过 Gateway 流式传输音频
                with open(audio_path, "rb") as f:
                    audio_data = f.read()

                envelope = perolink_pb2.Envelope()
                envelope.id = str(uuid.uuid4())
                envelope.source_id = gateway_client.device_id
                envelope.target_id = "broadcast"
                envelope.timestamp = int(time.time() * 1000)

                envelope.stream.stream_id = str(uuid.uuid4())
                envelope.stream.data = audio_data
                envelope.stream.is_end = True
                envelope.stream.content_type = "audio/mp3"

                await gateway_client.send(envelope)

                # 清理临时音频文件
                try:
                    import os

                    os.remove(audio_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"[Agent] TTS 生成失败: {e}")
