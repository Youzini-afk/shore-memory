import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import ConversationLog, Memory

logger = logging.getLogger("pero.memory")

# [Global] Tag cloud TTL 缓存 (避免高频全表扫描)
# 结构: {agent_id: {"data": [...], "expires_at": float}}
_tag_cloud_cache: Dict[str, Any] = {}
_TAG_CLOUD_TTL = 300  # 5 分钟


def _invalidate_tag_cloud_cache(agent_id: str = None):
    """使指定 agent（或全部）的 tag cloud 缓存立即失效。
    在写入/删除记忆后调用，保证下次 get_tag_cloud 能得到最新数据。
    """
    if agent_id:
        _tag_cloud_cache.pop(agent_id, None)
    else:
        _tag_cloud_cache.clear()


# Graph engine 已完全被 TriviumDB 替代
# 已移除过时的 CognitiveGraphEngine 及相关加载逻辑


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
        from services.memory.trivium_store import trivium_store

        # [钩子] memory.save.pre
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
        # 生成 Embedding (用于写入向量数据库)
        embedding_vec = await embedding_service.encode_one(content)

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

        # 3. 同步写入向量数据库 (TriviumDB)
        if embedding_vec:
            try:
                # 构建元数据 Payload
                payload = {
                    "id": memory.id,
                    "content": content,
                    "type": memory_type,
                    "timestamp": memory.timestamp,
                    "importance": float(importance),
                    "tags": tags,
                    "clusters": clusters,
                    "agent_id": agent_id,
                }

                # 写入 TriviumDB
                from services.memory.trivium_store import trivium_store

                await trivium_store.insert(memory.id, embedding_vec, payload)

            except Exception as e:
                print(f"[MemoryService] 同步到 TriviumDB 失败: {e}")
        else:
            print(
                f"[MemoryService] 警告: Embedding 为空，未写入 TriviumDB (Memory ID {memory.id})"
            )

        # 4. 更新上一条记忆的 next_id (双向链表维护)
        if last_memory:
            last_memory.next_id = memory.id
            session.add(last_memory)
            await session.commit()

            # TriviumDB 建立双向时间链接 (默认 label="associative")
            try:
                from services.memory.trivium_store import trivium_store

                await trivium_store.link(
                    memory.id, last_memory.id, label="associative", weight=0.2
                )
                await trivium_store.link(
                    last_memory.id, memory.id, label="associative", weight=0.2
                )
            except Exception as e:
                print(f"[MemoryService] TriviumDB 时间图谱连接失败: {e}")

        # [钩子] memory.save.post
        await EventBus.publish("memory.save.post", memory)

        # [缓存失效] 新记忆写入会改变 tag 分布，使缓存立即过期
        _invalidate_tag_cloud_cache(agent_id)

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
                print(f"[MemoryService] 无效的日期格式: {date_str}")

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
        from sqlmodel import delete

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
    async def delete_by_msg_timestamp(
        session: AsyncSession, msg_timestamp: str, agent_id: str = None
    ):
        from sqlmodel import delete

        statement = delete(Memory).where(Memory.msgTimestamp == msg_timestamp)
        await session.exec(statement)
        await session.commit()
        # [缓存失效] 删除记忆后使 tag cloud 缓存过期
        _invalidate_tag_cloud_cache(agent_id)

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
        from services.memory.trivium_store import trivium_store

        try:
            # 1. 直接通过 TriviumDB 的高级检索（图谱扩散已内置于底层 L4-L6）
            query_vec = await embedding_service.encode_one(text)
            if not query_vec:
                return []

            hits = await trivium_store.search(
                query_vec,
                top_k=limit,
                expand_depth=2,  # 开启图谱游走扩散
                agent_id=agent_id,
                query_text=text,
                enable_dpp=True,  # 增加联想多样性
                enable_text_hybrid=True,
            )

            if not hits:
                return []

            results = []
            seen_tags = set()
            for h in hits:
                payload = h.get("payload") or {}
                mid = h["id"]
                content = payload.get("content", "")

                tags_str = payload.get("tags", "")
                if tags_str:
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                    for tag in tags:
                        if tag not in seen_tags:
                            results.append({"id": mid, "name": tag, "type": "tag"})
                            seen_tags.add(tag)

                if len(results) < limit:
                    summary = content[:20] + "..." if len(content) > 20 else content
                    results.append({"id": mid, "name": summary, "type": "memory"})

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
        [混合检索策略 v3 - TriviumDB 原生引擎版]
        TriviumDB 已经在 Rust 底层原生实现了完整的高级认知管线：
        L1-L2 基础向量召回 -> L3 NMF+FISTA意图拆解与稀疏拓展 -> L4-L6 图谱扩散传播 -> L8 DPP去冗余
        """
        from services.core.embedding_service import embedding_service
        from services.memory.trivium_store import trivium_store

        if query_vec is None:
            query_vec = await embedding_service.encode_one(text)
        if not query_vec:
            return []

        # 直接调用 TriviumDB 高级查询管道
        hits = await trivium_store.search(
            query_vector=query_vec,
            top_k=limit,
            expand_depth=2,  # 开启图谱游走扩散
            agent_id=agent_id,
            query_text=text,  # 用于混合搜索
            enable_dpp=True,  # 开启 DPP 多样性
            dpp_weight=1.2,  # 质量权重
            enable_text_hybrid=True,
        )

        if not hits:
            return []

        # 过滤时间 (exclude_after_time) 及组装 Memory 模型
        final_memories = []
        exclude_ts = (
            exclude_after_time.timestamp() * 1000 if exclude_after_time else None
        )

        hit_ids = [h["id"] for h in hits]
        if hit_ids:
            # 去数据库捞一下完整的 ORM 对象 (包含完整长文本等字段)
            stmt = select(Memory).where(Memory.id.in_(hit_ids))
            memories_db = (await session.exec(stmt)).all()

            # 建立 ID 到对象的映射，保证顺序与打分一致
            mem_map = {m.id: m for m in memories_db}

            for h in hits:
                mid = h["id"]
                if mid in mem_map:
                    m = mem_map[mid]
                    # 跳过 Entity 节点本身
                    if m.type == "entity":
                        continue
                    if exclude_ts and m.timestamp >= exclude_ts:
                        continue
                    final_memories.append(m)

        # [强化] 更新访问统计
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
        from services.memory.trivium_store import trivium_store

        # 1. 搜索 VectorDB (获取更多候选以允许过滤)
        # TriviumDB 默认支持 payload_filter，但这里为了兼容后续逻辑，可以先调 search
        hits = await trivium_store.search(
            query_vector=query_vec,
            top_k=limit * 5,
            expand_depth=0,  # 简单搜索不需要图谱扩散
            agent_id=agent_id,
            enable_dpp=False,
            enable_text_hybrid=False,
        )
        if not hits:
            return []

        ids = [h["id"] for h in hits]
        score_map = {h["id"]: h["score"] for h in hits}

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
        agent_id: str = None,  # 允许按代理过滤
    ) -> List[Memory]:
        from datetime import datetime

        statement = select(Memory)

        # 代理过滤器
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
    async def delete_orphaned_edges(session: AsyncSession) -> int:
        """
        清除孤立的边
        (TriviumDB 会依靠后台引擎的 Auto Compaction 清理过期悬空边，此处改为空操作)
        """
        return 0

    @staticmethod
    async def get_memory_graph(
        session: AsyncSession, limit: int = 200, agent_id: str = "pero"
    ) -> Dict[str, Any]:
        """返回用于图形可视化的节点和边 (基于 TriviumDB)"""
        # 获取最近 N 条记忆
        statement = select(Memory).order_by(desc(Memory.timestamp)).limit(limit)
        if agent_id:
            statement = statement.where(Memory.agent_id == agent_id)

        memories = (await session.exec(statement)).all()
        if not memories:
            return {"nodes": [], "edges": []}

        memory_ids = {m.id for m in memories}
        nodes = []
        for m in memories:
            nodes.append(
                {
                    "id": str(m.id),
                    "name": m.content[:15] + "..."
                    if len(m.content) > 15
                    else m.content,
                    "category": m.type,
                    "value": m.importance,
                }
            )

        edges = []
        from services.memory.trivium_store import trivium_store

        for mem_id in memory_ids:
            neighbors = await trivium_store.get_neighbors(mem_id)
            if not neighbors:
                continue

            for nbr in neighbors:
                # 兼容可能的返回格式 (hit) 或者 tuple(id, weight, label)
                tgt_id = None
                weight = 0.5
                label = "related"

                if hasattr(nbr, "id"):
                    tgt_id = nbr.id
                    weight = getattr(nbr, "score", 0.5)
                elif isinstance(nbr, tuple):
                    tgt_id = nbr[0]
                    weight = nbr[1] if len(nbr) > 1 else 0.5
                elif isinstance(nbr, dict):
                    tgt_id = nbr.get("id")
                    weight = nbr.get("weight", 0.5)
                elif isinstance(nbr, int):
                    tgt_id = nbr

                # 双向边可能导致 Echarts 重复, 但这里如果 target 也在 limit 节点内我们就展示
                if tgt_id and tgt_id in memory_ids:
                    edges.append(
                        {
                            "source": str(mem_id),
                            "target": str(tgt_id),
                            "value": float(weight),
                            "label": label,
                        }
                    )

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    async def get_tag_cloud(
        session: AsyncSession, agent_id: str = "pero"
    ) -> List[Dict[str, Any]]:
        """
        获取标签云数据 (Top 20 tags)

        优化点:
        1. 只 SELECT tags 列，避免加载 content/embedding_json 等大字段
        2. TTL=5min 内存缓存：同一 agent 短时间内重复调用直接返回缓存
        """
        global _tag_cloud_cache

        cache_key = agent_id or "pero"
        now = time.monotonic()

        # 命中缓存则直接返回
        cached = _tag_cloud_cache.get(cache_key)
        if cached and now < cached["expires_at"]:
            return cached["data"]

        # 只查 tags 列，大幅减少 I/O（跳过 content、embedding_json 等大字段）
        statement = select(Memory.tags)
        if agent_id:
            statement = statement.where(
                Memory.agent_id == agent_id,
                Memory.tags != "",
                Memory.tags.is_not(None),
            )
        else:
            statement = statement.where(
                Memory.tags != "",
                Memory.tags.is_not(None),
            )

        rows = (await session.exec(statement)).all()

        tag_counts: Dict[str, int] = {}
        for tags_str in rows:
            # rows 返回标量列表 (str | None)
            if not tags_str:
                continue
            for t in tags_str.split(","):
                t = t.strip()
                if t:
                    tag_counts[t] = tag_counts.get(t, 0) + 1

        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        result = [{"tag": t, "count": c} for t, c in sorted_tags]

        # 写入缓存
        _tag_cloud_cache[cache_key] = {
            "data": result,
            "expires_at": now + _TAG_CLOUD_TTL,
        }

        return result
