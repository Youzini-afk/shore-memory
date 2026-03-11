import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import col, delete, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import (
    AIModelConfig,
    Config,
    ConversationLog,
    MaintenanceRecord,
    Memory,
    MemoryRelation,
)
from services.core.llm_service import LLMService
from services.mdp.manager import mdp
from utils.workspace_utils import get_workspace_root


class ReflectionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_reflection_config(self):
        """获取反思模型配置 (通常是更强大的模型，如 GPT-4/Claude-3.5)"""
        # 复用 AgentService 中的逻辑，或者直接查询 Config
        # 这里简化处理，直接查 Config
        configs = {
            c.key: c.value for c in (await self.session.exec(select(Config))).all()
        }

        reflection_model_id = configs.get("reflection_model_id")

        # 默认回退到主模型
        main_model_id = configs.get("current_model_id")

        api_key = configs.get("global_llm_api_key", "")
        api_base = configs.get("global_llm_api_base", "https://api.openai.com")
        model = "gpt-4o"  # 如果一切都失败则回退，但我们首先尝试使用主模型

        if reflection_model_id:
            model_config = await self.session.get(
                AIModelConfig, int(reflection_model_id)
            )
            if model_config:
                api_key = (
                    model_config.api_key
                    if model_config.provider_type == "custom"
                    else api_key
                )
                api_base = (
                    model_config.api_base
                    if model_config.provider_type == "custom"
                    else api_base
                )
                model = model_config.model_id
        elif main_model_id:
            # 使用主模型作为回退
            model_config = await self.session.get(AIModelConfig, int(main_model_id))
            if model_config:
                api_key = (
                    model_config.api_key
                    if model_config.provider_type == "custom"
                    else api_key
                )
                api_base = (
                    model_config.api_base
                    if model_config.provider_type == "custom"
                    else api_base
                )
                model = model_config.model_id

        return {
            "api_key": api_key,
            "api_base": api_base,
            "model": model,
            "temperature": 0.4,  # 需要一定的创造力来发现关联，但不能太发散
        }

    async def backfill_failed_scorer_tasks(
        self, retry_limit: int = 3, concurrency_limit: int = 5, agent_id: str = None
    ):
        """
        [补录记忆]
        处理失败的Scorer分析任务
        """
        print(
            f"[Reflection] 开始回填失败的 Scorer 任务 (agent_id={agent_id})...",
            flush=True,
        )

        semaphore = asyncio.Semaphore(concurrency_limit)

        # 1. 查找失败的分析任务
        statement = select(ConversationLog).where(
            (ConversationLog.analysis_status == "failed")
            & (ConversationLog.retry_count < retry_limit)
        )

        if agent_id:
            statement = statement.where(ConversationLog.agent_id == agent_id)

        statement = statement.order_by(desc(ConversationLog.timestamp))

        failed_tasks = (await self.session.exec(statement)).all()
        if not failed_tasks:
            print("[Reflection] 没有需要回填的失败 Scorer 任务。")
            return

        # 2. 并发处理失败任务
        # 注意：必须为每个并发任务创建独立的 Session，因为 SQLAlchemy Session 不是并发安全的
        from sqlalchemy.orm import sessionmaker

        from database import engine

        async def retry_task(task_id):
            async with semaphore:
                async_session_factory = sessionmaker(
                    engine, class_=AsyncSession, expire_on_commit=False
                )
                async with async_session_factory() as local_session:
                    print(f"[Reflection] 正在回填失败的任务 (ID: {task_id})...")
                    # 本地导入以避免循环依赖
                    from services.memory.scorer_service import ScorerService

                    scorer_service = ScorerService(local_session)
                    await scorer_service.retry_interaction(task_id)

        tasks = [retry_task(task.id) for task in failed_tasks]
        await asyncio.gather(*tasks)

        await self.session.commit()
        print(f"[Reflection] 已回填 {len(failed_tasks)} 个失败的 Scorer 任务。")

    async def consolidate_memories(
        self,
        lookback_days: int = 3,
        importance_threshold: int = 4,
        agent_id: str = "pero",
    ):
        """
        [记忆整合]
        压缩低重要性、陈旧的记忆为陈述性总结。
        """
        print(
            f"[Reflection] 开始记忆整合 (超过 {lookback_days} 天，重要性 < {importance_threshold}, agent_id={agent_id})...",
            flush=True,
        )

        # 1. 查找候选记忆
        cutoff_time = datetime.now() - timedelta(days=lookback_days)
        cutoff_timestamp = cutoff_time.timestamp() * 1000

        statement = (
            select(Memory)
            .where(
                (Memory.type == "event")
                & (Memory.timestamp < cutoff_timestamp)
                & (Memory.importance < importance_threshold)
                & (Memory.agent_id == agent_id)
            )
            .order_by(Memory.timestamp)
        )

        candidates = (await self.session.exec(statement)).all()

        if not candidates:
            print("[Reflection] 没有需要整合的记忆。")
            return

        # 2. 按日期分组
        grouped = defaultdict(list)
        for m in candidates:
            # 按 YYYY-MM-DD 分组
            date_key = m.realTime.split(" ")[0] if m.realTime else "unknown"
            grouped[date_key].append(m)

        config = await self._get_reflection_config()
        if not config["api_key"]:
            print("[Reflection] 未配置 API Key，跳过整合。")
            return

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        # 3. 处理每一组
        for date_key, group in grouped.items():
            if len(group) < 3:
                continue  # 跳过太少的组

            print(f"[Reflection] 正在整合来自 {date_key} 的 {len(group)} 条记忆...")

            # 生成总结
            temp = config.get("temperature", 0.4)
            summary_text = await self._generate_summary(
                llm, group, date_key, temperature=temp
            )
            if not summary_text:
                continue

            # 保存到文件 (MD) - 根据用户请求移除
            # from utils.memory_file_manager import MemoryFileManager
            # file_path = await MemoryFileManager.save_log("periodic_summaries", f"{date_key}_Consolidated", summary_text)

            # 创建总结性记忆
            # 我们将其插入到该组第一条记忆的位置
            first_mem = group[0]
            last_mem = group[-1]

            # 计算平均重要性并略微提升
            avg_imp = sum(m.importance for m in group) / len(group)
            new_importance = min(10, int(avg_imp) + 1)

            # 生成 Embedding
            from services.core.embedding_service import embedding_service

            embedding_json = "[]"
            try:
                vec = await embedding_service.encode_one(summary_text)
                embedding_json = json.dumps(vec)
            except Exception:
                pass

            db_content = summary_text

            summary_mem = Memory(
                content=db_content,
                tags="summary,consolidated",
                importance=new_importance,
                base_importance=float(new_importance),
                sentiment="neutral",
                timestamp=first_mem.timestamp,  # 使用第一条的时间
                realTime=first_mem.realTime,
                source="system",
                type="summary",
                embedding_json=embedding_json,
                agent_id=agent_id,
            )
            self.session.add(summary_mem)
            await self.session.flush()  # 获取 ID
            await self.session.refresh(summary_mem)

            # 更新链表 (跳过该组)
            # A -> [B -> ... -> D] -> E
            # 变为: A -> S -> E

            prev_node = None
            if first_mem.prev_id:
                prev_node = await self.session.get(Memory, first_mem.prev_id)

            next_node = None
            if last_mem.next_id:
                next_node = await self.session.get(Memory, last_mem.next_id)

            if prev_node:
                prev_node.next_id = summary_mem.id
                summary_mem.prev_id = prev_node.id
                self.session.add(prev_node)

            # 如果 group 包含了 next_node (逻辑上不可能，因为我们是按时间排序的一组)，但为了安全
            if next_node and next_node.id != summary_mem.id:
                next_node.prev_id = summary_mem.id
                summary_mem.next_id = next_node.id
                self.session.add(next_node)

            # 归档原始记忆
            archived_ids = []
            for m in group:
                m.type = "archived_event"
                self.session.add(m)
                archived_ids.append(m.id)

            # 记录维护日志
            record = MaintenanceRecord(
                consolidated=len(group),
                created_ids=json.dumps([summary_mem.id]),
                modified_data=json.dumps({"archived_ids": archived_ids}),
            )
            self.session.add(record)

            # 立即提交，释放写锁，防止长事务阻塞
            await self.session.commit()
            print(
                f"[Reflection] 已将 {len(group)} 条记忆整合为 ID {summary_mem.id}: {summary_text[:50]}..."
            )

        print("[Reflection] 记忆整合完成。")

    async def generate_desktop_diary(
        self, agent_id: str = "pero", date_str: str = None
    ) -> Optional[str]:
        """
        生成桌宠日记 (Desktop Mode Diary)
        保存为文件，不入库
        """
        print("[Reflection] 开始生成桌宠日记...", flush=True)

        # 1. 确定日期范围
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        # 2. 获取对话记录 (排除社交模式)
        stmt = (
            select(ConversationLog)
            .where(
                (ConversationLog.timestamp >= start_of_day)
                & (ConversationLog.timestamp <= end_of_day)
                & (ConversationLog.source != "social")
                & (ConversationLog.agent_id == agent_id)
            )
            .order_by(ConversationLog.timestamp)
        )

        logs = (await self.session.exec(stmt)).all()

        if not logs:
            print("[Reflection] 今天没有桌面交互记录，跳过日记生成。")
            return None

        # 3. 格式化对话
        chat_history = ""
        for log in logs:
            role_name = "主人" if log.role == "user" else agent_id
            content = log.content[:200]  # 简单截断
            chat_history += (
                f"[{log.timestamp.strftime('%H:%M')}] {role_name}: {content}\n"
            )

        # 4. 委托给 ScorerService 生成日记内容
        from services.memory.scorer_service import ScorerService

        scorer_service = ScorerService(self.session)

        # 获取 owner_name (ScorerService 也可以自己获取，但这里既然已经查了配置，可以传递进去，或者简化)
        # ScorerService 的 generate_desktop_diary 接受 owner_name
        configs = {
            c.key: c.value for c in (await self.session.exec(select(Config))).all()
        }
        owner_name = configs.get("owner_name", "主人")

        diary_content = await scorer_service.generate_desktop_diary(
            chat_history=chat_history[:10000],
            date_str=date_str,
            agent_name=agent_id,
            owner_name=owner_name,
        )

        if not diary_content:
            print("[Reflection] 日记生成失败 (Empty content)。")
            return None

        # 6. 保存文件
        # Path: {Workspace}/[agent_id]/diaries/YYYY-MM-DD.md
        # 定位相对于此文件或项目根目录的 workspace
        # 假设 backend 在 {ProjectRoot}/backend
        # workspace 在 {ProjectRoot}/pero_workspace

        # 健壮的路径查找
        agent_workspace = get_workspace_root(agent_id)
        diary_dir = os.path.join(agent_workspace, "diaries")
        os.makedirs(diary_dir, exist_ok=True)

        file_path = os.path.join(diary_dir, f"{date_str}.md")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(diary_content)
            print(f"[Reflection] 日记已保存至: {file_path}")
            return file_path
        except Exception as e:
            print(f"[Reflection] 保存日记文件失败: {e}")
            return None

    async def _generate_summary(
        self,
        llm: LLMService,
        memories: List[Memory],
        date_str: str,
        temperature: float = 0.3,
    ) -> str:
        mem_text = "\n".join(
            [
                f"- {m.realTime.split(' ')[1] if m.realTime else ''}: {m.content}"
                for m in memories
            ]
        )

        prompt = mdp.render(
            "tasks/memory/reflection/summary",
            {"date_str": date_str, "mem_text": mem_text},
        )

        try:
            res = await llm.chat([{"role": "user", "content": prompt}], temperature=0.3)
            return res["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"生成总结失败: {e}")
            return None

    async def _get_bot_name(self) -> str:
        try:
            config_entry = await self.session.get(Config, "bot_name")
            return config_entry.value if config_entry and config_entry.value else "Pero"
        except Exception:
            return "Pero"

    async def run_maintenance(self) -> dict:
        """运行增强版记忆整理任务（多 Agent 支持）"""
        # 使用 Reflection 配置
        config = await self._get_reflection_config()
        if not config["api_key"]:
            print("[Reflection] 未配置 API Key，无法运行维护任务。")
            return {"status": "error", "error": "No API Key"}

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        self.created_ids = []
        self.deleted_data = []
        self.modified_data = []

        report = {
            "preferences_extracted": 0,
            "important_tagged": 0,
            "clustered_count": 0,
            "consolidated": 0,
            "cleaned_count": 0,
            "retired_count": 0,
            "social_summaries_cleaned": 0,
            "waifu_texts_updated": 0,
            "status": "success",
            "agents_processed": [],
        }

        try:
            # 0. 识别 Agent
            from sqlalchemy import distinct

            from models import Memory

            stmt = select(distinct(Memory.agent_id))
            agent_ids = (await self.session.exec(stmt)).all()
            # 如果 DB 为空或包含 null，确保至少处理 'pero'
            agent_ids = [aid for aid in agent_ids if aid]
            if not agent_ids:
                agent_ids = ["pero"]

            report["agents_processed"] = agent_ids
            print(f"[Reflection] 正在为以下代理运行维护: {agent_ids}")

            for agent_id in agent_ids:
                print(f"[Reflection] 正在处理代理: {agent_id}")
                # 1. 提取偏好 (已按需关闭)
                report["preferences_extracted"] += (
                    0  # await self._extract_preferences(llm, agent_id)
                )

                # 2. 标记重要性
                report["important_tagged"] += await self._tag_importance(llm, agent_id)

                # 3. 自动归簇
                report["clustered_count"] += await self._cluster_memories(llm, agent_id)

                # 4. 记忆合并
                for _ in range(3):
                    merged_count = await self._consolidate_memories(
                        llm, offset=0, agent_id=agent_id
                    )
                    report["consolidated"] += merged_count
                    if merged_count == 0:
                        break

                # 5. 新增：清理可疑/错误记忆
                report["cleaned_count"] += await self._clean_invalid_memories(
                    llm, agent_id
                )

                # 6. 新增：自动清理重复的社交日报总结
                report[
                    "social_summaries_cleaned"
                ] += await self._clean_duplicate_social_summaries(agent_id)

                # 6. 维护边界处理
                report["retired_count"] += await self._handle_maintenance_boundary(
                    agent_id
                )

            # 7. 调用 ScorerService 更新台词 (因为这是生成任务)
            # 维护任务现在不再负责更新台词，而是由 ScorerService 负责
            # 但为了保持兼容性，我们可以顺便触发一下 ScorerService
            try:
                from services.memory.scorer_service import ScorerService

                scorer_service = ScorerService(self.session)
                # 为每个 active agent 更新
                for agent_id in agent_ids:
                    report[
                        "waifu_texts_updated"
                    ] += await scorer_service.update_waifu_texts(agent_id)
            except Exception as e:
                print(f"[Reflection] 触发 Scorer 更新台词失败: {e}")

            # 8. 保存维护记录用于撤回
            record = MaintenanceRecord(
                preferences_extracted=report["preferences_extracted"],
                important_tagged=report["important_tagged"],
                clustered_count=report["clustered_count"],
                consolidated=report["consolidated"],
                cleaned_count=report["cleaned_count"],
                created_ids=json.dumps(self.created_ids),
                deleted_data=json.dumps(
                    self.deleted_data, ensure_ascii=False, default=str
                ),
                modified_data=json.dumps(
                    self.modified_data, ensure_ascii=False, default=str
                ),
            )
            self.session.add(record)
            await self.session.commit()
            await self.session.refresh(record)

            report["record_id"] = record.id
            print(f"[Reflection] 维护完成。记录 ID: {record.id}, 报告: {report}")
            return report

        except Exception as e:
            import traceback

            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    async def _clean_invalid_memories(self, llm: LLMService, agent_id: str) -> int:
        """识别并清理可疑、矛盾或复读的错误记忆"""
        statement = (
            select(Memory)
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(100)
        )
        memories = (await self.session.exec(statement)).all()

        if len(memories) < 5:
            return 0

        mem_data = [
            {"id": m.id, "content": m.content, "type": m.type} for m in memories
        ]

        # 如果不是 Pero，使用 agent_id 作为名字
        bot_name = await self._get_bot_name()
        if agent_id != "pero":
            bot_name = agent_id.capitalize()

        prompt = mdp.render(
            "tasks/memory/reflection/memory_auditor",
            {
                "agent_name": bot_name,
                "memory_data": json.dumps(mem_data, ensure_ascii=False),
            },
        )

        try:
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.2
            )
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            import re

            match = re.search(r"\[.*\]", content, re.S)
            if match:
                ids_to_delete = json.loads(match.group(0))
                if not isinstance(ids_to_delete, list):
                    print(
                        f"[Reflection] LLM 返回格式错误 (期望 list): {type(ids_to_delete)}"
                    )
                    return 0

                count = 0
                for mid in ids_to_delete:
                    try:
                        mem_id = int(mid)
                        mem = await self.session.get(Memory, mem_id)
                        if mem:
                            self.deleted_data.append(mem.dict())
                            await self.session.delete(mem)

                            # [Fix] 同步删除向量
                            try:
                                from services.core.vector_service import vector_service

                                vector_service.delete_memory(mem.id, agent_id=agent_id)
                            except Exception as ve:
                                print(f"[Reflection] 向量删除失败: {ve}")

                            count += 1
                    except ValueError:
                        print(f"[Reflection] 跳过无效 ID: {mid}")
                        continue

                await self.session.commit()
                return count
        except Exception as e:
            print(f"清理记忆时出错: {e}")
            import traceback

            traceback.print_exc()
        return 0

    async def _extract_preferences(self, llm: LLMService, agent_id: str) -> int:
        """从记忆中提取长期偏好 (优化提示词)"""
        statement = (
            select(Memory)
            .where(Memory.type == "event")
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(50)
        )
        memories = (await self.session.exec(statement)).all()
        if not memories:
            return 0

        memory_texts = [f"- {m.content}" for m in memories]

        bot_name = await self._get_bot_name()
        if agent_id != "pero":
            bot_name = agent_id.capitalize()

        prompt = mdp.render(
            "tasks/memory/reflection/preference_extractor",
            {"agent_name": bot_name, "memory_texts": "\n".join(memory_texts)},
        )

        try:
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.3
            )
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            import re

            json_match = re.search(r"\[.*\]", content, re.S)
            if json_match:
                preferences = json.loads(json_match.group(0))
                if not isinstance(preferences, list):
                    print(
                        f"[Reflection] LLM 返回格式错误 (期望 list): {type(preferences)}"
                    )
                    return 0

                count = 0
                for pref in preferences:
                    if not isinstance(pref, str):
                        continue

                    existing = (
                        await self.session.exec(
                            select(Memory)
                            .where(Memory.type == "preference")
                            .where(Memory.content == pref)
                            .where(Memory.agent_id == agent_id)
                        )
                    ).first()
                    if not existing:
                        new_mem = Memory(
                            content=pref,
                            type="preference",
                            source="reflection",
                            tags="偏好",
                            agent_id=agent_id,
                        )
                        self.session.add(new_mem)
                        await self.session.flush()  # 获取 ID
                        self.created_ids.append(new_mem.id)
                        count += 1
                await self.session.commit()
                return count
        except Exception as e:
            print(f"提取偏好时出错: {e}")
            import traceback

            traceback.print_exc()
        return 0

    async def _cluster_memories(self, llm: LLMService, agent_id: str = "pero") -> int:
        """为未归类的记忆分配思维簇"""
        # 查找 clusters 为空或 null 的 event 类型记忆
        statement = (
            select(Memory)
            .where(
                Memory.agent_id == agent_id,
                (Memory.clusters is None) | (Memory.clusters == ""),
            )
            .order_by(desc(Memory.timestamp))
            .limit(50)
        )

        memories = (await self.session.exec(statement)).all()
        if not memories:
            return 0

        mem_data = [{"id": m.id, "content": m.content} for m in memories]
        bot_name = await self._get_bot_name()

        prompt = mdp.render(
            "tasks/memory/reflection/memory_clusterizer",
            {
                "agent_name": bot_name,
                "memory_data": json.dumps(mem_data, ensure_ascii=False),
            },
        )

        try:
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.2
            )
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            import re

            json_match = re.search(r"\{.*\}", content, re.S)
            if json_match:
                updates = json.loads(json_match.group(0))
                count = 0
                for m in memories:
                    if str(m.id) in updates:
                        self.modified_data.append(m.dict())
                        clusters = updates[str(m.id)]
                        if isinstance(clusters, list):
                            m.clusters = ",".join(clusters)
                        elif isinstance(clusters, str):
                            m.clusters = clusters

                        # [修复] 簇变更后更新向量元数据
                        try:
                            from services.core.embedding_service import (
                                embedding_service,
                            )
                            from services.core.vector_service import vector_service

                            enriched = (
                                f"{m.tags} {m.tags} {m.content}"
                                if m.tags
                                else m.content
                            )
                            new_vec = await embedding_service.encode_one(enriched)

                            if new_vec:
                                metadata_dict = {
                                    "type": m.type,
                                    "timestamp": m.timestamp,
                                    "importance": float(m.importance),
                                    "tags": m.tags,
                                    "clusters": m.clusters,
                                    "agent_id": agent_id,
                                }

                                if m.clusters:
                                    cluster_list = [
                                        c.strip()
                                        for c in m.clusters.split(",")
                                        if c.strip()
                                    ]
                                    for c in cluster_list:
                                        clean_c = c.replace("[", "").replace("]", "")
                                        if clean_c:
                                            metadata_dict[f"cluster_{clean_c}"] = True

                                vector_service.add_memory(
                                    memory_id=m.id,
                                    content=m.content,
                                    embedding=new_vec,
                                    metadata=metadata_dict,
                                )
                        except Exception as e:
                            print(f"[Reflection] 更新簇向量失败: {e}")

                        self.session.add(m)
                        count += 1
                await self.session.commit()
                return count
        except Exception as e:
            print(f"归类记忆簇时出错: {e}")
        return 0

    async def _tag_importance(self, llm: LLMService, agent_id: str = "pero") -> int:
        """优化重要性打分逻辑"""
        statement = (
            select(Memory)
            .where(Memory.type == "event")
            .where(Memory.importance == 1)
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(50)
        )
        memories = (await self.session.exec(statement)).all()
        if not memories:
            return 0

        mem_data = [{"id": m.id, "content": m.content} for m in memories]

        bot_name = await self._get_bot_name()
        prompt = mdp.render(
            "tasks/memory/reflection/importance_tagger",
            {
                "agent_name": bot_name,
                "memory_data": json.dumps(mem_data, ensure_ascii=False),
            },
        )

        try:
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.2
            )
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            import re

            json_match = re.search(r"\{.*\}", content, re.S)
            if json_match:
                updates = json.loads(json_match.group(0))
                count = 0
                for m in memories:
                    if str(m.id) in updates:
                        self.modified_data.append(m.dict())
                        info = updates[str(m.id)]
                        m.importance = info.get("importance", m.importance)
                        new_tags = info.get("tags", [])
                        if not new_tags and "tag" in info:
                            new_tags = [info["tag"]]

                        if new_tags:
                            current_tags = set(m.tags.split(",")) if m.tags else set()
                            for t in new_tags:
                                if t:
                                    current_tags.add(t)
                            m.tags = ",".join(filter(None, current_tags))

                            # [Fix] 标签变更后更新向量
                            try:
                                from services.core.embedding_service import (
                                    embedding_service,
                                )
                                from services.core.vector_service import vector_service

                                enriched = f"{m.tags} {m.tags} {m.content}"
                                new_vec = await embedding_service.encode_one(enriched)
                                if new_vec:
                                    vector_service.add_memory(
                                        memory_id=m.id,
                                        content=m.content,
                                        embedding=new_vec,
                                        metadata={
                                            "type": m.type,
                                            "timestamp": m.timestamp,
                                            "importance": float(m.importance),
                                            "tags": m.tags,
                                            "agent_id": agent_id,
                                        },
                                    )
                            except Exception as e:
                                print(f"[Reflection] 更新标签向量失败: {e}")

                        self.session.add(m)
                        count += 1
                await self.session.commit()
                return count
        except Exception as e:
            print(f"标记重要性时出错: {e}")
        return 0

    async def _consolidate_memories(
        self, llm: LLMService, offset: int = 0, agent_id: str = "pero"
    ) -> int:
        """合并相似记忆 (优化提示词)"""
        # 修改：同时拉取 'event' 和 'interaction_summary' 类型的记忆进行熔炼
        # 排除 source='secretary_merge' 的记忆，避免递归合并已生成的总结
        statement = (
            select(Memory)
            .where(
                Memory.type.in_(["event", "interaction_summary"]),
                Memory.source != "secretary_merge",
                Memory.agent_id == agent_id,
            )
            .order_by(desc(Memory.timestamp))
            .offset(offset)
            .limit(100)
        )

        memories = (await self.session.exec(statement)).all()
        if len(memories) < 5:
            return 0

        batch_memories = memories[:80]
        mem_data = [
            {"id": m.id, "content": m.content, "time": m.realTime}
            for m in batch_memories
        ]

        bot_name = await self._get_bot_name()
        if agent_id != "pero":
            bot_name = agent_id.capitalize()

        prompt = mdp.render(
            "tasks/memory/reflection/memory_consolidator",
            {
                "agent_name": bot_name,
                "memory_data": json.dumps(mem_data, ensure_ascii=False),
            },
        )

        try:
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.2
            )
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            import re

            json_match = re.search(r"\[.*\]", content, re.S)
            if json_match:
                merges = json.loads(json_match.group(0))
                count = 0
                for merge in merges:
                    valid_ids = [
                        int(mid)
                        for mid in merge.get("ids_to_merge", [])
                        if any(m.id == int(mid) for m in batch_memories)
                    ]
                    if len(valid_ids) < 2:
                        continue

                    new_tags = merge.get("tags", [])
                    if not new_tags and "tag" in merge:
                        new_tags = [merge["tag"]]
                    if not new_tags:
                        new_tags = ["回忆"]

                    new_mem = Memory(
                        content=merge["new_content"],
                        tags=",".join(filter(None, new_tags)),
                        importance=merge.get("importance", 3),
                        source="reflection_merge",  # 更改自 secretary_merge
                        type="event",
                        realTime=batch_memories[0].realTime,
                        agent_id=agent_id,
                    )
                    self.session.add(new_mem)
                    await self.session.flush()
                    self.created_ids.append(new_mem.id)

                    # [修复] 立即生成并同步向量，确保新节点可被检索
                    try:
                        from services.core.embedding_service import embedding_service
                        from services.core.vector_service import vector_service

                        # 生成向量
                        content_vec = await embedding_service.encode_one(
                            new_mem.content
                        )
                        if content_vec:
                            # 如果有 tags，增强向量权重
                            final_vec = content_vec
                            if new_mem.tags:
                                enriched = (
                                    f"{new_mem.tags} {new_mem.tags} {new_mem.content}"
                                )
                                final_vec = await embedding_service.encode_one(enriched)

                            # 写入 VectorDB
                            vector_service.add_memory(
                                memory_id=new_mem.id,
                                content=new_mem.content,
                                embedding=final_vec,
                                metadata={
                                    "type": new_mem.type,
                                    "timestamp": new_mem.timestamp,
                                    "importance": float(new_mem.importance),
                                    "tags": new_mem.tags,
                                    "agent_id": agent_id,
                                },
                            )
                    except Exception as ve:
                        print(f"[Reflection] 警告: 新合并记忆向量生成失败: {ve}")

                    # [增强] 关系迁移：将旧节点的连接继承给新节点
                    try:
                        # 1. 查找所有涉及 valid_ids 的关系
                        stmt_rel = select(MemoryRelation).where(
                            (col(MemoryRelation.source_id).in_(valid_ids))
                            | (col(MemoryRelation.target_id).in_(valid_ids))
                        )
                        existing_relations = (await self.session.exec(stmt_rel)).all()

                        processed_pairs = set()  # (source, target) 用于去重

                        for rel in existing_relations:
                            # Case 1: 内部关系 (Source 和 Target 都在合并范围内) -> 丢弃 (已内化)
                            if (
                                rel.source_id in valid_ids
                                and rel.target_id in valid_ids
                            ):
                                continue

                            # Case 2: 对外关系 (Source 在范围内 -> 变为 New -> Target)
                            if rel.source_id in valid_ids:
                                new_source = new_mem.id
                                new_target = rel.target_id
                            # Case 3: 被引用关系 (Target 在范围内 -> 变为 Source -> New)
                            else:  # rel.target_id in valid_ids
                                new_source = rel.source_id
                                new_target = new_mem.id

                            # 去重检查
                            if (new_source, new_target) not in processed_pairs:
                                processed_pairs.add((new_source, new_target))
                                self.session.add(
                                    MemoryRelation(
                                        source_id=new_source,
                                        target_id=new_target,
                                        relation_type=rel.relation_type,
                                        strength=rel.strength,
                                        description=rel.description,
                                    )
                                )

                        # 显式删除旧关系 (防止僵尸数据)
                        if existing_relations:
                            rel_ids = [r.id for r in existing_relations]
                            if rel_ids:
                                await self.session.exec(
                                    delete(MemoryRelation).where(
                                        col(MemoryRelation.id).in_(rel_ids)
                                    )
                                )

                    except Exception as e:
                        print(f"[Reflection] 关系迁移失败: {e}")

                    for mid in valid_ids:
                        m_obj = next(m for m in batch_memories if m.id == mid)
                        self.deleted_data.append(m_obj.dict())
                        await self.session.exec(delete(Memory).where(Memory.id == mid))

                        # [Fix] 同步删除向量
                        try:
                            from services.core.vector_service import vector_service

                            vector_service.delete_memory(mid, agent_id=agent_id)
                        except Exception as ve:
                            print(f"[Reflection] 向量删除失败: {ve}")

                    count += 1
                await self.session.commit()
                return count
        except Exception as e:
            print(f"整合记忆时出错: {e}")
        return 0

    async def _clean_duplicate_social_summaries(self, agent_id: str) -> int:
        """清理重复生成的社交日报记忆"""
        import re
        from collections import defaultdict

        try:
            # 查找包含社交日报标题的所有记忆
            statement = (
                select(Memory)
                .where(Memory.content.like("%【社交日报%"))
                .where(Memory.agent_id == agent_id)
            )
            memories = (await self.session.exec(statement)).all()

            if len(memories) < 2:
                return 0

            # 按日期分组
            date_groups = defaultdict(list)
            pattern = re.compile(r"【社交日报 (\d{4}-\d{2}-\d{2})】")

            for mem in memories:
                match = pattern.search(mem.content)
                if match:
                    date_str = match.group(1)
                    date_groups[date_str].append(mem)

            total_deleted = 0
            for _, mem_list in date_groups.items():
                if len(mem_list) > 1:
                    # 按 ID 排序，保留最新的（ID 最大的）
                    mem_list.sort(key=lambda x: x.id)
                    to_delete = mem_list[:-1]

                    for mem in to_delete:
                        self.deleted_data.append(mem.dict())
                        await self.session.delete(mem)

                        # [Fix] 同步删除向量
                        try:
                            from services.core.vector_service import vector_service

                            vector_service.delete_memory(mem.id, agent_id=agent_id)
                        except Exception as ve:
                            print(f"[Reflection] 向量删除失败: {ve}")

                        total_deleted += 1

            if total_deleted > 0:
                await self.session.commit()
                print(f"[Reflection] 清理了 {total_deleted} 条重复的社交摘要。")
            return total_deleted

        except Exception as e:
            print(f"清理重复社交摘要时出错: {e}")
            return 0

    async def _handle_maintenance_boundary(self, agent_id: str) -> int:
        """处理 1000 条维护边界"""
        try:
            statement = (
                select(Memory)
                .where(Memory.type == "event")
                .where(Memory.agent_id == agent_id)
                .order_by(desc(Memory.timestamp))
                .offset(1000)
                .limit(100)
            )

            old_memories = (await self.session.exec(statement)).all()
            if not old_memories:
                return 0

            count = 0
            for mem in old_memories:
                if mem.importance < 3:  # 仅自动删除低重要性的
                    self.deleted_data.append(mem.dict())
                    await self.session.delete(mem)

                    # 同步删除向量
                    try:
                        from services.core.vector_service import vector_service

                        vector_service.delete_memory(mem.id, agent_id=agent_id)
                    except Exception as ve:
                        print(f"[Reflection] 向量删除失败: {ve}")

                    count += 1

            if count > 0:
                await self.session.commit()
                print(f"[Reflection] 边界维护清理了 {count} 条陈旧记忆。")
            return count

        except Exception as e:
            print(f"边界维护出错: {e}")
            return 0

    async def dream_and_associate(self, limit: int = 5, agent_id: str = "pero") -> dict:
        from services.memory.memory_service import MemoryService

        print(
            f"[Reflection] 进入梦境模式 (扫描关联, agent_id={agent_id})...", flush=True
        )

        # 1. 获取最近的 N 条记忆 (Event 类型) 作为"梦境锚点"
        statement = (
            select(Memory)
            .where(Memory.type == "event")
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(limit)
        )
        anchors = (await self.session.exec(statement)).all()

        if len(anchors) < 1:
            print("[Reflection] 记忆不足，无法关联。")
            return {"status": "skipped", "reason": "Not enough memories to associate"}

        config = await self._get_reflection_config()
        if not config["api_key"]:
            print("[Reflection] 未配置 API Key，跳过。")
            return {"status": "skipped", "reason": "No API Key configured"}

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        # 2. 针对每个锚点，使用记忆检索算法寻找相关记忆
        # 这比简单的滑动窗口更智能，能发现跨度很大的深层联系
        processed_pairs = set()
        new_relations_count = 0

        for target_memory in anchors:
            print(f"[Reflection] 正在梦到: {target_memory.content[:30]}...")

            # 使用 MemoryService 的高级检索 (Vector + Graph)
            # 排除掉自己，且不限制时间范围 (exclude_after_time=None) 以允许连接过去
            candidates = await MemoryService.get_relevant_memories(
                self.session, target_memory.content, limit=5, agent_id=agent_id
            )

            for candidate in candidates:
                if candidate.id == target_memory.id:
                    continue

                # 避免重复处理同一对 (A, B) 和 (B, A)
                pair_key = tuple(sorted((target_memory.id, candidate.id)))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)

                # 检查数据库中是否已经存在关联
                existing = await self.session.exec(
                    select(MemoryRelation).where(
                        (
                            (MemoryRelation.source_id == target_memory.id)
                            & (MemoryRelation.target_id == candidate.id)
                        )
                        | (
                            (MemoryRelation.source_id == candidate.id)
                            & (MemoryRelation.target_id == target_memory.id)
                        )
                    )
                )
                if existing.first():
                    continue  # 已关联，跳过

                # 3. 调用 LLM 判断关联
                relation = await self._analyze_relation(llm, target_memory, candidate)

                if relation:
                    # 4. 写入数据库
                    new_relation = MemoryRelation(
                        source_id=target_memory.id,
                        target_id=candidate.id,
                        relation_type=relation["type"],
                        strength=relation["strength"],
                        description=relation["description"],
                        agent_id=agent_id,
                    )
                    self.session.add(new_relation)
                    await self.session.commit()  # 发现一个关联就提交一个，避免长事务
                    print(
                        f"[Reflection] 发现新关联: {relation['description']} (强度: {relation['strength']})"
                    )
                    new_relations_count += 1

        print("[Reflection] 梦境循环完成。")
        return {
            "status": "success",
            "new_relations": new_relations_count,
            "anchors_processed": len(anchors),
        }

    async def scan_lonely_memories(
        self, limit: int = 5, agent_id: str = "pero"
    ) -> dict:
        """
        [孤独记忆扫描器]
        寻找那些没有关联 (MemoryRelation) 的孤立记忆，并尝试将它们织入关系网。
        """
        from services.memory.memory_service import MemoryService

        print(f"[Reflection] 正在扫描孤独记忆 (agent_id={agent_id})...", flush=True)

        # 1. 查找孤立记忆 (没有作为 source 或 target 出现在 Relation 表中)
        # 优化: 使用 SQL 过滤而非 Python 内存过滤，避免全量加载 Memory 表导致阻塞

        # 获取所有有关系的 ID (仅限当前 Agent)
        rel_statement = select(
            MemoryRelation.source_id, MemoryRelation.target_id
        ).where(MemoryRelation.agent_id == agent_id)
        relations = (await self.session.exec(rel_statement)).all()
        connected_ids = set()
        for src, tgt in relations:
            connected_ids.add(src)
            connected_ids.add(tgt)

        # 查找不在 connected_ids 中的最近记忆
        # SQLModel/SQLAlchemy 不直接支持 "NOT IN" 大集合的高效查询，
        # 我们使用 LEFT OUTER JOIN 或者 NOT EXISTS 子查询会更好。
        # 但为了简单，我们先获取一批最近的记忆，然后在内存中过滤 (因为 limit 很小)

        # 获取最近 100 条 event 记忆
        mem_statement = (
            select(Memory)
            .where(Memory.type == "event")
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(100)
        )
        recent_memories = (await self.session.exec(mem_statement)).all()

        lonely_memories = []
        for mem in recent_memories:
            if mem.id not in connected_ids:
                lonely_memories.append(mem)
                if len(lonely_memories) >= limit:
                    break

        if not lonely_memories:
            return {"status": "skipped", "reason": "No lonely memories found"}

        config = await self._get_reflection_config()
        if not config["api_key"]:
            return {"status": "skipped", "reason": "No API Key"}

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        new_relations_count = 0

        for target_memory in lonely_memories:
            # 尝试为孤独记忆寻找家
            print(f"[Reflection] 尝试挽救孤独记忆: {target_memory.content[:30]}...")

            candidates = await MemoryService.get_relevant_memories(
                self.session, target_memory.content, limit=5, agent_id=agent_id
            )

            for candidate in candidates:
                if candidate.id == target_memory.id:
                    continue

                # 检查重复
                existing = await self.session.exec(
                    select(MemoryRelation).where(
                        (
                            (MemoryRelation.source_id == target_memory.id)
                            & (MemoryRelation.target_id == candidate.id)
                        )
                        | (
                            (MemoryRelation.source_id == candidate.id)
                            & (MemoryRelation.target_id == target_memory.id)
                        )
                    )
                )
                if existing.first():
                    continue

                relation = await self._analyze_relation(llm, target_memory, candidate)

                if relation:
                    new_relation = MemoryRelation(
                        source_id=target_memory.id,
                        target_id=candidate.id,
                        relation_type=relation["type"],
                        strength=relation["strength"],
                        description=relation["description"],
                        agent_id=agent_id,
                    )
                    self.session.add(new_relation)
                    await self.session.commit()
                    print(f"[Reflection] 孤独记忆已连接: {relation['description']}")
                    new_relations_count += 1
                    break  # 找到一个连接就够了，脱离孤独状态

        return {"status": "success", "new_relations": new_relations_count}

    async def build_ontology_graph(
        self, limit: int = 20, agent_id: str = "pero"
    ) -> dict:
        """
        [图谱园丁] (Graph Gardener)
        执行原子化清洗与图谱构建任务：
        1. 提取 Event 中的 Raw Tags
        2. 清洗、归一化、晋升为 Entity Node
        3. 建立 Event -> Entity 的连接
        """
        print(
            f"[Reflection] 开始构建本体图谱 (limit={limit}, agent_id={agent_id})...",
            flush=True,
        )

        # 1. 获取最近的未处理 Event (这里简单取最近的 N 条，实际生产中应该记录 cursor)
        statement = (
            select(Memory)
            .where(Memory.type == "event")
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(limit)
        )
        events = (await self.session.exec(statement)).all()

        if not events:
            return {"status": "skipped", "reason": "No events found"}

        # 过滤掉已经有大量关系的 Event (假设它们已经被处理过)
        # 这里为了简化，我们总是重新检查一遍，依靠 LLM 和 DB 唯一性约束来去重

        # 2. 准备 Prompt 数据
        event_data = []
        for e in events:
            event_data.append(
                {
                    "id": e.id,
                    "content": e.content,
                    "raw_tags": e.tags.split(",") if e.tags else [],
                }
            )

        config = await self._get_reflection_config()
        if not config["api_key"]:
            return {"status": "skipped", "reason": "No API Key"}

        llm = LLMService(
            api_key=config["api_key"],
            api_base=config["api_base"],
            model=config["model"],
        )

        prompt = mdp.render(
            "tasks/memory/reflection/graph_builder",
            {"events_json": json.dumps(event_data, ensure_ascii=False)},
        )

        try:
            # 3. 调用反思模型
            response = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=300.0,
                response_format={"type": "json_object"},
            )
            content = response["choices"][0]["message"]["content"]

            # 鲁棒性 JSON 解析
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            graph_updates = json.loads(content)

            # 4. 执行图谱更新 (原子事务)
            new_entities_count = 0
            new_relations_count = 0

            # 4.1 处理新实体 (Nodes)
            entity_map = {}  # name -> id

            for entity in graph_updates.get("new_entities", []):
                name = entity.get("name")
                if not name:
                    continue

                # 检查是否存在
                existing = (
                    await self.session.exec(
                        select(Memory)
                        .where(Memory.type == "entity")
                        .where(Memory.content == name)  # 实体名存入 content
                        .where(Memory.agent_id == agent_id)
                    )
                ).first()

                if existing:
                    entity_map[name] = existing.id
                else:
                    # 创建新实体
                    new_entity = Memory(
                        content=name,
                        type="entity",
                        tags=entity.get("type", "concept"),  # 将实体类型存入 tags
                        source="graph_gardener",
                        agent_id=agent_id,
                        importance=5,  # 实体默认重要性较高
                    )
                    self.session.add(new_entity)
                    await self.session.flush()  # 获取 ID
                    entity_map[name] = new_entity.id
                    new_entities_count += 1

                    # 立即生成向量 (实体的向量只编码名字和类型)
                    try:
                        from services.core.embedding_service import embedding_service
                        from services.core.vector_service import vector_service

                        vec = await embedding_service.encode_one(
                            f"{name} {entity.get('type', '')}"
                        )
                        if vec:
                            vector_service.add_memory(
                                memory_id=new_entity.id,
                                content=new_entity.content,
                                embedding=vec,
                                metadata={
                                    "type": "entity",
                                    "timestamp": new_entity.timestamp,
                                    "agent_id": agent_id,
                                },
                            )
                    except Exception as e:
                        print(f"[GraphGardener] 实体向量生成失败: {e}")

            # 4.2 处理关系 (Edges)
            for rel in graph_updates.get("relations", []):
                event_id = rel.get("event_id")
                entity_name = rel.get("entity")
                rel_type = rel.get("rel", "related")
                weight = rel.get("weight", 0.5)

                if not event_id or not entity_name:
                    continue

                entity_id = entity_map.get(entity_name)
                if not entity_id:
                    # 实体未创建成功，跳过
                    continue

                # 检查重复关系
                existing_rel = (
                    await self.session.exec(
                        select(MemoryRelation).where(
                            (MemoryRelation.source_id == event_id)
                            & (MemoryRelation.target_id == entity_id)
                            & (MemoryRelation.relation_type == rel_type)
                        )
                    )
                ).first()

                if not existing_rel:
                    new_rel = MemoryRelation(
                        source_id=event_id,
                        target_id=entity_id,
                        relation_type=rel_type,
                        strength=weight,
                        agent_id=agent_id,
                    )
                    self.session.add(new_rel)
                    new_relations_count += 1

            await self.session.commit()
            print(
                f"[Reflection] 图谱构建完成: +{new_entities_count} 实体, +{new_relations_count} 关系"
            )

            return {
                "status": "success",
                "new_entities": new_entities_count,
                "new_relations": new_relations_count,
            }

        except Exception as e:
            print(f"[Reflection] 图谱构建失败: {e}")
            import traceback

            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    async def _analyze_relation(
        self, llm: LLMService, m1: Memory, m2: Memory
    ) -> Optional[dict]:
        """让 LLM 分析两条记忆的关系"""
        prompt = mdp.render(
            "tasks/memory/reflection/relation",
            {
                "m1_time": m1.realTime,
                "m1_content": m1.content,
                "m1_tags": m1.tags,
                "m2_time": m2.realTime,
                "m2_content": m2.content,
                "m2_tags": m2.tags,
            },
        )

        try:
            # [Fix] GLM-4 等部分模型不支持 response_format="json_object"，移除该参数以兼容
            # 显式设置超时时间为 300s (5分钟)，防止反思分析超时
            response = await llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.1, timeout=300.0
            )
            content = response["choices"][0]["message"]["content"]

            # 解析 JSON (简单)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content)
            if data.get("has_relation"):
                return data
            return None
        except Exception as e:
            print(f"[Reflection] 分析关联错误: {e}")
            return None

    async def undo_maintenance(self, record_id: int) -> bool:
        """撤销某次维护操作"""
        try:
            record = await self.session.get(MaintenanceRecord, record_id)
            if not record:
                print(f"[Reflection] 找不到维护记录: {record_id}")
                return False

            print(f"[Reflection] 正在撤销维护记录 {record_id}...")

            # 1. 删除本次维护创建的记忆 (Created IDs)
            if record.created_ids:
                created_ids = json.loads(record.created_ids)
                if created_ids:
                    # 批量删除
                    statement = select(Memory).where(col(Memory.id).in_(created_ids))
                    created_memories = (await self.session.exec(statement)).all()

                    for mem in created_memories:
                        await self.session.delete(mem)
                        # 同步删除向量
                        try:
                            from services.core.vector_service import vector_service

                            vector_service.delete_memory(mem.id, agent_id=mem.agent_id)
                        except Exception:
                            pass
                    print(f"[Reflection] 已撤销创建的 {len(created_memories)} 条记忆。")

            # 2. 恢复被修改的记忆 (Modified Data)
            if record.modified_data:
                modified_data = json.loads(record.modified_data)
                count_restored = 0
                for old_state in modified_data:
                    mem_id = old_state.get("id")
                    if not mem_id:
                        continue

                    mem = await self.session.get(Memory, mem_id)
                    if mem:
                        # 恢复关键字段
                        mem.importance = old_state.get("importance", mem.importance)
                        mem.tags = old_state.get("tags", mem.tags)
                        mem.clusters = old_state.get("clusters", mem.clusters)
                        mem.content = old_state.get("content", mem.content)
                        mem.type = old_state.get(
                            "type", mem.type
                        )  # e.g. archived_event -> event

                        self.session.add(mem)

                        # 恢复向量 (重新生成)
                        try:
                            from services.core.embedding_service import (
                                embedding_service,
                            )
                            from services.core.vector_service import vector_service

                            enriched = (
                                f"{mem.tags} {mem.tags} {mem.content}"
                                if mem.tags
                                else mem.content
                            )
                            vec = await embedding_service.encode_one(enriched)
                            if vec:
                                vector_service.add_memory(
                                    memory_id=mem.id,
                                    content=mem.content,
                                    embedding=vec,
                                    metadata={
                                        "type": mem.type,
                                        "timestamp": mem.timestamp,
                                        "importance": float(mem.importance),
                                        "tags": mem.tags,
                                        "agent_id": mem.agent_id,
                                    },
                                )
                        except Exception:
                            pass

                        count_restored += 1
                print(f"[Reflection] 已恢复 {count_restored} 条被修改的记忆。")

            # 3. 恢复被删除的记忆 (Deleted Data)
            if record.deleted_data:
                deleted_data = json.loads(record.deleted_data)
                count_recreated = 0
                for old_mem in deleted_data:
                    # 检查是否已存在 (ID) - 虽然被删了，但为了安全
                    existing = await self.session.get(Memory, old_mem["id"])
                    if not existing:
                        # 重新创建，保持原 ID
                        new_mem = Memory(**old_mem)
                        self.session.add(new_mem)

                        # 恢复向量
                        try:
                            from services.core.embedding_service import (
                                embedding_service,
                            )
                            from services.core.vector_service import vector_service

                            enriched = (
                                f"{new_mem.tags} {new_mem.tags} {new_mem.content}"
                                if new_mem.tags
                                else new_mem.content
                            )
                            vec = await embedding_service.encode_one(enriched)
                            if vec:
                                vector_service.add_memory(
                                    memory_id=new_mem.id,
                                    content=new_mem.content,
                                    embedding=vec,
                                    metadata={
                                        "type": new_mem.type,
                                        "timestamp": new_mem.timestamp,
                                        "importance": float(new_mem.importance),
                                        "tags": new_mem.tags,
                                        "agent_id": new_mem.agent_id,
                                    },
                                )
                        except Exception:
                            pass

                        count_recreated += 1
                print(f"[Reflection] 已恢复 {count_recreated} 条被删除的记忆。")

            # 4. 删除维护记录
            await self.session.delete(record)
            await self.session.commit()
            print("[Reflection] 维护撤销完成。")
            return True

        except Exception as e:
            print(f"[Reflection] 撤销维护失败: {e}")
            import traceback

            traceback.print_exc()
            return False
