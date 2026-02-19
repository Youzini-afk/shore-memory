import json
import logging
from typing import Any, Dict

from sqlmodel.ext.asyncio.session import AsyncSession

from services.agent.agent_service import AgentService
from services.core.llm_service import LLMService
from services.mdp.manager import mdp
from services.memory.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MemoryImporter:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_story(
        self, story_text: str, agent_id: str = "pero"
    ) -> Dict[str, Any]:
        """
        导入长故事，使用 LLM 将其拆分为事件，并保存到记忆中。
        """
        if not story_text or len(story_text.strip()) == 0:
            return {"success": False, "message": "Story text is empty."}

        # 1. 准备提示词
        print(f"[MemoryImporter] 正在处理故事导入 (Agent: {agent_id})...")
        prompt = mdp.render("tasks/memory/story_extract", {"story": story_text})

        # 2. 调用 LLM
        agent_service = AgentService(self.session)
        try:
            llm_config = await agent_service._get_llm_config()
        except Exception as e:
            return {"success": False, "message": f"Failed to get LLM config: {e}"}

        llm = LLMService(
            api_key=llm_config.get("api_key"),
            api_base=llm_config.get("api_base"),
            model=llm_config.get("model"),
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            print("[MemoryImporter] 调用 LLM 进行事件拆解...")
            response = await llm.chat(messages, temperature=0.3)  # 低温以获得结构化输出
            content = response["choices"][0]["message"]["content"]

            # 清理 JSON
            json_str = content.strip()

            # 移除 Markdown 代码块（如果存在）（更稳健）
            import re

            json_match = re.search(r"\[\s*\{.*\}\s*\]", json_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # 如果正则表达式未找到列表，回退到现有的清理逻辑
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                elif json_str.startswith("```"):
                    json_str = json_str[3:]

                if json_str.endswith("```"):
                    json_str = json_str[:-3]

            json_str = json_str.strip()

            try:
                events = json.loads(json_str)
            except json.JSONDecodeError:
                # 回退：尝试查找第一个 '[' 和最后一个 ']'
                start = json_str.find("[")
                end = json_str.rfind("]")
                if start != -1 and end != -1:
                    json_str = json_str[start : end + 1]
                    events = json.loads(json_str)
                else:
                    raise ValueError("Failed to parse JSON response from LLM") from None

            if not isinstance(events, list):
                # 尝试在特定键中查找列表
                if isinstance(events, dict):
                    for key in ["events", "items", "memories"]:
                        if key in events and isinstance(events[key], list):
                            events = events[key]
                            break
                    else:
                        raise ValueError(
                            "Output JSON is not a list and contains no list wrapper."
                        )
                else:
                    raise ValueError("Output is not a list")

            print(f"[MemoryImporter] 提取到 {len(events)} 个事件。开始入库...")

            # 3. 保存到记忆
            saved_count = 0
            for event in events:
                # 提取字段并使用安全默认值
                content = event.get("content")
                if not content:
                    continue

                tags = event.get("tags", "")
                if isinstance(tags, list):
                    tags = ",".join(tags)

                # 安全地将重要性转换为整数
                try:
                    importance = int(event.get("importance", 1))
                except Exception:
                    importance = 1

                memory_type = event.get("type", "event")

                # 如果我们要将其存储在元数据中或记录日志，请使用 timestamp_hint
                # 目前 MemoryService 不容易支持自定义时间戳覆盖
                # (它使用 realTime=now, timestamp=now)。
                # 但顺序保存保留了逻辑链（prev_id/next_id）。
                # 如果需要，我们可以将提示附加到标签或内容中。
                timestamp_hint = event.get("timestamp_hint")
                if timestamp_hint:
                    # 附加到标签以提高可搜索性
                    tags = (
                        f"{tags},Time:{timestamp_hint}"
                        if tags
                        else f"Time:{timestamp_hint}"
                    )

                await MemoryService.save_memory(
                    session=self.session,
                    content=content,
                    tags=tags,
                    importance=importance,
                    memory_type=memory_type,
                    agent_id=agent_id,
                )
                saved_count += 1

            print(f"[MemoryImporter] 导入完成。共保存 {saved_count} 条记忆。")
            return {
                "success": True,
                "message": f"Successfully imported {saved_count} events.",
                "count": saved_count,
            }

        except Exception as e:
            logger.error(f"Story import failed: {e}")
            return {"success": False, "message": str(e)}
