import json
import os
from datetime import datetime
from typing import Dict, List, Set, Tuple

from sqlmodel import col, select

from .database import get_social_db_session
from .models_db import QQMessage, SocialDailyReport, SocialMemory, SocialMemoryRelation

# 独立的向量服务（社交专用）
# 暂时复用 embedding_service，未来可迁移至独立索引
# 假设有一个独立的 social_vector_store 目录


class SocialMemoryService:
    _instance = None
    _rust_engine = None
    _social_engine = None  # PEDSA 社交核心引擎

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SocialMemoryService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.vector_store_path = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
            "data",
            "social_vector_store",
        )
        # 确保目录存在
        os.makedirs(self.vector_store_path, exist_ok=True)

        # 内存中的关键词索引 (Keyword -> List[MemoryID])
        self.keyword_index: Dict[str, Set[int]] = {}

        # 初始化 PEDSA 社交核心
        try:
            from pero_social_core import SocialMemoryEngine

            self._social_engine = SocialMemoryEngine()
            print("[SocialMemory] PEDSA Social Core (Rust) 已加载。", flush=True)
        except ImportError:
            print(
                "[SocialMemory] 未找到 pero_social_core，将使用降级模式。", flush=True
            )
            self._social_engine = None

    async def initialize(self):
        """初始化 Rust 引擎和加载索引"""
        print("[SocialMemory] 正在初始化...", flush=True)
        await self._init_rust_engine()
        await self._load_keyword_index()
        await self._load_pedsa_engine()

    async def _load_pedsa_engine(self):
        """加载数据到 PEDSA 社交引擎"""
        if not self._social_engine:
            return

        print("[SocialMemory] 正在向 PEDSA 引擎注入记忆...", flush=True)
        count = 0
        async for session in get_social_db_session():
            statement = select(SocialMemory)
            memories = (await session.exec(statement)).all()
            for mem in memories:
                try:
                    vec = json.loads(mem.embedding_json) if mem.embedding_json else []
                    ts = int(mem.created_at.timestamp())
                    kws = [k.strip() for k in mem.keywords.split(",") if k.strip()]
                    # 确保 vector 是 float list
                    vec = [float(x) for x in vec]
                    self._social_engine.add_memory(mem.id, mem.content, ts, vec, kws)
                    count += 1
                except Exception as e:
                    print(f"[SocialMemory] 加载记忆 {mem.id} 失败: {e}")
        print(f"[SocialMemory] PEDSA 引擎加载完成，共 {count} 条记忆。", flush=True)

    async def _init_rust_engine(self):
        """初始化独立的 Rust 认知引擎"""
        try:
            from pero_memory_core import CognitiveGraphEngine

            self._rust_engine = CognitiveGraphEngine()
            self._rust_engine.configure(max_active_nodes=5000, max_fan_out=15)

            total_relations = 0
            # 加载现有关系
            async for session in get_social_db_session():
                statement = select(SocialMemoryRelation)
                relations = (await session.exec(statement)).all()
                if relations:
                    total_relations += len(relations)
                    chunk_relations = [
                        (int(rel.source_id), int(rel.target_id), float(rel.strength), 0)
                        for rel in relations
                    ]
                    self._rust_engine.batch_add_connections(chunk_relations)

            print(
                f"[SocialMemory] Rust 引擎已初始化，包含 {total_relations} 个连接。",
                flush=True,
            )
        except Exception as e:
            print(f"[SocialMemory] 初始化 Rust 引擎失败: {e}")
            self._rust_engine = None

    async def _load_keyword_index(self):
        """加载关键词索引到内存"""
        async for session in get_social_db_session():
            statement = select(SocialMemory.id, SocialMemory.keywords)
            results = (await session.exec(statement)).all()
            for mid, kw_str in results:
                if kw_str:
                    for kw in kw_str.split(","):
                        kw = kw.strip()
                        if kw:
                            if kw not in self.keyword_index:
                                self.keyword_index[kw] = set()
                            self.keyword_index[kw].add(mid)

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
        添加一条新的会话总结，并自动建立关联
        """
        # 1. 保存到数据库
        async for session in get_social_db_session():
            # Embedding（调用核心的 EmbeddingService）
            vec = []
            try:
                from services.core.embedding_service import embedding_service

                vec = await embedding_service.encode_one(content)
            except Exception as e:
                print(f"[SocialMemory] 警告: 生成 Embedding 失败: {e}")

            memory = SocialMemory(
                content=content,
                keywords=",".join(keywords),
                source_session_id=str(session_id),
                source_session_type=session_type,
                embedding_json=json.dumps(vec),
                msg_start_id=msg_range[0] if msg_range else None,
                msg_end_id=msg_range[1] if msg_range else None,
                agent_id=agent_id,
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)

            # 2. 自动串线（Auto-Linking）
            related_ids = set()
            for kw in keywords:
                kw = kw.strip()
                if not kw:
                    continue

                # 更新内存索引
                if kw not in self.keyword_index:
                    self.keyword_index[kw] = set()

                # 查找现有 ID
                existing_ids = self.keyword_index[kw]
                related_ids.update(existing_ids)

                # 将自己加入索引
                self.keyword_index[kw].add(memory.id)

            # 建立关联
            new_relations = []
            for rid in related_ids:
                if rid == memory.id:
                    continue

                # 创建双向关联
                # 新 -> 旧
                rel1 = SocialMemoryRelation(
                    source_id=memory.id,
                    target_id=rid,
                    relation_type="thematic",
                    strength=0.8,
                )
                session.add(rel1)
                new_relations.append((memory.id, rid, 0.8))

                # 旧 -> 新
                rel2 = SocialMemoryRelation(
                    source_id=rid,
                    target_id=memory.id,
                    relation_type="thematic",
                    strength=0.8,
                )
                session.add(rel2)
                new_relations.append((rid, memory.id, 0.8))

            await session.commit()

            # 3. 更新 Rust 引擎
            if self._rust_engine and new_relations:
                self._rust_engine.batch_add_connections(new_relations)

            # 4. 更新 PEDSA 社交引擎
            if self._social_engine:
                try:
                    ts = int(memory.created_at.timestamp())
                    # vec 已在上方计算为 vec
                    vec_float = [float(x) for x in vec]
                    kws = [k.strip() for k in keywords if k.strip()]
                    self._social_engine.add_memory(
                        memory.id, memory.content, ts, vec_float, kws
                    )
                except Exception as e:
                    print(f"[SocialMemory] PEDSA 添加失败: {e}")

            return memory

    async def search_memories(
        self, query: str, agent_id: str = "pero", limit: int = 5
    ) -> List[SocialMemory]:
        """
        搜索记忆（PEDSA + 扩散），返回 Memory 对象列表
        """
        entry_points = set()

        # 1. PEDSA 混合检索 (优先)
        if self._social_engine:
            try:
                ref_time = int(datetime.now().timestamp())
                # 尝试获取 Query Vector
                query_vec = None
                try:
                    from services.core.embedding_service import embedding_service

                    query_vec = await embedding_service.encode_one(query)
                except Exception:
                    pass

                # 搜索前 20 条
                results = self._social_engine.search(query, ref_time, 20, query_vec)
                entry_points.update([mid for mid, score in results])
            except Exception as e:
                print(f"[SocialMemory] PEDSA 检索失败: {e}")

        # 2. 传统关键词匹配 (补充)
        if not entry_points:
            for kw, mids in self.keyword_index.items():
                if kw in query:
                    entry_points.update(mids)

        if not entry_points:
            return []

        # 3. 扩散激活 (Cognitive Graph Diffusion)
        activated_ids = set(entry_points)
        if self._rust_engine:
            try:
                entry_point_ids = [int(mid) for mid in entry_points]
                spread_result = self._rust_engine.spread(entry_point_ids, 2, 0.5)
                activated_ids = set(spread_result.keys())
            except Exception as e:
                print(f"[SocialMemory] Rust 引擎扩散激活失败: {e}")
                pass

        # 4. 读取内容
        if not activated_ids:
            return []

        async for session in get_social_db_session():
            statement = (
                select(SocialMemory)
                .where(col(SocialMemory.id).in_(activated_ids))
                .where(SocialMemory.agent_id == agent_id)
                .limit(limit)
            )
            return (await session.exec(statement)).all()
        return []

    async def retrieve_context(
        self, query: str, current_session_id: str, agent_id: str = "pero"
    ) -> str:
        """
        检索上下文：PEDSA 混合检索 -> Rust 引擎扩散激活
        """
        memories = await self.search_memories(query, agent_id, limit=5)

        if not memories:
            return ""

        # 过滤：优先显示非当前会话的记忆
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

        # [修改] 优先检查文件
        import os

        from utils.workspace_utils import get_workspace_root

        agent_workspace = get_workspace_root(agent_id)
        report_dir = os.path.join(agent_workspace, "social_reports")
        os.makedirs(report_dir, exist_ok=True)
        file_path = os.path.join(report_dir, f"{date_str}.md")

        if os.path.exists(file_path):
            print(f"[SocialMemory] 日报已存在: {file_path}")
            # 读取并返回模拟对象
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return SocialDailyReport(
                    date_str=date_str, content=content, agent_id=agent_id
                )
            except Exception:
                pass

        async for session in get_social_db_session():
            # 1. (已移除 DB 检查)

            # 2. 统计当日消息
            start_dt = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(f"{date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")

            # 消息总数
            count_stmt = select(col(QQMessage.id)).where(
                col(QQMessage.timestamp) >= start_dt,
                col(QQMessage.timestamp) <= end_dt,
                QQMessage.agent_id == agent_id,
            )
            total_messages = len((await session.exec(count_stmt)).all())

            # 活跃群组
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

            # 新加好友（模拟）
            new_friends = 0

            # 3. 汇总当日生成的记忆总结
            mem_stmt = select(SocialMemory).where(
                col(SocialMemory.created_at) >= start_dt,
                col(SocialMemory.created_at) <= end_dt,
                SocialMemory.agent_id == agent_id,
            )
            daily_memories = (await session.exec(mem_stmt)).all()

            summary_content = "今日无重要记忆。"
            if daily_memories:
                summary_content = "\n".join([f"- {m.content}" for m in daily_memories])

            # 4. 生成日报内容（LLM）
            try:
                from core.config_manager import get_config_manager

                config = get_config_manager()
                bot_name = config.get("bot_name", "Pero")
            except Exception:
                bot_name = "Pero"

            # 获取 Agent 配置文件以进行动态角色注入
            from services.agent.agent_manager import AgentManager

            agent_manager = AgentManager()
            agent_manager.agents.get(agent_id)

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

            # 保存报告
            # [修改] 只保存到文件
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(report_text)
                print(f"[SocialMemory] 日报文件已保存: {file_path}")
            except Exception as e:
                print(f"[SocialMemory] 保存日报文件失败: {e}")

            # 构造返回对象但不入库
            report = SocialDailyReport(
                date_str=date_str,
                content=report_text,
                total_messages=total_messages,
                active_groups=",".join([str(g) for g in active_groups]),
                new_friends=new_friends,
                agent_id=agent_id,
            )
            # session.add(report)
            # await session.commit()

            print(f"[SocialMemory] 已生成 {date_str} 的日报 (仅文件)")
            return report


def get_social_memory_service():
    return SocialMemoryService()
