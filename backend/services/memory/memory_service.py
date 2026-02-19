import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import delete, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import ConversationLog, Memory, MemoryRelation

# [Global] Rust 引擎单例 (PEDSA 算法核心)
_rust_engine = None

RELATION_TYPE_MAP = {
    "associative": 0,
    "is_instance_of": 1,
    "inhibits": 255,
    "causes": 2,
    "involves": 0,
    "mentions": 0,
    "expresses": 0,
}


async def get_rust_engine(session: AsyncSession):
    global _rust_engine
    if _rust_engine is not None:
        return _rust_engine

    try:
        from pero_memory_core import CognitiveGraphEngine

        print("[Memory] 初始化 Rust 图遍历引擎...", flush=True)
        _rust_engine = CognitiveGraphEngine()
        _rust_engine.configure(max_active_nodes=10000, max_fan_out=20)

        # 预加载关系 (分批)
        BATCH_SIZE = 5000
        total_loaded = 0

        # 1. 加载 MemoryRelation
        mr_offset = 0
        while True:
            statement = select(MemoryRelation).offset(mr_offset).limit(BATCH_SIZE)
            relations = (await session.exec(statement)).all()
            if not relations:
                break

            chunk_relations = []
            for rel in relations:
                type_id = RELATION_TYPE_MAP.get(rel.relation_type, 0)
                chunk_relations.append(
                    (rel.source_id, rel.target_id, rel.strength, type_id)
                )

            _rust_engine.batch_add_connections(chunk_relations)
            total_loaded += len(relations)
            mr_offset += BATCH_SIZE

        # 2. 加载时间链表关系
        mem_offset = 0
        while True:
            statement_mem = (
                select(Memory.id, Memory.prev_id, Memory.next_id)
                .where((Memory.prev_id != None) | (Memory.next_id != None))  # noqa: E711
                .offset(mem_offset)
                .limit(BATCH_SIZE)
            )
            mem_links = (await session.exec(statement_mem)).all()
            if not mem_links:
                break

            chunk_links = []
            for mid, prev_id, next_id in mem_links:
                # 时间关系默认类型为 0 (associative)
                if prev_id:
                    chunk_links.append((mid, prev_id, 0.2, 0))
                if next_id:
                    chunk_links.append((mid, next_id, 0.2, 0))

            if chunk_links:
                _rust_engine.batch_add_connections(chunk_links)
                total_loaded += len(chunk_links)
            mem_offset += BATCH_SIZE

        print(f"[Memory] Rust 引擎已加载 {total_loaded} 个连接。", flush=True)
    except Exception as e:
        print(f"[Memory] Rust 引擎初始化失败: {e}")
        _rust_engine = False

    return _rust_engine


class MemoryService:
    @staticmethod
    async def save_memory(
        session: AsyncSession,
        content: str,
        tags: str = "",
        clusters: str = "",  # 新增 clusters 参数
        importance: int = 1,
        base_importance: float = 1.0,
        sentiment: str = "neutral",
        msg_timestamp: Optional[str] = None,
        source: str = "desktop",
        memory_type: str = "event",
        agent_id: str = "pero",  # 多 Agent 隔离
    ) -> Optional[Memory]:
        from datetime import datetime

        from sqlmodel import desc

        from core.event_bus import EventBus
        from services.core.embedding_service import embedding_service
        from services.core.vector_service import vector_service

        # [Hook] memory.save.pre
        # 允许 MOD 修改参数或取消保存
        ctx = {
            "session": session,
            "content": content,
            "tags": tags,
            "clusters": clusters,
            "importance": importance,
            "base_importance": base_importance,
            "sentiment": sentiment,
            "msg_timestamp": msg_timestamp,
            "source": source,
            "memory_type": memory_type,
            "agent_id": agent_id,
            "cancel": False,
        }
        await EventBus.publish("memory.save.pre", ctx)

        if ctx.get("cancel"):
            print("[MemoryService] memory.save.pre 钩子取消了保存操作。")
            return None

        # 从上下文更新变量 (允许 MOD 修改)
        content = ctx["content"]
        tags = ctx["tags"]
        clusters = ctx["clusters"]
        importance = ctx["importance"]
        base_importance = ctx["base_importance"]
        sentiment = ctx["sentiment"]
        msg_timestamp = ctx["msg_timestamp"]
        source = ctx["source"]
        memory_type = ctx["memory_type"]
        agent_id = ctx["agent_id"]

        # 1. 查找上一条记忆 (时间轴末尾)
        # 增加 agent_id 过滤，确保只链接到同一个 Agent 的记忆链
        statement = (
            select(Memory)
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(1)
        )
        last_memory_result = await session.exec(statement)
        last_memory = last_memory_result.first()

        prev_id = last_memory.id if last_memory else None

        # 2. 创建新记忆
        # 生成 Embedding (用于写入 VectorDB)
        embedding_vec = embedding_service.encode_one(content)

        if not embedding_vec:
            print(f"[MemoryService] 警告: 记忆内容嵌入生成失败: {content[:30]}...")

        embedding_json = json.dumps(embedding_vec)

        memory = Memory(
            content=content,
            tags=tags,
            clusters=clusters,
            importance=importance,
            base_importance=base_importance,
            sentiment=sentiment,
            msgTimestamp=msg_timestamp,
            realTime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source=source,
            type=memory_type,
            prev_id=prev_id,
            next_id=None,
            embedding_json=embedding_json,  # 保留 SQLite 备份
            agent_id=agent_id,
        )
        session.add(memory)
        await session.commit()
        await session.refresh(memory)

        # 3. 同步写入 VectorDB
        if embedding_vec:
            try:
                # [Feature] 标签加权向量
                # 如果有 tags，生成混合文本 "tags tags content" 增强权重
                final_embedding = embedding_vec
                if tags:
                    enriched_text = f"{tags} {tags} {content}"
                    final_embedding = embedding_service.encode_one(enriched_text)

                    # [Feature] TagMemo Indexing - 独立索引标签
                    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                    if tag_list:
                        try:
                            tag_embeddings = embedding_service.encode(tag_list)
                            for i, tag_name in enumerate(tag_list):
                                vector_service.add_tag(tag_name, tag_embeddings[i])
                        except Exception as tag_e:
                            print(f"[MemoryService] 索引标签失败: {tag_e}")

                # 构建元数据
                metadata_dict = {
                    "type": memory_type,
                    "timestamp": memory.timestamp,
                    "importance": float(importance),
                    "tags": tags,
                    "clusters": clusters,
                    "agent_id": agent_id,
                }

                # [Feature] 簇过滤支持
                if clusters:
                    cluster_list = [c.strip() for c in clusters.split(",") if c.strip()]
                    for c in cluster_list:
                        clean_c = c.replace("[", "").replace("]", "")
                        if clean_c:
                            metadata_dict[f"cluster_{clean_c}"] = True

                vector_service.add_memory(
                    memory_id=memory.id,
                    content=content,
                    embedding=final_embedding,
                    metadata=metadata_dict,
                )
            except Exception as e:
                print(f"[MemoryService] 同步到 VectorDB 失败: {e}")
        else:
            # Embedding 为空时的同步重试策略
            print(
                f"[MemoryService] Embedding 为空，正在对 Memory ID {memory.id} 进行同步重试..."
            )
            try:
                # 强制重新加载模型并编码
                retry_vec = embedding_service.encode_one(content)
                if retry_vec:
                    # 更新 SQL
                    memory.embedding_json = json.dumps(retry_vec)
                    session.add(memory)
                    await session.commit()

                    # 写入 VectorDB
                    vector_service.add_memory(
                        memory_id=memory.id,
                        content=content,
                        embedding=retry_vec,
                        metadata={
                            "type": memory_type,
                            "timestamp": memory.timestamp,
                            "importance": float(importance),
                            "tags": tags,
                            "clusters": clusters,
                            "agent_id": agent_id,
                        },
                    )
                    print(f"[MemoryService] Memory ID {memory.id} 重试成功。")
                else:
                    print(
                        f"[MemoryService] 严重错误: 重试失败。Memory {memory.id} 已存储但无向量索引。"
                    )
            except Exception as retry_e:
                print(f"[MemoryService] 重试异常: {retry_e}")

        # 4. 更新上一条记忆的 next_id (双向链表维护)
        if last_memory:
            last_memory.next_id = memory.id
            session.add(last_memory)
            await session.commit()

            # [Optimization] 同步更新全局 Rust 引擎单例
            try:
                engine = await get_rust_engine(session)
                if engine:
                    # 添加 prev/next 双向链接权重 (type=0)
                    engine.batch_add_connections(
                        [
                            (memory.id, last_memory.id, 0.2, 0),
                            (last_memory.id, memory.id, 0.2, 0),
                        ]
                    )
            except Exception:
                pass

        # [Hook] memory.save.post
        await EventBus.publish("memory.save.post", memory)

        return memory

    @staticmethod
    async def save_log(
        session: AsyncSession,
        source: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict = None,
        pair_id: str = None,
        raw_content: str = None,
        agent_id: str = "pero",
    ) -> ConversationLog:
        """保存原始对话记录到 ConversationLog"""
        # 1. 移除 NIT 协议标记 (Non-invasive Integration Tools)
        from nit_core.dispatcher import remove_nit_tags

        cleaned_content = remove_nit_tags(content)

        # 2. 清洗大数据量技术标签 (FILE_RESULTS, MEMORY_LIST 等)
        big_data_tags = ["FILE_RESULTS", "MEMORY_LIST", "SEARCH_RESULTS"]
        for tag in big_data_tags:
            pattern = rf"<{tag}>([\s\S]{{1000,}}?)</{tag}>"
            cleaned_content = re.sub(
                pattern, f"<{tag}>[已折叠大数据量内容]</{tag}>", cleaned_content
            )

        log = ConversationLog(
            source=source,
            session_id=session_id,
            role=role,
            content=cleaned_content,
            raw_content=raw_content,  # 保存原始内容
            metadata_json=json.dumps(metadata or {}),
            pair_id=pair_id,
            agent_id=agent_id,
        )
        session.add(log)
        # 注意：这里去掉了 commit()，改为由外部或 save_log_pair 统一控制
        return log

    @staticmethod
    async def save_log_pair(
        session: AsyncSession,
        source: str,
        session_id: str,
        user_content: str,
        assistant_content: str,
        pair_id: str,
        metadata: dict = None,
        assistant_raw_content: str = None,
        agent_id: str = "pero",
        user_metadata: dict = None,
    ):
        """原子性保存用户消息与助手回复成对记录"""
        try:
            # [Feature] 系统触发角色修正
            user_role = "user"
            if user_content and user_content.startswith("【系统触发】"):
                user_role = "system"

            # 如果提供 user_metadata 则使用，否则回退到 metadata (共享)
            u_meta = user_metadata if user_metadata is not None else metadata

            # 创建用户消息记录
            user_log = await MemoryService.save_log(
                session,
                source,
                session_id,
                user_role,
                user_content,
                u_meta,
                pair_id,
                agent_id=agent_id,
            )
            # 创建助手消息记录
            assistant_log = await MemoryService.save_log(
                session,
                source,
                session_id,
                "assistant",
                assistant_content,
                metadata,
                pair_id,
                raw_content=assistant_raw_content,
                agent_id=agent_id,
            )

            await session.commit()
            await session.refresh(user_log)
            await session.refresh(assistant_log)

            # [Feature] 向 Gateway 广播新消息 (事件驱动)
            try:
                import time
                import uuid

                from peroproto import perolink_pb2
                from services.core.gateway_client import gateway_client

                async def broadcast_log(log):
                    # [Privacy] 不要向全局仪表板广播社交模式日志
                    if log.source == "social":
                        return

                    envelope = perolink_pb2.Envelope()
                    envelope.id = str(uuid.uuid4())
                    envelope.source_id = "memory_service"
                    envelope.target_id = "broadcast"
                    envelope.timestamp = int(time.time() * 1000)

                    envelope.request.action_name = "new_message"
                    envelope.request.params["id"] = str(log.id)
                    envelope.request.params["role"] = log.role
                    envelope.request.params["content"] = log.content
                    envelope.request.params["timestamp"] = (
                        log.timestamp.isoformat() if log.timestamp else ""
                    )
                    envelope.request.params["agent_id"] = log.agent_id or ""
                    envelope.request.params["session_id"] = log.session_id or ""
                    envelope.request.params["pair_id"] = log.pair_id or ""
                    envelope.request.params["metadata"] = log.metadata_json or "{}"

                    await gateway_client.send(envelope)

                await broadcast_log(user_log)
                await broadcast_log(assistant_log)
            except Exception as e:
                print(f"[MemoryService] 广播失败: {e}")

            return user_log, assistant_log
        except Exception as e:
            await session.rollback()
            print(f"[MemoryService] 保存日志对失败: {e}")
            raise e

    @staticmethod
    async def query_logs(
        session: AsyncSession,
        source: str = "all",
        session_id: str = "all",
        limit: int = 20,
        offset: int = 0,
        date_str: str = None,
        sort: str = "asc",
        agent_id: str = "pero",
        before_id: Optional[int] = None,
        query: Optional[str] = None,
    ) -> List[ConversationLog]:
        """
        查询对话日志的统一接口（列表、过滤、搜索）。
        结合了之前 get_recent_logs 和 search_logs 的功能。
        """
        from datetime import datetime, time

        from sqlmodel import desc

        statement = select(ConversationLog).where(ConversationLog.agent_id == agent_id)

        # 1. 来源过滤
        if source != "all":
            if "%" in source:  # 支持来自旧 search_logs 的通配符
                statement = statement.where(ConversationLog.source.like(source))
                # [Privacy] 即使使用通配符（如 '%'），除非明确指定，否则排除社交日志
                if not source.startswith("social"):
                    statement = statement.where(ConversationLog.source != "social")
            else:
                statement = statement.where(ConversationLog.source == source)
        else:
            # [Privacy] 默认排除 'all' 来源
            # 除非明确请求，否则排除 'social'
            statement = statement.where(ConversationLog.source != "social")

        # 2. 会话过滤
        if session_id != "all":
            statement = statement.where(ConversationLog.session_id == session_id)
        else:
            # [降噪] 列出全局历史记录（所有会话）时，
            # 排除临时的 'work_' 会话以保持视图整洁。
            # （除非明确搜索它们，但通常通过特定 ID 访问）
            statement = statement.where(~ConversationLog.session_id.startswith("work_"))

        # 3. 内容搜索
        if query:
            statement = statement.where(ConversationLog.content.contains(query))

        # 4. 游标分页
        if before_id:
            statement = statement.where(ConversationLog.id < before_id)

        # 5. 日期过滤
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                start_dt = datetime.combine(target_date, time.min)
                end_dt = datetime.combine(target_date, time.max)
                statement = statement.where(
                    ConversationLog.timestamp >= start_dt
                ).where(ConversationLog.timestamp <= end_dt)
            except ValueError:
                print(f"[MemoryService] Invalid date format: {date_str}")

        # 6. 排序
        # 始终首先按时间戳倒序排列以获取“最近”日志。
        statement = statement.order_by(
            desc(ConversationLog.timestamp), desc(ConversationLog.id)
        )

        # 7. 分页
        statement = statement.offset(offset).limit(limit)

        logs = (await session.exec(statement)).all()

        # 8. 后处理
        # 如果 sort='asc'，我们需要按时间顺序（旧 -> 新）
        # 但我们获取的是最新日志（新 -> 旧）。
        # 所以我们反转列表。
        if sort == "asc":
            return list(reversed(logs))

        # 如果 sort='desc'，我们需要按时间倒序（新 -> 旧）
        # 这正是我们获取的。
        return list(logs)

    @staticmethod
    async def delete_log(session: AsyncSession, log_id: int):
        """删除指定的对话记录 (如果属于成对记录，则成对删除)"""
        log = await session.get(ConversationLog, log_id)
        if not log:
            return

        if log.pair_id:
            # 如果有 pair_id，删除该组内的所有记录
            statement = delete(ConversationLog).where(
                ConversationLog.pair_id == log.pair_id
            )
        else:
            # 否则仅删除单条
            statement = delete(ConversationLog).where(ConversationLog.id == log_id)

        await session.exec(statement)
        await session.commit()

    @staticmethod
    async def update_log(
        session: AsyncSession, log_id: int, content: str
    ) -> Optional[ConversationLog]:
        """更新指定的对话记录内容"""
        log = await session.get(ConversationLog, log_id)
        if log:
            log.content = content
            session.add(log)
            await session.commit()
            await session.refresh(log)
        return log

    @staticmethod
    async def delete_by_msg_timestamp(session: AsyncSession, msg_timestamp: str):
        statement = delete(Memory).where(Memory.msgTimestamp == msg_timestamp)
        await session.exec(statement)
        await session.commit()

    @staticmethod
    async def mark_memories_accessed(session: AsyncSession, memories: List[Memory]):
        """
        [Reinforcement]
        标记记忆被访问，增加 access_count 并小幅提升 base_importance
        """
        from datetime import datetime

        if not memories:
            return

        for m in memories:
            if m.access_count is None:
                m.access_count = 0
            m.access_count += 1
            m.last_accessed = datetime.now()
            # 每次访问提升 0.1，上限 10.0
            if m.base_importance < 10.0:
                m.base_importance = min(10.0, m.base_importance + 0.1)
                m.importance = int(m.base_importance)  # 同步整数 importance
            session.add(m)

        try:
            await session.commit()
        except Exception as e:
            print(f"[MemoryService] 更新访问统计失败: {e}")

    @staticmethod
    async def logical_flashback(
        session: AsyncSession, text: str, limit: int = 5, agent_id: str = "pero"
    ) -> List[Dict[str, Any]]:
        """
        [Brain-Net Flashback] 基于关键词的图谱联想
        """
        if not text or len(text.strip()) < 2:
            return []

        from services.core.embedding_service import embedding_service
        from services.core.vector_service import vector_service

        try:
            # 1. 向量搜索获取锚点
            query_vec = embedding_service.encode_one(text)
            if not query_vec:
                return []

            vector_results = vector_service.search(
                query_vec, limit=10, agent_id=agent_id
            )
            if not vector_results:
                return []

            anchor_ids = [res["id"] for res in vector_results]
            sim_map = {res["id"]: res["score"] for res in vector_results}

            # 2. 关联检索
            activation_scores = {aid: sim_map.get(aid, 0.5) for aid in anchor_ids}

            engine = await get_rust_engine(session)
            if engine:
                flashback_scores = engine.propagate_activation(
                    activation_scores, steps=2, decay=0.7, min_threshold=0.05
                )
            else:
                flashback_scores = activation_scores

            # 3. 提取关联结果 (排除锚点)
            associated_ids = [mid for mid in flashback_scores if mid not in anchor_ids]
            if not associated_ids:
                associated_ids = anchor_ids

            sorted_ids = sorted(
                associated_ids, key=lambda x: flashback_scores.get(x, 0), reverse=True
            )[:limit]

            if not sorted_ids:
                return []

            # 获取详情
            statement = (
                select(Memory)
                .where(Memory.id.in_(sorted_ids))
                .where(Memory.agent_id == agent_id)
            )
            memories = (await session.exec(statement)).all()

            # 转换为碎片格式
            results = []
            seen_tags = set()
            for m in memories:
                if m.tags:
                    tags = [t.strip() for t in m.tags.split(",") if t.strip()]
                    for tag in tags:
                        if tag not in seen_tags:
                            results.append({"id": m.id, "name": tag, "type": "tag"})
                            seen_tags.add(tag)

                if len(results) < limit:
                    summary = (
                        m.content[:20] + "..." if len(m.content) > 20 else m.content
                    )
                    results.append({"id": m.id, "name": summary, "type": "memory"})

            return results[:limit]

        except Exception as e:
            print(f"[Memory] 逻辑闪回异常: {e}")
            return []

    @staticmethod
    async def get_relevant_memories(
        session: AsyncSession,
        text: str,
        limit: int = 5,
        query_vec: Optional[List[float]] = None,
        exclude_after_time: Optional[datetime] = None,
        update_access_stats: bool = True,
        agent_id: str = "pero",
    ) -> List[Memory]:
        """
        [混合检索策略] (Hybrid Search Strategy)
        1. 锚点定位 (Anchoring): 使用关键词/Tag 命中 Entity Node
        2. 扩散激活 (Diffusion): 利用 Rust 引擎进行能量扩散
        3. 向量重排 (Re-ranking): 结合向量相似度输出最终结果
        """
        import math

        from sqlmodel import or_

        from services.core.embedding_service import embedding_service
        from services.core.vector_service import vector_service

        # --- 1. 锚点定位 (Anchoring) ---
        # 简单分词 (未来可接入 AC 自动机)
        keywords = set(re.findall(r"[\w]+", text))

        # 查找匹配的 Entity Node
        entity_anchors = []
        if keywords:
            # 构造 SQL OR 查询
            conditions = []
            for kw in keywords:
                if len(kw) > 1:  # 忽略单字
                    conditions.append(Memory.content == kw)

            if conditions:
                stmt = select(Memory).where(
                    Memory.type == "entity",
                    Memory.agent_id == agent_id,
                    or_(*conditions),
                )
                entity_anchors = (await session.exec(stmt)).all()

        # --- 2. 向量检索 (Vector Search) ---
        if query_vec is None:
            query_vec = embedding_service.encode_one(text)

        if not query_vec:
            return []

        # 初步召回 Top-20 (为了给扩散留余地)
        vector_candidates = vector_service.search(
            query_vec, limit=20, agent_id=agent_id
        )

        # --- 3. 扩散激活 (Spreading Activation) ---
        # 初始能量源:
        # - Vector Top-N: 能量 = score
        # - Entity Anchors: 能量 = 2.0 (最大值，因为是精确匹配)

        initial_energy = {}

        # 注入向量候选能量
        for res in vector_candidates:
            initial_energy[res["id"]] = res["score"]

        # 注入实体锚点能量
        for ent in entity_anchors:
            initial_energy[ent.id] = 2.0

        # 调用 Rust 引擎扩散
        engine = await get_rust_engine(session)
        final_scores = initial_energy

        if engine and initial_energy:
            # 扩散 2 步，衰减 0.6，阈值 0.05
            # 这样 Entity 可以激活与之相连的 Event
            final_scores = engine.propagate_activation(
                initial_scores=initial_energy, steps=2, decay=0.6, min_threshold=0.05
            )

        # --- 4. 结果重排 (Re-ranking) ---
        # 结合: 扩散分数 + 向量相似度 (如果存在) + 时间衰减 + 重要性

        # 获取所有涉及的记忆 ID
        all_candidate_ids = list(final_scores.keys())
        if not all_candidate_ids:
            return []

        # 批量获取 Memory 对象
        stmt = select(Memory).where(Memory.id.in_(all_candidate_ids))
        if exclude_after_time:
            stmt = stmt.where(Memory.timestamp < exclude_after_time.timestamp() * 1000)

        memories = (await session.exec(stmt)).all()

        ranked_results = []
        for mem in memories:
            # 跳过 Entity 节点本身 (我们只返回 Event 给 LLM，除非用户明确问定义)
            if mem.type == "entity":
                continue

            # 基础分 = 扩散分
            score = final_scores.get(mem.id, 0.0)

            # 向量分修正 (如果在向量结果里)
            vec_score = next(
                (x["score"] for x in vector_candidates if x["id"] == mem.id), 0.0
            )
            if vec_score > 0:
                score = score * 0.7 + vec_score * 0.3  # 扩散分主导

            # 重要性加权 (1-10 -> 1.0-2.0)
            importance_weight = 1.0 + (mem.importance / 10.0)
            score *= importance_weight

            # 时间衰减 (Ebbinghaus) - 简单的线性衰减
            # 越近越好，但如果是很久以前的高分记忆也保留
            days_diff = (datetime.now().timestamp() * 1000 - mem.timestamp) / (
                1000 * 3600 * 24
            )
            time_decay = 1.0 / (1.0 + math.log(1 + days_diff))  # 对数衰减
            score *= 0.8 + 0.2 * time_decay  # 时间影响占 20%

            ranked_results.append((mem, score))

        # 排序并截断
        ranked_results.sort(key=lambda x: x[1], reverse=True)
        final_memories = [m for m, s in ranked_results[:limit]]

        # [Reinforcement] 更新访问统计
        if update_access_stats and final_memories:
            await MemoryService.mark_memories_accessed(session, final_memories)

        return final_memories

    @staticmethod
    async def get_memories_by_filter(
        session: AsyncSession,
        limit: int = 10,
        filter_criteria: Dict = None,
        agent_id: str = "pero",
    ) -> List[Dict]:
        """
        基于 Metadata 过滤记忆 (用于周报生成等)
        替代 vector_service.query_memories
        """
        statement = select(Memory).where(Memory.agent_id == agent_id)

        if filter_criteria:
            # 时间戳范围的简单实现
            # {"timestamp": {"$lt": ...}}
            ts_filter = filter_criteria.get("timestamp")
            if ts_filter and isinstance(ts_filter, dict):
                lt_val = ts_filter.get("$lt")
                gt_val = ts_filter.get("$gt")
                if lt_val:
                    statement = statement.where(Memory.timestamp < lt_val)
                if gt_val:
                    statement = statement.where(Memory.timestamp > gt_val)

            # TODO: 如果需要，处理其他过滤器，如标签/簇

        statement = statement.order_by(desc(Memory.timestamp)).limit(limit)
        results = await session.exec(statement)
        memories = results.all()

        # 转换为 ChainService 期望的字典格式
        output = []
        for m in memories:
            output.append(
                {
                    "id": m.id,
                    "document": m.content,
                    "metadata": {
                        "timestamp": m.timestamp,
                        "importance": m.importance,
                        "tags": m.tags,
                        "type": m.type,
                    },
                }
            )
        return output

    @staticmethod
    async def search_memories_simple(
        session: AsyncSession,
        query_vec: List[float],
        limit: int = 5,
        filter_criteria: Dict = None,
        agent_id: str = "pero",
    ) -> List[Dict]:
        """
        简单的向量搜索 + Metadata 过滤 (用于 ChainService 查找历史)
        """
        from services.core.vector_service import vector_service

        # 1. 搜索 VectorDB (获取更多候选以允许过滤)
        candidates = vector_service.search(
            query_vec, limit=limit * 5, agent_id=agent_id
        )
        if not candidates:
            return []

        ids = [c["id"] for c in candidates]
        score_map = {c["id"]: c["score"] for c in candidates}

        # 2. 从带过滤器的 DB 中获取
        statement = (
            select(Memory).where(Memory.id.in_(ids)).where(Memory.agent_id == agent_id)
        )

        if filter_criteria:
            ts_filter = filter_criteria.get("timestamp")
            if ts_filter and isinstance(ts_filter, dict):
                lt_val = ts_filter.get("$lt")
                if lt_val:
                    statement = statement.where(Memory.timestamp < lt_val)

        results = await session.exec(statement)
        memories = results.all()

        # 3. 格式化
        output = []
        for m in memories:
            output.append(
                {
                    "id": m.id,
                    "score": score_map.get(m.id, 0),
                    "document": m.content,
                    "metadata": {"timestamp": m.timestamp, "importance": m.importance},
                }
            )

        # 按分数排序
        output.sort(key=lambda x: x["score"], reverse=True)
        return output[:limit]

    @staticmethod
    async def _keyword_search_fallback(
        session: AsyncSession,
        text: str,
        limit: int = 10,
        exclude_after_time=None,
        agent_id: str = "pero",
    ) -> List[Memory]:
        """原有的关键词搜索逻辑，作为兜底"""
        # ... (保留原有逻辑)
        # 提取关键词 (简单正则分词)
        keywords = [
            k.lower()
            for k in re.split(r"[\s,，.。!！?？;；:：、]+", text)
            if len(k) >= 2
        ]

        if not keywords:
            statement = (
                select(Memory)
                .where(Memory.agent_id == agent_id)
                .order_by(Memory.importance.desc())
                .limit(limit)
            )
            memories = (await session.exec(statement)).all()
        else:
            statement = select(Memory).where(Memory.agent_id == agent_id)
            all_memories = (await session.exec(statement)).all()

            scored_memories = []
            for m in all_memories:
                score = 0
                m_tags = [t.lower() for t in (m.tags.split(",") if m.tags else [])]

                for kw in keywords:
                    if any(kw in t or t in kw for t in m_tags):
                        score += 10
                    if kw in m.content.lower():
                        score += 5

                score += m.importance
                if score > 0:
                    scored_memories.append((m, score))

            scored_memories.sort(key=lambda x: x[1], reverse=True)
            memories = [m for m, s in scored_memories[:limit]]

        if exclude_after_time and memories:
            exclude_timestamp_ms = exclude_after_time.timestamp() * 1000
            memories = [m for m in memories if m.timestamp < exclude_timestamp_ms]

        return memories

    @staticmethod
    async def get_all_memories(
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        date_start: str = None,
        date_end: str = None,
        tags: str = None,
        memory_type: str = None,
        agent_id: str = None,  # Allow filtering by agent
    ) -> List[Memory]:
        from datetime import datetime

        statement = select(Memory)

        # Agent Filter
        if agent_id:
            statement = statement.where(Memory.agent_id == agent_id)

        # 类型过滤器
        if memory_type:
            statement = statement.where(Memory.type == memory_type)

        # 日期过滤器 (使用时间戳 ms)
        if date_start:
            try:
                start_dt = datetime.strptime(date_start, "%Y-%m-%d")
                start_ms = start_dt.timestamp() * 1000
                statement = statement.where(Memory.timestamp >= start_ms)
            except Exception as e:
                print(f"[MemoryService] 无效的开始日期: {e}")

        if date_end:
            try:
                end_dt = datetime.strptime(date_end, "%Y-%m-%d")
                # 增加一天以完全包含结束日期
                end_ms = (end_dt.timestamp() + 86400) * 1000
                statement = statement.where(Memory.timestamp < end_ms)
            except Exception as e:
                print(f"[MemoryService] 无效的结束日期: {e}")

        # 标签过滤器 (简单的字符串包含)
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            for tag in tag_list:
                statement = statement.where(Memory.tags.contains(tag))

        statement = (
            statement.order_by(desc(Memory.timestamp)).offset(offset).limit(limit)
        )
        return (await session.exec(statement)).all()

    @staticmethod
    async def get_tag_cloud(
        session: AsyncSession, agent_id: str = "pero"
    ) -> List[Dict[str, Any]]:
        """
        获取标签云数据 (Top 20 tags)
        """
        # 简单实现：取出所有 Memory 的 tags 字段，在内存中统计
        # TODO: 后期可以使用 SQL group by 优化
        statement = select(Memory)
        if agent_id:
            statement = statement.where(Memory.agent_id == agent_id)

        memories = (await session.exec(statement)).all()
        tag_counts = {}

        for m in memories:
            if not m.tags:
                continue
            tags = [t.strip() for t in m.tags.split(",") if t.strip()]
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        # 排序并取前 20
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        return [{"tag": t, "count": c} for t, c in sorted_tags]

    @staticmethod
    async def delete_orphaned_edges(session: AsyncSession) -> int:
        """
        清除孤立的边（即源节点或目标节点不存在的边）
        """
        # 使用子查询查找不存在的节点引用
        # DELETE FROM memoryrelation WHERE source_id NOT IN (SELECT id FROM memory) OR target_id NOT IN (SELECT id FROM memory)

        # SQLModel 的 delete 支持 where 子句，但对 subquery 支持视方言而定
        # 这里使用标准 SQLAlchemy 风格

        subquery = select(Memory.id)

        statement = delete(MemoryRelation).where(
            (MemoryRelation.source_id.not_in(subquery))
            | (MemoryRelation.target_id.not_in(subquery))
        )

        result = await session.exec(statement)
        await session.commit()

        # 如果有 Rust Engine 且已加载，可能需要重新加载或同步删除
        # 简单起见，这里假设 Rust Engine 会在下次启动或定期刷新时同步
        # 或者我们可以尝试从 Rust Engine 中移除（如果支持）
        # 目前 Rust Engine 是只读/追加为主，暂时忽略实时同步

        return result.rowcount

    @staticmethod
    async def get_memory_graph(
        session: AsyncSession, limit: int = 200, agent_id: str = "pero"
    ) -> Dict[str, Any]:
        """返回用于图形可视化的节点和边 (针对酷炫 UI 增强)"""
        # 获取最近 N 条记忆
        statement = select(Memory).order_by(desc(Memory.timestamp)).limit(limit)
        if agent_id:
            statement = statement.where(Memory.agent_id == agent_id)

        memories = (await session.exec(statement)).all()
        if not memories:
            return {"nodes": [], "edges": []}

        memory_ids = [m.id for m in memories]

        # 获取连接这些记忆的关系
        rel_statement = select(MemoryRelation).where(
            (MemoryRelation.source_id.in_(memory_ids))
            | (MemoryRelation.target_id.in_(memory_ids))
        )
        # 关系表也有 agent_id，增加过滤更严谨，虽然基于 memory_ids 过滤已经隐含了隔离
        if agent_id:
            rel_statement = rel_statement.where(MemoryRelation.agent_id == agent_id)

        relations = (await session.exec(rel_statement)).all()

        # 格式化为前端格式 (ECharts 力导向图)
        nodes = []
        for m in memories:
            # 根据重要性和访问计数计算符号大小
            # 基础大小 10，最大重要性 10 -> +20，最大访问对数刻度 -> +10
            import math

            size = 10 + (m.importance * 2) + (math.log(m.access_count + 1) * 5)
            size = min(size, 60)  # 限制大小

            nodes.append(
                {
                    "id": m.id,
                    "name": str(m.id),  # ECharts 的唯一名称
                    "label": {
                        "show": size > 15,  # 仅显示重要节点的标签
                        "formatter": (
                            m.content[:10] + "..." if len(m.content) > 10 else m.content
                        ),
                    },
                    "full_content": m.content,
                    "category": m.type,  # 事件、事实等
                    "value": m.importance,
                    "symbolSize": size,
                    "sentiment": m.sentiment,
                    "tags": m.tags,
                    "realTime": m.realTime,
                    "access_count": m.access_count,
                    # 如果需要，可以在此处添加每个节点的 ECharts 特定样式，
                    # 但最好在前端使用 categories/visualMap 处理
                }
            )

        edges = []
        added_edges = set()

        for r in relations:
            if r.source_id in memory_ids and r.target_id in memory_ids:
                edge_key = f"{r.source_id}-{r.target_id}"
                if edge_key not in added_edges:
                    edges.append(
                        {
                            "source": str(r.source_id),
                            "target": str(r.target_id),
                            "value": r.strength,
                            "relation_type": r.relation_type,
                            "lineStyle": {
                                "width": 1 + (r.strength * 4),  # 1px 到 5px
                                "curveness": 0.2,
                            },
                            "tooltip": {
                                "formatter": f"{r.relation_type}: {r.description or 'No desc'}"
                            },
                        }
                    )
                    added_edges.add(edge_key)

        # 时间顺序边 (Next/Prev) - 使它们变得微妙
        for m in memories:
            if m.prev_id and m.prev_id in memory_ids:
                edge_key = f"{m.prev_id}-{m.id}"
                if edge_key not in added_edges:
                    edges.append(
                        {
                            "source": str(m.prev_id),
                            "target": str(m.id),
                            "value": 1,
                            "relation_type": "temporal",
                            "lineStyle": {
                                "width": 1,
                                "color": "#cccccc",
                                "opacity": 0.3,
                                "type": "dashed",
                                "curveness": 0.1,
                            },
                        }
                    )
                    added_edges.add(edge_key)

        return {"nodes": nodes, "edges": edges}
