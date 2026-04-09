import json
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Memory, TriviumSyncTask
from services.memory.trivium_store import TriviumMemoryStore


class TriviumSyncService:
    @staticmethod
    def _serialize_payload(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _get_store(store_name: str = "memory") -> TriviumMemoryStore:
        return TriviumMemoryStore(store_name=store_name or "memory")

    @staticmethod
    def _build_insert_payload(memory: Memory) -> Dict[str, Any]:
        return {
            "id": memory.id,
            "content": memory.content,
            "type": memory.type,
            "timestamp": memory.timestamp,
            "importance": float(memory.importance or 0),
            "tags": memory.tags,
            "clusters": memory.clusters,
            "agent_id": memory.agent_id,
        }

    @staticmethod
    def _build_dedupe_key(store_name: str, operation: str, **kwargs: Any) -> str:
        store_prefix = store_name or "memory"
        if operation == "upsert_memory":
            return f"{store_prefix}:upsert:{kwargs['memory_id']}"
        if operation == "delete_memory":
            return f"{store_prefix}:delete:{kwargs['memory_id']}"
        if operation == "link_memories":
            label = kwargs.get("label", "associative")
            return f"{store_prefix}:link:{kwargs['src']}:{kwargs['dst']}:{label}"
        return f"{store_prefix}:{operation}"

    @staticmethod
    async def _get_existing_task(
        session: AsyncSession,
        dedupe_key: str,
    ) -> Optional[TriviumSyncTask]:
        statement = (
            select(TriviumSyncTask)
            .where(TriviumSyncTask.dedupe_key == dedupe_key)
            .where(TriviumSyncTask.status.in_(["pending", "failed", "processing"]))
            .order_by(TriviumSyncTask.created_at.desc())
        )
        return (await session.exec(statement)).first()

    @staticmethod
    def _apply_task_filters(
        statement,
        agent_id: Optional[str] = None,
        store_name: Optional[str] = None,
        status: Optional[str] = None,
        operation: Optional[str] = None,
        min_retry_count: Optional[int] = None,
        max_retry_count: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ):
        if agent_id:
            statement = statement.where(TriviumSyncTask.agent_id == agent_id)
        if store_name:
            statement = statement.where(TriviumSyncTask.store_name == store_name)
        if status:
            statement = statement.where(TriviumSyncTask.status == status)
        if operation:
            statement = statement.where(TriviumSyncTask.operation == operation)
        if min_retry_count is not None:
            statement = statement.where(TriviumSyncTask.retry_count >= min_retry_count)
        if max_retry_count is not None:
            statement = statement.where(TriviumSyncTask.retry_count <= max_retry_count)
        if created_after is not None:
            statement = statement.where(TriviumSyncTask.created_at >= created_after)
        if created_before is not None:
            statement = statement.where(TriviumSyncTask.created_at <= created_before)
        return statement

    @staticmethod
    async def _enqueue_task(
        session: AsyncSession,
        *,
        operation: str,
        memory_id: Optional[int],
        agent_id: str,
        payload: Dict[str, Any],
        store_name: str = "memory",
        dedupe_kwargs: Optional[Dict[str, Any]] = None,
    ) -> TriviumSyncTask:
        normalized_store_name = store_name or "memory"
        dedupe_key = TriviumSyncService._build_dedupe_key(
            normalized_store_name,
            operation,
            **(dedupe_kwargs or {}),
        )
        serialized_payload = TriviumSyncService._serialize_payload(payload)
        existing_task = await TriviumSyncService._get_existing_task(session, dedupe_key)
        if existing_task:
            existing_task.memory_id = memory_id
            existing_task.store_name = normalized_store_name
            existing_task.agent_id = agent_id
            existing_task.payload_json = serialized_payload
            existing_task.status = "pending"
            existing_task.last_error = None
            existing_task.updated_at = datetime.now()
            session.add(existing_task)
            await session.commit()
            await session.refresh(existing_task)
            return existing_task

        task = TriviumSyncTask(
            operation=operation,
            memory_id=memory_id,
            store_name=normalized_store_name,
            dedupe_key=dedupe_key,
            payload_json=serialized_payload,
            status="pending",
            agent_id=agent_id,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def enqueue_insert(
        session: AsyncSession,
        memory: Memory,
        embedding: Optional[list[float]],
        store_name: str = "memory",
    ) -> TriviumSyncTask:
        return await TriviumSyncService.enqueue_upsert_payload(
            session,
            memory_id=memory.id,
            agent_id=memory.agent_id,
            embedding=embedding,
            payload=TriviumSyncService._build_insert_payload(memory),
            content=memory.content,
            store_name=store_name,
        )

    @staticmethod
    async def enqueue_upsert_payload(
        session: AsyncSession,
        memory_id: int,
        agent_id: str,
        embedding: Optional[list[float]],
        payload: Dict[str, Any],
        content: Optional[str] = None,
        store_name: str = "memory",
    ) -> TriviumSyncTask:
        return await TriviumSyncService._enqueue_task(
            session,
            operation="upsert_memory",
            memory_id=memory_id,
            agent_id=agent_id,
            payload={
                "memory_id": memory_id,
                "content": content or payload.get("content"),
                "embedding": embedding or [],
                "payload": payload,
            },
            store_name=store_name,
            dedupe_kwargs={"memory_id": memory_id},
        )

    @staticmethod
    async def enqueue_delete(
        session: AsyncSession,
        memory_id: int,
        agent_id: str,
        store_name: str = "memory",
    ) -> TriviumSyncTask:
        return await TriviumSyncService.enqueue_delete_payload(
            session,
            memory_id=memory_id,
            agent_id=agent_id,
            store_name=store_name,
        )

    @staticmethod
    async def enqueue_delete_payload(
        session: AsyncSession,
        memory_id: int,
        agent_id: str,
        store_name: str = "memory",
    ) -> TriviumSyncTask:
        return await TriviumSyncService._enqueue_task(
            session,
            operation="delete_memory",
            memory_id=memory_id,
            agent_id=agent_id,
            payload={"memory_id": memory_id},
            store_name=store_name,
            dedupe_kwargs={"memory_id": memory_id},
        )

    @staticmethod
    async def enqueue_time_link(
        session: AsyncSession,
        src_memory_id: int,
        dst_memory_id: int,
        agent_id: str,
        label: str = "associative",
        weight: float = 0.2,
        store_name: str = "memory",
    ) -> TriviumSyncTask:
        return await TriviumSyncService.enqueue_link_payload(
            session,
            src_memory_id=src_memory_id,
            dst_memory_id=dst_memory_id,
            agent_id=agent_id,
            label=label,
            weight=weight,
            store_name=store_name,
        )

    @staticmethod
    async def enqueue_link_payload(
        session: AsyncSession,
        src_memory_id: int,
        dst_memory_id: int,
        agent_id: str,
        label: str = "associative",
        weight: float = 0.2,
        store_name: str = "memory",
    ) -> TriviumSyncTask:
        return await TriviumSyncService._enqueue_task(
            session,
            operation="link_memories",
            memory_id=src_memory_id,
            agent_id=agent_id,
            payload={
                "src": src_memory_id,
                "dst": dst_memory_id,
                "label": label,
                "weight": weight,
            },
            store_name=store_name,
            dedupe_kwargs={
                "src": src_memory_id,
                "dst": dst_memory_id,
                "label": label,
            },
        )

    @staticmethod
    async def retry_pending_tasks(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        store_name: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        statement = (
            select(TriviumSyncTask)
            .where(TriviumSyncTask.status.in_(["pending", "failed"]))
            .order_by(TriviumSyncTask.created_at)
            .limit(limit)
        )
        statement = TriviumSyncService._apply_task_filters(
            statement,
            agent_id=agent_id,
            store_name=store_name,
        )

        tasks = (await session.exec(statement)).all()
        if not tasks:
            return {
                "status": "success",
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "store_name": store_name,
                "task_ids": [],
            }

        processed = 0
        succeeded = 0
        failed = 0
        touched_stores: dict[str, TriviumMemoryStore] = {}
        processed_by_store: dict[str, int] = {}
        succeeded_by_store: dict[str, int] = {}
        failed_by_store: dict[str, int] = {}
        task_ids: list[int] = []

        for task in tasks:
            processed += 1
            task_ids.append(task.id)
            task.status = "processing"
            task.updated_at = datetime.now()
            session.add(task)
            await session.commit()

            try:
                payload = json.loads(task.payload_json or "{}")
                normalized_store_name = task.store_name or "memory"
                touched_stores[normalized_store_name] = TriviumSyncService._get_store(
                    normalized_store_name
                )
                store = touched_stores[normalized_store_name]
                processed_by_store[normalized_store_name] = (
                    processed_by_store.get(normalized_store_name, 0) + 1
                )
                if task.operation == "upsert_memory":
                    embedding = payload.get("embedding") or []
                    if embedding:
                        await store.insert(
                            payload["memory_id"],
                            embedding,
                            payload.get("payload") or {},
                        )
                elif task.operation == "link_memories":
                    await store.link(
                        payload["src"],
                        payload["dst"],
                        label=payload.get("label", "associative"),
                        weight=float(payload.get("weight", 0.2)),
                    )
                elif task.operation == "delete_memory":
                    await store.delete(payload["memory_id"])
                else:
                    raise ValueError(f"未知补偿任务类型: {task.operation}")

                await session.delete(task)
                await session.commit()
                succeeded += 1
                succeeded_by_store[normalized_store_name] = (
                    succeeded_by_store.get(normalized_store_name, 0) + 1
                )
            except Exception as e:
                task.status = "failed"
                task.retry_count += 1
                task.last_error = str(e)
                task.updated_at = datetime.now()
                session.add(task)
                await session.commit()
                failed += 1
                failed_by_store[normalized_store_name] = (
                    failed_by_store.get(normalized_store_name, 0) + 1
                )

        for store in touched_stores.values():
            with suppress(Exception):
                await store.flush()

        return {
            "status": "success",
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "store_name": store_name,
            "task_ids": task_ids,
            "processed_by_store": processed_by_store,
            "succeeded_by_store": succeeded_by_store,
            "failed_by_store": failed_by_store,
        }

    @staticmethod
    async def clear_tasks_for_memory(
        session: AsyncSession,
        memory_id: int,
        store_name: str = "memory",
    ):
        statement = (
            delete(TriviumSyncTask)
            .where(TriviumSyncTask.memory_id == memory_id)
            .where(TriviumSyncTask.store_name == (store_name or "memory"))
        )
        await session.exec(statement)
        await session.commit()

    @staticmethod
    async def list_tasks(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        store_name: Optional[str] = None,
        status: Optional[str] = None,
        operation: Optional[str] = None,
        min_retry_count: Optional[int] = None,
        max_retry_count: Optional[int] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TriviumSyncTask]:
        statement = (
            select(TriviumSyncTask)
            .order_by(TriviumSyncTask.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        statement = TriviumSyncService._apply_task_filters(
            statement,
            agent_id=agent_id,
            store_name=store_name,
            status=status,
            operation=operation,
            min_retry_count=min_retry_count,
            max_retry_count=max_retry_count,
            created_after=created_after,
            created_before=created_before,
        )
        return list((await session.exec(statement)).all())

    @staticmethod
    async def get_task_summary(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        store_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        statement = select(TriviumSyncTask).order_by(TriviumSyncTask.created_at.desc())
        statement = TriviumSyncService._apply_task_filters(
            statement,
            agent_id=agent_id,
            store_name=store_name,
        )
        tasks = list((await session.exec(statement)).all())

        summary: Dict[str, Any] = {
            "total": len(tasks),
            "pending_total": 0,
            "failed_total": 0,
            "processing_total": 0,
            "healthy": True,
            "attention_required": False,
            "by_status": {},
            "by_store": {},
            "by_operation": {},
            "top_failed_stores": [],
            "top_failed_operations": [],
            "oldest_pending_created_at": None,
            "latest_error": None,
        }

        failed_store_counts: Dict[str, int] = {}
        failed_operation_counts: Dict[str, int] = {}
        oldest_pending = None
        latest_error_task = None
        for task in tasks:
            summary["by_status"][task.status] = summary["by_status"].get(task.status, 0) + 1
            summary["by_operation"][task.operation] = summary["by_operation"].get(task.operation, 0) + 1
            task_store_name = task.store_name or "memory"
            store_bucket = summary["by_store"].setdefault(
                task_store_name,
                {
                    "total": 0,
                    "pending": 0,
                    "failed": 0,
                    "processing": 0,
                    "by_operation": {},
                },
            )
            store_bucket["total"] += 1
            store_bucket[task.status] = store_bucket.get(task.status, 0) + 1
            store_bucket["by_operation"][task.operation] = (
                store_bucket["by_operation"].get(task.operation, 0) + 1
            )

            if task.status == "failed":
                failed_store_counts[task_store_name] = (
                    failed_store_counts.get(task_store_name, 0) + 1
                )
                failed_operation_counts[task.operation] = (
                    failed_operation_counts.get(task.operation, 0) + 1
                )

            if task.status in {"pending", "failed"} and (
                oldest_pending is None or task.created_at < oldest_pending
            ):
                oldest_pending = task.created_at

            if task.last_error and (
                latest_error_task is None or task.updated_at > latest_error_task.updated_at
            ):
                latest_error_task = task

        summary["pending_total"] = summary["by_status"].get("pending", 0)
        summary["failed_total"] = summary["by_status"].get("failed", 0)
        summary["processing_total"] = summary["by_status"].get("processing", 0)
        summary["healthy"] = summary["pending_total"] == 0 and summary["failed_total"] == 0
        summary["attention_required"] = not summary["healthy"]
        summary["top_failed_stores"] = [
            {"store_name": name, "failed": count}
            for name, count in sorted(
                failed_store_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        summary["top_failed_operations"] = [
            {"operation": name, "failed": count}
            for name, count in sorted(
                failed_operation_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

        if oldest_pending is not None:
            summary["oldest_pending_created_at"] = oldest_pending.isoformat()
        if latest_error_task is not None:
            summary["latest_error"] = {
                "task_id": latest_error_task.id,
                "store_name": latest_error_task.store_name,
                "operation": latest_error_task.operation,
                "message": latest_error_task.last_error,
                "updated_at": latest_error_task.updated_at.isoformat(),
            }

        return summary
