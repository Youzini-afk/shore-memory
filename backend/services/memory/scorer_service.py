import json
import re
from typing import Any, Dict

from sqlalchemy import update
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config_manager import get_config_manager
from models import AIModelConfig, Config, ConversationLog, Memory
from services.core.llm_service import LLMService
from services.mdp.manager import mdp
from services.memory.memory_service import MemoryService


class ScorerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.memory_service = MemoryService()

        # 初始化 MDPManager
        self.mdp = mdp

    def _smart_clean_text(self, text: str) -> str:
        """
        智能清洗文本：
        - 移除大数据量的系统注入标签 (如 FILE_RESULTS)
        - 移除 Thinking 和 Monologue 块，只保留最有价值的回复用于总结
        - 保留有助于判断语气的 NIT 协议块和关键性格标签
        """
        if not text:
            return ""

        # 1. 移除大数据量的系统注入标签 (数据垃圾/系统噪音)
        remove_tags = [
            "FILE_RESULTS",
            "SEARCH_RESULTS",
            "RETRIEVED_CONTEXT",
            "SYSTEM_INJECTION",
        ]

        cleaned = text
        for tag in remove_tags:
            pattern = f"<{tag}>[\\s\\S]*?</{tag}>"
            cleaned = re.sub(pattern, f"[{tag} Data Omitted]", cleaned)

        # 2. 移除 Thinking 和 Monologue 块
        # 这些内心戏对于长期记忆来说通常是噪音，Scorer 只需要关注最终的交互结果
        cleaned = re.sub(
            r"【(?:Thinking|Monologue)[:：]?\s*[\s\S]*?】",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\[(?:Thinking|Monologue)[:：]?\s*[\s\S]*?\]",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        # 3. 保留逻辑：
        # 我们默认保留所有 NIT 协议块 [[[NIT_CALL]]]...[[[NIT_END]]]
        # 以及可能残留的性格相关标签 (PEROCUE, TOPIC 等)，因为它们包含关键的语气和状态信息。

        return cleaned.strip()

    async def _get_scorer_config(self) -> Dict[str, Any]:
        """获取秘书专用模型配置，如果未配置则回退到全局配置"""
        # 1. 尝试查找名为 "秘书" 的模型配置
        statement = select(AIModelConfig).where(AIModelConfig.name == "秘书")
        result = await self.session.exec(statement)
        model_config = result.first()

        # 2. 获取全局配置作为回退
        configs = {
            c.key: c.value for c in (await self.session.exec(select(Config))).all()
        }
        global_api_key = configs.get("global_llm_api_key", "")
        global_api_base = configs.get("global_llm_api_base", "https://api.openai.com")

        if model_config:
            return {
                "api_key": (
                    model_config.api_key
                    if model_config.provider_type == "custom"
                    else global_api_key
                ),
                "api_base": (
                    model_config.api_base
                    if model_config.provider_type == "custom"
                    else global_api_base
                ),
                "model": model_config.model_id,
                "temperature": 0.3,  # Scorer 需要相对客观
            }

        # 3. 尝试使用主模型回退
        main_model_id = configs.get("current_model_id")
        if main_model_id:
            main_config = await self.session.get(AIModelConfig, int(main_model_id))
            if main_config:
                return {
                    "api_key": (
                        main_config.api_key
                        if main_config.provider_type == "custom"
                        else global_api_key
                    ),
                    "api_base": (
                        main_config.api_base
                        if main_config.provider_type == "custom"
                        else global_api_base
                    ),
                    "model": main_config.model_id,
                    "temperature": 0.3,
                }

        # 4. 如果没有特定于评分者的配置，也没有主模型，则回退到默认的低成本模型（作为最后手段）
        return {
            "api_key": global_api_key,
            "api_base": global_api_base,
            "model": "gpt-4o-mini",  # 最后的兜底
            "temperature": 0.3,
        }

    async def _update_log_status(
        self,
        pair_id: str,
        status: str,
        error: str = None,
        increment_retry: bool = False,
    ):
        """更新日志的分析状态"""
        if not pair_id:
            return

        try:
            # 构建更新语句
            # 兼容性修复：SQLModel/SQLAlchemy 更新语句在不同版本中的行为差异
            # 使用 session.execute + update() 对象是比较稳妥的方式

            stmt = update(ConversationLog).where(ConversationLog.pair_id == pair_id)

            update_values = {"analysis_status": status}  # 直接使用字符串键名

            if error:
                update_values["last_error"] = str(error)[:500]

            if increment_retry:
                # 对于自增操作，需要特殊处理，或者先读后写。
                # 简单起见，这里我们不使用原子自增，因为 retry_count 不会高并发竞争
                # 实际上 ScorerService 是单线程消费的
                pass
                # 如果确实需要自增，最好是先查出来再更新，或者使用 ConversationLog.retry_count + 1
                # 但在 values() 中使用表达式可能需要 synchronize_session=False

            stmt = stmt.values(**update_values)

            # 手动处理 retry_count 自增 (如果需要)
            if increment_retry:
                stmt = (
                    update(ConversationLog)
                    .where(ConversationLog.pair_id == pair_id)
                    .values(
                        retry_count=ConversationLog.retry_count + 1, **update_values
                    )
                )
            else:
                stmt = stmt.values(**update_values)

            await self.session.exec(stmt)
            await self.session.commit()

        except Exception as e:
            print(f"[秘书] 更新 {pair_id} 的状态失败: {e}")

    async def retry_interaction(self, log_id: int):
        """重试指定日志的分析任务"""
        # 查找日志
        log = await self.session.get(ConversationLog, log_id)
        if not log:
            print(f"[秘书] 未找到日志 {log_id}")
            return False

        if not log.pair_id:
            print(f"[秘书] 日志 {log_id} 没有 pair_id，无法重试")
            return False

        # 查找配对
        statement = select(ConversationLog).where(
            ConversationLog.pair_id == log.pair_id
        )
        results = (await self.session.exec(statement)).all()

        user_msg = next((r for r in results if r.role == "user"), None)
        assistant_msg = next((r for r in results if r.role == "assistant"), None)

        if not user_msg or not assistant_msg:
            print(f"[秘书] {log.pair_id} 的配对不完整")
            # 如果我们至少有一个，我们可能会尝试？但是 user_content 和 assistant_content 是必需的。
            # 如果只有一个存在，我们实际上无法进行“交互分析”。
            return False

        # 从日志中获取 agent_id (如果存在)
        agent_id = log.agent_id if hasattr(log, "agent_id") and log.agent_id else "pero"

        await self.process_interaction(
            user_msg.content,
            assistant_msg.content,
            source=log.source,
            pair_id=log.pair_id,
            agent_id=agent_id,
        )
        return True

    async def generate_weekly_report(
        self, context: str, current_time: str, agent_name: str
    ) -> str:
        """
        生成周报 (Weekly Report)
        """
        print("[秘书] 开始生成周报...", flush=True)
        config = await self._get_scorer_config()
        if not config.get("api_key"):
            print("[秘书] 未配置 API Key，无法生成周报。")
            return ""

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        variables = {
            "agent_name": agent_name,
            "current_time": current_time,
            "context": context,
        }
        # 使用 PromptManager 丰富变量 (如果需要)
        from services.core.prompt_service import PromptManager

        pm = PromptManager()
        pm._enrich_variables(variables, is_social_mode=False, is_work_mode=False)

        prompt = self.mdp.render(
            "tasks/memory/scorer/weekly_report",
            variables,
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await llm.chat(messages, temperature=0.7)
            content = response["choices"][0]["message"]["content"]
            return content
        except Exception as e:
            print(f"[秘书] 生成周报出错: {e}")
            return ""

    async def generate_social_daily_report(
        self, context_text: str, date_str: str, total_messages: int, agent_name: str
    ) -> str:
        """
        生成社交日报 (Social Daily Report)
        """
        print(f"[秘书] 开始生成社交日报 ({date_str})...", flush=True)
        config = await self._get_scorer_config()
        if not config.get("api_key"):
            print("[秘书] 未配置 API Key，无法生成社交日报。")
            return ""

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        variables = {
            "agent_name": agent_name,
            "date_str": date_str,
            "total_messages": total_messages,
            "context_text": context_text,
        }

        from services.core.prompt_service import PromptManager

        pm = PromptManager()
        pm._enrich_variables(variables, is_social_mode=True, is_work_mode=False)

        prompt = self.mdp.render(
            "tasks/memory/scorer/social_daily",
            variables,
        )

        messages = [{"role": "user", "content": prompt}]

        # 增加重试机制
        retry_count = 3
        last_error = None

        for i in range(retry_count):
            try:
                response = await llm.chat(messages, temperature=0.7)
                content = response["choices"][0]["message"]["content"]
                return content
            except Exception as e:
                last_error = e
                print(
                    f"[秘书] 生成社交日报 LLM 请求失败 (尝试 {i + 1}/{retry_count}): {e}"
                )
                import asyncio

                await asyncio.sleep(2 * (i + 1))

        print(
            f"[秘书] 生成社交日报失败，已重试 {retry_count} 次。最后错误: {last_error}"
        )
        return ""

    async def generate_work_log_summary(
        self, task_name: str, log_text: str, agent_name: str
    ) -> str:
        """
        生成工作日志总结 (Work Log Summary)
        """
        print(f"[秘书] 开始生成工作日志总结 ({task_name})...", flush=True)
        config = await self._get_scorer_config()
        if not config.get("api_key"):
            print("[秘书] 未配置 API Key，无法生成工作日志总结。")
            return ""

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        variables = {
            "agent_name": agent_name,
            "task_name": task_name,
            "log_text": log_text,
        }

        from services.core.prompt_service import PromptManager

        pm = PromptManager()
        pm._enrich_variables(variables, is_social_mode=False, is_work_mode=True)

        prompt = self.mdp.render(
            "tasks/memory/scorer/work_log",
            variables,
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await llm.chat(messages)
            content = response["choices"][0]["message"]["content"]
            return content
        except Exception as e:
            print(f"[秘书] 生成工作日志总结出错: {e}")
            return ""

    async def generate_desktop_diary(
        self,
        chat_history: str,
        date_str: str,
        agent_name: str,
        owner_name: str = "主人",
    ) -> str:
        """
        生成桌宠日记 (Desktop Diary)
        """
        print(f"[秘书] 开始生成桌宠日记 ({date_str})...", flush=True)
        config = await self._get_scorer_config()
        if not config.get("api_key"):
            print("[秘书] 未配置 API Key，无法生成桌宠日记。")
            return ""

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        variables = {
            "agent_name": agent_name,
            "owner_name": owner_name,
            "date_str": date_str,
            "chat_history": chat_history,
        }

        from services.core.prompt_service import PromptManager

        pm = PromptManager()
        pm._enrich_variables(variables, is_social_mode=False, is_work_mode=False)

        prompt = self.mdp.render(
            "tasks/memory/scorer/desktop_diary",
            variables,
        )

        try:
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.7
            )
            content = response["choices"][0]["message"]["content"].strip()
            return content
        except Exception as e:
            print(f"[秘书] 生成桌宠日记出错: {e}")
            return ""

    async def update_waifu_texts(self, agent_id: str = "pero") -> int:
        """根据近期记忆更新欢迎语和系统台词"""
        try:
            # 1. 获取当前配置
            # 兼容旧 key: pero 使用 "waifu_dynamic_texts"，其他 agent 使用 "waifu_dynamic_texts_{agent_id}"
            config_key = (
                "waifu_dynamic_texts"
                if agent_id == "pero"
                else f"waifu_dynamic_texts_{agent_id}"
            )

            current_config = await self.session.get(Config, config_key)
            current_texts = {}
            if current_config:
                import contextlib

                with contextlib.suppress(Exception):
                    current_texts = json.loads(current_config.value)

            # 如果没有动态配置，尝试读取静态文件作为初始参考
            if not current_texts:
                try:
                    import os

                    # 1. 优先尝试从 Agent 自身的目录读取 (backend/services/mdp/agents/{agent_id}/waifu_texts.json)
                    base_dir = os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                    agent_path = os.path.join(
                        base_dir,
                        "backend",
                        "services",
                        "mdp",
                        "agents",
                        agent_id,
                        "waifu_texts.json",
                    )

                    if os.path.exists(agent_path):
                        static_path = agent_path
                    else:
                        # 2. 回退到公共的 public/waifu-texts.json
                        static_path = os.path.join(
                            base_dir, "public", "waifu-texts.json"
                        )

                    if os.path.exists(static_path):
                        with open(static_path, "r", encoding="utf-8") as f:
                            current_texts = json.load(f)
                except Exception as e:
                    print(f"[秘书] 加载静态 Waifu 文本失败: {e}")

            # 2. 获取近期记忆摘要作为上下文 (Filter by agent_id)
            statement = (
                select(Memory)
                .where(Memory.type == "event")
                .where(Memory.agent_id == agent_id)
                .order_by(desc(Memory.timestamp))
                .limit(20)
            )
            memories = (await self.session.exec(statement)).all()
            context_text = "\n".join([f"- {m.content}" for m in memories])

            if not context_text:
                return 0

            # 3. 构建 Prompt
            # 定义需要更新的字段及其说明
            target_fields = {
                "visibilityBack": "主人切回窗口时的欢迎语 (简短可爱)",
                "idleMessages": "挂机时的随机闲聊 (数组，3-5句)",
                "welcome_timeRanges_morningEarly": "清晨 (4:00-7:00) 问候",
                "welcome_timeRanges_morning": "上午 (7:00-11:00) 问候",
                "welcome_timeRanges_noon": "中午 (11:00-13:00) 问候",
                "welcome_timeRanges_afternoon": "下午 (13:00-17:00) 问候",
                "welcome_timeRanges_eveningSunset": "傍晚 (17:00-19:00) 问候",
                "welcome_timeRanges_night": "晚上 (19:00-22:00) 问候",
                "welcome_timeRanges_lateNight": "深夜 (22:00-24:00) 问候 (可以是数组)",
                "welcome_timeRanges_midnight": "凌晨 (0:00-4:00) 问候",
                "randTexturesNoClothes": "换装失败/没衣服时的吐槽",
                "randTexturesSuccess": "换装成功时的撒娇",
            }

            # 获取当前 Agent 名称
            config_manager = get_config_manager()
            from services.agent.agent_manager import AgentManager

            agent_manager = AgentManager()
            agent_profile = agent_manager.agents.get(agent_id)
            bot_name = (
                agent_profile.name
                if agent_profile
                else config_manager.get("bot_name", "Pero")
            )

            # 获取风格描述 (从 AgentProfile 或配置中获取，目前先从 Identity.md 中提取或默认)
            # 暂时使用默认风格
            tone_style = "可爱、元气、偶尔调皮或温柔"

            # 使用 Scorer 模型配置
            config = await self._get_scorer_config()
            if not config.get("api_key"):
                print("[秘书] 未配置 API Key，无法更新 Waifu 文本。")
                return 0

            llm = LLMService(
                api_key=config["api_key"],
                api_base=config["api_base"],
                model=config["model"],
            )

            prompt = self.mdp.render(
                "tasks/memory/scorer/waifu_text_updater",
                {
                    "agent_name": bot_name,
                    "tone_style": tone_style,
                    "context_text": context_text,
                    "current_texts": json.dumps(current_texts, ensure_ascii=False),
                    "target_fields": json.dumps(target_fields, ensure_ascii=False),
                },
            )

            # 4. 调用 LLM
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.7, timeout=300.0
            )
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            import re

            # 优先匹配 Markdown 代码块
            code_block_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", content)
            if code_block_match:
                json_str = code_block_match.group(1)
            else:
                # 备用：寻找最外层的 {}
                json_match = re.search(r"\{[\s\S]*\}", content)
                json_str = json_match.group(0) if json_match else None

            if json_str:
                new_texts = json.loads(json_str)

                # 简单校验
                if not isinstance(new_texts, dict):
                    return 0

                # 5. 保存更新到 Config (Welcome/System)
                if not current_config:
                    current_config = Config(
                        key=config_key, value=json.dumps(new_texts, ensure_ascii=False)
                    )
                    self.session.add(current_config)
                else:
                    current_config.value = json.dumps(new_texts, ensure_ascii=False)
                    self.session.add(current_config)  # 确保它被标记为更新

                # 6. [特性] 同步更新 PetState (Idle/Back/Click)
                # 这样前端 PetView 通过 get_pet_state 就能获取到最新的动态台词
                from models import PetState

                state = (
                    await self.session.exec(
                        select(PetState).where(PetState.agent_id == agent_id)
                    )
                ).first()
                if not state:
                    # 如果不存在则创建（虽然通常应该存在）
                    state = PetState(agent_id=agent_id)
                    self.session.add(state)

                if state:
                    # 更新回来时的消息
                    if "visibilityBack" in new_texts:
                        # PetState 期望 JSON 列表字符串
                        state.back_messages_json = json.dumps(
                            [new_texts["visibilityBack"]], ensure_ascii=False
                        )

                    # 更新空闲消息
                    if "idleMessages" in new_texts:
                        msgs = new_texts["idleMessages"]
                        if isinstance(msgs, str):
                            msgs = [msgs]
                        if isinstance(msgs, list):
                            state.idle_messages_json = json.dumps(
                                msgs, ensure_ascii=False
                            )

                    self.session.add(state)

                await self.session.commit()

                # [特性] 通过 Gateway 广播状态更新
                if state:
                    try:
                        from services.core.gateway_client import gateway_client

                        await gateway_client.broadcast_pet_state(state.model_dump())
                    except Exception as e:
                        print(f"[秘书] 广播失败: {e}")

                print(f"[秘书] 已更新动态 Waifu 文本 (Agent: {agent_id})。")
                return 1

        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"[秘书] 更新 Waifu 文本时出错: {e!r}")
            return 0

    async def process_interaction(
        self,
        user_content: str,
        assistant_content: str,
        source: str = "desktop",
        pair_id: str = None,
        agent_id: str = "pero",
    ):
        """
        处理一次交互：调用秘书分析，然后存入 Memory
        """
        print(
            f"[秘书] 开始交互分析... (pair_id: {pair_id}, agent_id: {agent_id})",
            flush=True,
        )

        # 智能清理助手内容以删除数据转储
        assistant_content = self._smart_clean_text(assistant_content)

        if pair_id:
            await self._update_log_status(pair_id, "processing")

        config = await self._get_scorer_config()

        if not config.get("api_key"):
            print("[秘书] 未配置 API Key，跳过分析。")
            if pair_id:
                await self._update_log_status(
                    pair_id, "failed", "未配置 API Key", increment_retry=True
                )
            return

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        # 获取当前 Agent 名称 (用于 Prompt 注入)
        config_manager = get_config_manager()

        # 获取 Agent Profile 以注入动态人设
        from services.agent.agent_manager import AgentManager

        agent_manager = AgentManager()
        # 使用传递的 agent_id 获取正确的 profile，如果未找到则回退到 active (尽管 agent_id 应该是正确的)
        agent_profile = agent_manager.agents.get(agent_id)
        if not agent_profile and agent_id == "pero":
            # 如果需要，为旧版 pero ID 逻辑回退
            agent_profile = agent_manager.agents.get(agent_manager.active_agent_id)

        bot_name = (
            agent_profile.name
            if agent_profile
            else config_manager.get("bot_name", "Pero")
        )

        # 确定角色标签，如果是系统触发则处理用户内容
        owner_name = "用户"
        try:
            # 查询 Config 表获取主人名称
            result = await self.session.exec(
                select(Config).where(Config.key == "owner_name")
            )
            config_entry = result.first()
            if config_entry and config_entry.value:
                owner_name = config_entry.value
        except Exception as e:
            print(f"[秘书] 获取 owner_name 失败: {e}")

        # 渲染分析提示词
        system_prompt = self.mdp.render(
            "tasks/memory/scorer/summary", {"agent_name": bot_name, "user": owner_name}
        )

        # 验证是否加载成功，如果包含 Error 则记录警告 (虽然 render 会返回错误信息，但不会抛出异常)
        if "Missing Prompt" in system_prompt:
            print(
                "[秘书] 警告: 缺少 MDP 提示词 'tasks/memory/scorer/summary'。请检查 mdp/prompts 目录。"
            )

        user_label = f"{owner_name} (主人)"

        # 检查系统提醒 (例如来自陪伴服务或计划任务)
        if user_content.strip().startswith("【管理系统提醒"):
            user_label = "系统事件 (非用户本人发言)"
            # 可选：为了帮助 LLM 理解，可以去除包装器，
            # 但保留它可能更好，以便 LLM 了解上下文。
            # 让我们保留它，但强调标签。

        # 使用 MDPManager 渲染 User Prompt
        user_prompt = self.mdp.render(
            "tasks/memory/scorer/user_input",
            {
                "user_label": user_label,
                "user_content": user_content,
                "agent_name": bot_name,
                "assistant_content": assistant_content,
            },
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # 使用 response_format={"type": "json_object"} 来强制 JSON 输出
            response = await llm.chat(
                messages,
                temperature=config["temperature"],
                response_format={"type": "json_object"},
            )
            content = response["choices"][0]["message"]["content"]

            # 解析 JSON
            data = None
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # 尝试修复 markdown json code block
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                    try:
                        data = json.loads(content)
                    except Exception:
                        print(f"[秘书] 即使在清理后仍无法解析 JSON: {content}")
                else:
                    print(f"[秘书] 无法解析 JSON: {content}")

            if not data or not data.get("content"):
                # 如果是 null 或没有内容，尝试更新日志元数据（即使没有记忆摘要）
                if pair_id:
                    try:
                        await self.session.execute(
                            update(ConversationLog)
                            .where(ConversationLog.pair_id == pair_id)
                            .values(
                                sentiment=data.get("sentiment") if data else None,
                                analysis_status="completed",
                                last_error=None,
                            )
                        )
                        await self.session.commit()
                        print(
                            f"[秘书] 已更新 pair_id 的 ConversationLog 元数据（仅情感）: {pair_id}"
                        )
                    except Exception as meta_err:
                        print(f"[秘书] 更新日志元数据失败: {meta_err}")

                print("[秘书] 未提取到有意义的记忆内容（已忽略）。")
                return

            # 使用服务保存到内存（处理 VectorDB 和聚类索引）
            clusters_list = data.get("clusters", [])
            clusters_str = (
                ",".join(clusters_list)
                if isinstance(clusters_list, list)
                else str(clusters_list)
            )
            tags_str = (
                ",".join(data.get("tags", []))
                if isinstance(data.get("tags"), list)
                else str(data.get("tags", ""))
            )

            memory = await MemoryService.save_memory(
                session=self.session,
                content=data["content"],
                tags=tags_str,
                clusters=clusters_str,
                importance=data.get("importance", 5),
                base_importance=data.get("importance", 5),
                sentiment=data.get("sentiment", "neutral"),
                source=source,
                memory_type=data.get("type", "event"),
                agent_id=agent_id,
            )

            # 3. 如果有 pair_id，更新对话日志的元数据
            if pair_id:
                try:
                    await self.session.execute(
                        update(ConversationLog)
                        .where(ConversationLog.pair_id == pair_id)
                        .values(
                            sentiment=data.get("sentiment"),
                            importance=data.get("importance"),
                            memory_id=memory.id,
                            analysis_status="completed",
                            last_error=None,
                        )
                    )
                except Exception as meta_err:
                    print(f"[秘书] 更新日志元数据失败: {meta_err}")

            # 注意：save_memory 已经提交，但如果未包含，update_log 需要提交
            await self.session.commit()
            print(f"[秘书] 记忆保存成功: {data['content']}")

        except Exception as e:
            print(f"[秘书] 处理交互时出错: {e}")
            if pair_id:
                await self._update_log_status(
                    pair_id, "failed", str(e), increment_retry=True
                )
