import json
import os
from datetime import datetime
from typing import Dict, List, Set, Tuple

from sqlmodel import col, select

from .database import get_social_db_session
from .models_db import QQMessage, SocialDailyReport, SocialMemory

# 引入 TriviumDB 异步适配层，使用独立命名的实例空间
from services.memory.trivium_store import TriviumMemoryStore
from services.core.embedding_service import embedding_service


class SocialMemoryService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SocialMemoryService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 初始化独立的 TriviumDB 向量空间: social_memory.tdb
        self._store = TriviumMemoryStore(store_name="social")
        print("[SocialMemory] 基于 TriviumDB 的独立社交记忆图谱已加载。", flush=True)

    async def initialize(self):
        """初始化社交记忆引擎"""
        print("[SocialMemory] 正在初始化...", flush=True)
        # 以前在 SQLite 里读取所有关系用来灌回 Rust Core，
        # 如果当前 db_path 在 TriviumDB 已经持久化，则无需每次重新加载！
        # 但如果是新创建的数据库，我们可以加一个异步索引重建任务。
        # 暂时只做打印：TriviumDB 负责在后台持久化。
        print(f"[SocialMemory] TriviumDB (social) 已自动恢复，共有 {self._store.count()} 个记忆节点。")

    async def add_summary(
        self,
        content: str,
        keywords: List[str],
        session_id: str,
        session_type: str,
        msg_range: Tuple[int, int] = None,
        agent_id: str = "pero",
    ) -> SocialMemory:
        """
        添加一条新的会话总结，并自动建立关联 (存储到 TriviumDB)
        """
        # 1. 尝试生成向量 Embedding
        vec = []
        try:
            vec = await embedding_service.encode_one(content)
        except Exception as e:
            print(f"[SocialMemory] 警告: 生成 Embedding 失败: {e}")

        # 2. 保存到数据库 (基础信息)
        async for session in get_social_db_session():
            memory = SocialMemory(
                content=content,
                keywords=",".join(keywords),
                source_session_id=str(session_id),
                source_session_type=session_type,
                embedding_json=json.dumps(vec), # 暂时保留 JSON 用于后备兼容
                msg_start_id=msg_range[0] if msg_range else None,
                msg_end_id=msg_range[1] if msg_range else None,
                agent_id=agent_id,
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)

            # 3. 放入 TriviumDB (包含文本和标签的混合索引)
            payload = {
                "source_session_id": memory.source_session_id,
                "source_session_type": memory.source_session_type,
                "created_at": memory.created_at.timestamp(),
                "agent_id": memory.agent_id,
                "content": memory.content,  # 建立文本搜索索引
                "clusters": memory.keywords  # 建立关键词聚类索引
            }
            try:
                # 放入独立空间
                await self._store.insert(memory.id, vec, payload)
                
                # 同步更新关系的旧表逻辑 (P2之后会移除，目前保留兼容查询如果需要)
                # 后续可以用 self._store.link() 代替。
            except Exception as e:
                print(f"[SocialMemory] TriviumDB 插入失败: {e}")

            return memory

    async def search_memories(
        self, query: str, agent_id: str = "pero", limit: int = 5
    ) -> List[SocialMemory]:
        """
        搜索记忆（向量 + 文本混合检索，并附带 TriviumDB FISTA/图扩散）
        """
        # 尝试获取 Query Vector
        query_vec = []
        try:
            query_vec = await embedding_service.encode_one(query)
        except Exception:
            # 防止空向量报错
            query_vec = [0.0] * 384
            
        try:
            # 利用 TriviumDB 内置的图谱深度扩散 + 文本混合检索
            hits = await self._store.search(
                query_vector=query_vec,
                top_k=limit,
                expand_depth=2,          # 图谱扩散深度
                agent_id=agent_id,       # payload 空间隔离
                query_text=query,        # 引入混合关键字
                enable_dpp=True,         # 多样性采样
                enable_text_hybrid=True, # 开启混合
            )
            
            if not hits:
                return []
                
            activated_ids = [int(hit["id"]) for hit in hits]
            
            # 查库返回实体
            async for session in get_social_db_session():
                statement = (
                    select(SocialMemory)
                    .where(col(SocialMemory.id).in_(activated_ids))
                    .where(SocialMemory.agent_id == agent_id)
                )
                memories = (await session.exec(statement)).all()
                # 按照 hit 得分排序返回
                memories_dict = {m.id: m for m in memories}
                ordered_memories = [memories_dict[mid] for mid in activated_ids if mid in memories_dict]
                return ordered_memories
                
        except Exception as e:
            print(f"[SocialMemory] Trivium 搜索失败: {e}")
            return []

    async def retrieve_context(
        self, query: str, current_session_id: str, agent_id: str = "pero"
    ) -> str:
        """
        检索上下文：混合检索 -> 结果合并
        """
        memories = await self.search_memories(query, agent_id, limit=5)

        if not memories:
            return ""

        result = "【相关记忆回忆】:\n"
        for mem in memories:
            source_label = (
                "私聊"
                if mem.source_session_type == "private"
                else f"群{mem.source_session_id}"
            )
            result += f"- [{source_label}] {mem.content}\n"

        return result

    async def generate_daily_report(self, date_str: str = None, agent_id: str = "pero"):
        """生成并保存社交日报"""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        import os
        from utils.workspace_utils import get_workspace_root

        agent_workspace = get_workspace_root(agent_id)
        report_dir = os.path.join(agent_workspace, "social_reports")
        os.makedirs(report_dir, exist_ok=True)
        file_path = os.path.join(report_dir, f"{date_str}.md")

        if os.path.exists(file_path):
            print(f"[SocialMemory] 日报已存在: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return SocialDailyReport(
                    date_str=date_str, content=content, agent_id=agent_id
                )
            except Exception:
                pass

        async for session in get_social_db_session():
            start_dt = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(f"{date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")

            count_stmt = select(col(QQMessage.id)).where(
                col(QQMessage.timestamp) >= start_dt,
                col(QQMessage.timestamp) <= end_dt,
                QQMessage.agent_id == agent_id,
            )
            total_messages = len((await session.exec(count_stmt)).all())

            group_stmt = (
                select(QQMessage.session_id)
                .where(
                    col(QQMessage.timestamp) >= start_dt,
                    col(QQMessage.timestamp) <= end_dt,
                    QQMessage.session_type == "group",
                    QQMessage.agent_id == agent_id,
                )
                .distinct()
            )
            active_groups = (await session.exec(group_stmt)).all()
            new_friends = 0

            mem_stmt = select(SocialMemory).where(
                col(SocialMemory.created_at) >= start_dt,
                col(SocialMemory.created_at) <= end_dt,
                SocialMemory.agent_id == agent_id,
            )
            daily_memories = (await session.exec(mem_stmt)).all()

            summary_content = "今日无重要记忆。"
            if daily_memories:
                summary_content = "\n".join([f"- {m.content}" for m in daily_memories])

            try:
                from core.config_manager import get_config_manager
                config = get_config_manager()
                bot_name = config.get("bot_name", "Pero")
            except Exception:
                bot_name = "Pero"

            from services.mdp.manager import mdp
            report_prompt = mdp.render(
                "social/reporting/daily_report_generator",
                {
                    "agent_name": bot_name,
                    "date_str": date_str,
                    "total_messages": total_messages,
                    "active_groups_count": len(active_groups),
                    "summary_content": summary_content,
                },
            )

            from services.core.llm_service import llm_service
            report_text = await llm_service.chat_completion(
                messages=[{"role": "user", "content": report_prompt}], temperature=0.7
            )

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(report_text)
                print(f"[SocialMemory] 日报文件已保存: {file_path}")
            except Exception as e:
                print(f"[SocialMemory] 保存日报文件失败: {e}")

            report = SocialDailyReport(
                date_str=date_str,
                content=report_text,
                total_messages=total_messages,
                active_groups=",".join([str(g) for g in active_groups]),
                new_friends=new_friends,
                agent_id=agent_id,
            )

            print(f"[SocialMemory] 已生成 {date_str} 的日报 (仅文件)")
            return report


def get_social_memory_service():
    return SocialMemoryService()
