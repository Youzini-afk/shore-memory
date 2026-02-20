import asyncio
import contextlib
import hashlib
import logging
import os
from datetime import datetime
from typing import Awaitable, Callable, Dict, Optional

import aiofiles
import httpx

# 用于持久化的数据库导入
from .models import SocialMessage, SocialSession

logger = logging.getLogger(__name__)


class ImageCacheManager:
    """
    简单的本地图片缓存管理器。
    用于下载 OneBot 图片到本地，以便转换为 Base64 发送给 LLM。
    """

    def __init__(self, cache_dir: str = None, max_files: int = 50):
        if cache_dir is None:
            # 动态计算绝对路径: .../backend/nit_core/plugins/social_adapter/session_manager.py -> .../backend/data/social_images
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            self.cache_dir = os.path.join(backend_dir, "data", "social_images")
        else:
            self.cache_dir = cache_dir

        self.max_files = max_files
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    async def download_image(self, url: str) -> Optional[str]:
        """
        下载图片并返回本地绝对路径。
        如果下载失败，返回 None。
        """
        try:
            # 使用 URL 的 MD5 作为文件名
            url_hash = hashlib.md5(url.encode()).hexdigest()
            # 尝试推断扩展名，默认 jpg
            ext = "jpg"
            if ".png" in url:
                ext = "png"
            elif ".gif" in url:
                ext = "gif"

            filename = f"{url_hash}.{ext}"
            filepath = os.path.join(self.cache_dir, filename)
            abs_path = os.path.abspath(filepath)

            # 如果文件已存在，直接返回
            if os.path.exists(filepath):
                return abs_path

            # 下载
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    async with aiofiles.open(filepath, "wb") as f:
                        await f.write(resp.content)

                    # 简单的清理策略：如果文件过多，删除最旧的
                    self._cleanup()
                    return abs_path
                else:
                    logger.warning(
                        f"[ImageCache] 下载图片失败 {url}: {resp.status_code}"
                    )
                    return None
        except Exception as e:
            logger.error(f"[ImageCache] 下载图片错误: {e}")
            return None

    def _cleanup(self):
        """
        清理旧文件，保持缓存大小在 max_files 以内。
        """
        try:
            files = [
                os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir)
            ]
            if len(files) <= self.max_files:
                return

            # 按修改时间排序 (最旧的在前)
            files.sort(key=os.path.getmtime)

            # 删除多余的
            num_to_delete = len(files) - self.max_files
            for i in range(num_to_delete):
                with contextlib.suppress(Exception):
                    os.remove(files[i])
        except Exception as e:
            logger.warning(f"[ImageCache] 清理失败: {e}")


class SocialSessionManager:
    def __init__(self, flush_callback: Callable[[SocialSession], Awaitable[None]]):
        """
        参数：
            flush_callback: 缓冲区刷新时调用的异步函数。
        """
        self.sessions: Dict[str, SocialSession] = {}
        self.flush_callback = flush_callback

        # [重构] 如果需要，为多 Agent 存储 bot_id 映射
        # 但实际上 SocialService 处理连接映射。
        # SessionManager 需要知道使用哪个连接进行发送。
        # 我们可以将 bot_id 存储在 Session 对象中。
        self.bot_id: Optional[str] = None  # 旧版全局回退

        # 配置
        self.BUFFER_TIMEOUT = 20  # 秒
        self.BUFFER_MAX_SIZE = 10  # 条消息
        self.ACTIVE_DURATION = 120  # 秒（发言后保持“活跃”的时间）

        # 图片缓存管理器
        self.image_manager = ImageCacheManager()

    def set_bot_id(self, bot_id: str):
        """设置全局 Bot ID (旧版支持)"""
        self.bot_id = str(bot_id)
        logger.info(f"[SessionManager] Bot ID set to: {self.bot_id}")

    def get_or_create_session(
        self,
        session_id: str,
        session_type: str,
        session_name: str = "",
        agent_id: str = "pero",
    ) -> SocialSession:
        # [多代理支持] 使用复合键隔离不同代理之间的会话
        # 键格式: "{agent_id}:{session_id}"
        # 这确保 Nana 对群 123 的记忆与 Pero 对群 123 的记忆是分开的
        composite_key = f"{agent_id}:{session_id}"

        if composite_key not in self.sessions:
            session = SocialSession(
                session_id=session_id,  # 保留原始 ID 用于 API 调用
                session_type=session_type,
                session_name=session_name,
            )
            # 将 agent_id 注入会话上下文
            session.agent_id = agent_id
            # 如果需要，也可以存储复合键，或者仅用于查找映射
            self.sessions[composite_key] = session

        return self.sessions[composite_key]

    async def _persist_message(
        self, session: SocialSession, msg: SocialMessage, role: str
    ):
        """
        将消息持久化到独立社交数据库 (QQMessage)。
        """
        try:
            # 局部导入以避免循环导入
            import json

            from .database import get_social_db_session
            from .models_db import QQMessage

            # [优化] 使用单独的任务或快速提交以避免持有锁
            async for db_session in get_social_db_session():
                try:
                    new_msg = QQMessage(
                        msg_id=msg.msg_id,
                        session_id=session.session_id,
                        session_type=session.session_type,
                        sender_id=msg.sender_id,
                        sender_name=msg.sender_name,
                        content=msg.content,
                        timestamp=msg.timestamp,
                        raw_event_json=json.dumps(msg.raw_event, default=str),
                        agent_id=session.agent_id,
                    )
                    db_session.add(new_msg)
                    await db_session.commit()
                except Exception as inner_e:
                    logger.error(f"数据库插入错误: {inner_e}")
                    await db_session.rollback()

        except Exception as e:
            logger.error(f"持久化社交消息到独立数据库失败: {e}")

    async def persist_outgoing_message(
        self,
        session_id: str,
        session_type: str,
        content: str,
        sender_name: str = "Assistant",
        agent_id: str = "pero",
    ):
        """
        将发出的消息（Agent 的回复）持久化到独立社交数据库，并同步更新内存 Buffer。
        """
        try:
            import uuid

            from .database import get_social_db_session
            from .models_db import QQMessage

            msg_id = str(uuid.uuid4())
            timestamp = datetime.now()

            # 1. 更新内存 Buffer (上下文一致性的关键)
            # 确保 Bot 下一次思考时能看到自己刚刚说的话
            session = self.get_or_create_session(
                session_id, session_type, agent_id=agent_id
            )
            mem_msg = SocialMessage(
                msg_id=msg_id,
                sender_id="self",
                sender_name=sender_name,
                content=content,
                timestamp=timestamp,
                raw_event={},
            )
            session.add_message(mem_msg)

            # 2. 持久化到数据库
            async for db_session in get_social_db_session():
                new_msg = QQMessage(
                    msg_id=msg_id,  # 为内部消息生成 ID
                    session_id=session_id,
                    session_type=session_type,
                    sender_id="self",  # 如果已知，则为 Bot 的 ID
                    sender_name=sender_name,
                    content=content,
                    timestamp=timestamp,
                    raw_event_json="{}",
                    agent_id=agent_id,
                )
                db_session.add(new_msg)
                await db_session.commit()
        except Exception as e:
            logger.error(f"持久化发出消息失败: {e}")

    async def persist_system_notification(
        self, session_id: str, session_type: str, content: str, raw_event: dict = None
    ):
        """
        将系统通知（如撤回、禁言）持久化到独立社交数据库。
        """
        try:
            import json
            import uuid

            from .database import get_social_db_session
            from .models_db import QQMessage

            if raw_event is None:
                raw_event = {}

            async for db_session in get_social_db_session():
                new_msg = QQMessage(
                    msg_id=str(uuid.uuid4()),
                    session_id=session_id,
                    session_type=session_type,
                    sender_id="system",
                    sender_name="System",
                    content=content,
                    timestamp=datetime.now(),
                    raw_event_json=json.dumps(raw_event, default=str),
                )
                db_session.add(new_msg)
                await db_session.commit()
        except Exception as e:
            logger.error(f"持久化系统通知失败: {e}")

    async def get_recent_messages(
        self, session_id: str, session_type: str, limit: int = 20
    ) -> list[SocialMessage]:
        """
        从独立数据库获取最近的消息作为上下文。
        """
        logger.debug(
            f"[{session_id}] 调用 get_recent_messages。类型: {session_type}, 限制: {limit}"
        )
        try:
            from sqlmodel import select

            from .database import get_social_db_session
            from .models_db import QQMessage

            messages = []
            logger.debug(f"[{session_id}] 正在请求数据库会话...")

            # [关键修复] 使用 run_in_executor 以避免同步 DB 调用阻塞事件循环
            # 即使 db_session.exec 是可等待的，底层的 aiosqlite/sqlite 驱动程序可能会阻塞 GIL 或线程
            asyncio.get_running_loop()

            def run_sync_query():
                # 此函数将在单独的线程中运行
                # 我们需要一个新的同步引擎和会话，因为我们正在跨越线程边界
                # 且异步引擎在这种情况下对于同步执行不是线程安全的。
                # 但是，我们是在异步函数内部。

                # 让我们尝试另一种方法：在执行前强制让出事件循环
                pass

            async for db_session in get_social_db_session():
                logger.debug(f"[{session_id}] 已获取数据库会话。正在执行查询...")

                try:
                    # [关键调试] 添加 sleep 以确保循环正在让出
                    await asyncio.sleep(0.01)

                    statement = (
                        select(QQMessage)
                        .where(
                            QQMessage.session_id == session_id,
                            QQMessage.session_type == session_type,
                        )
                        .order_by(QQMessage.timestamp.desc())
                        .limit(limit)
                    )

                    # [修复] 将执行包装在 shield 中或检查它是否真正被等待
                    logger.debug(f"[{session_id}] 正在等待 db_session.exec...")
                    result = await asyncio.wait_for(
                        db_session.exec(statement), timeout=3.0
                    )
                    logger.debug(
                        f"[{session_id}] db_session.exec 返回。正在获取所有结果..."
                    )
                    results = result.all()

                    logger.debug(f"[{session_id}] 查询返回了 {len(results)} 行。")

                    # 转换回 SocialMessage（或类似的字典）并反转顺序
                    for row in reversed(results):
                        msg = SocialMessage(
                            msg_id=row.msg_id,
                            sender_id=row.sender_id,
                            sender_name=row.sender_name,
                            content=row.content,
                            timestamp=row.timestamp,
                            raw_event={},
                        )
                        messages.append(msg)
                except asyncio.TimeoutError:
                    logger.error(f"[{session_id}] 数据库查询超时 (3s)！")
                    # 不要抛出异常，只需返回空列表让流程继续
                    # [回退] 如果 DB 失败，返回缓冲区内容？不，调用者处理回退。
                    return []
                except Exception as query_e:
                    logger.error(f"[{session_id}] 查询执行错误: {query_e}")
                    raise query_e

            logger.debug(
                f"[{session_id}] get_recent_messages 完成。返回 {len(messages)} 条消息。"
            )
            return messages

        except Exception as e:
            logger.error(f"从数据库获取最近消息失败: {e}", exc_info=True)
            return []

    async def get_latest_active_group(self, user_id: str) -> str | None:
        """
        查找指定用户最近活跃的群聊 ID。
        """
        try:
            from sqlmodel import select

            from .database import get_social_db_session
            from .models_db import QQMessage

            async for db_session in get_social_db_session():
                result = await db_session.exec(
                    select(QQMessage.session_id)
                    .where(QQMessage.sender_id == user_id)
                    .where(QQMessage.session_type == "group")
                    .order_by(QQMessage.timestamp.desc())
                    .limit(1)
                )
                first_result = result.first()
                if first_result:
                    return str(first_result)
                # 如果没有结果，继续循环还是直接返回？
                # 由于 get_social_db_session 是个生成器，我们只希望用第一个可用的 session 执行一次
                return None

            return None
        except Exception as e:
            logger.error(f"获取用户 {user_id} 最近活跃群组失败: {e}")
            return None

    async def handle_message(self, event: dict, agent_id: str = "pero"):
        """
        处理传入消息事件的主要入口点。
        """
        # 1. 解析事件
        try:
            msg_type = event.get("message_type")  # group 或 private
            self_id = str(event.get("self_id", ""))

            # [修复] 健壮的自身消息过滤
            # OneBot 实现可能会丢失 self_id 或以不同方式处理回环消息。
            # 我们同时使用 event['self_id'] 和我们全局存储的 bot_id。
            raw_user_id = event.get("user_id")
            sender_id = str(raw_user_id)

            is_self = (sender_id == self_id and self_id) or (
                self.bot_id and sender_id == self.bot_id
            )

            if is_self:
                logger.debug(
                    f"[SessionManager] 忽略自身消息。发送者: {sender_id}, BotID: {self.bot_id}"
                )
                return

            if msg_type == "group":
                session_id = str(event.get("group_id"))
                # sender_id 已在上方解析

                # 理想情况下从事件或 API 获取群名/发送者名称
                sender_name = event.get("sender", {}).get("nickname", "Unknown")
                # 群名并不总是在消息事件中，可能需要 API 或缓存
                session_name = f"Group {session_id}"
            elif msg_type == "private":
                session_id = str(event.get("user_id"))
                # sender_id 已在上方解析

                sender_name = event.get("sender", {}).get("nickname", "Unknown")
                if sender_name == "Unknown":
                    sender_name = f"User{sender_id}"
                session_name = sender_name
            else:
                return  # 忽略其他类型

            content = event.get("raw_message", "")
            msg_id = str(event.get("message_id"))

            # 提取图像
            images = []
            image_tasks = []

            message_chain = event.get("message", [])
            for segment in message_chain:
                if segment["type"] == "image":
                    url = segment["data"].get("url")
                    if url:
                        # [多模态] 开始异步下载
                        # 我们不在这里等待，以避免阻塞 WS 循环。
                        # 刷新逻辑将等待这些任务。
                        task = asyncio.create_task(
                            self.image_manager.download_image(url)
                        )
                        image_tasks.append(task)

                        # 我们可以暂时将 URL 存储在 images 中，
                        # 但当任务完成并处理后，它将被本地路径替换。
                        # 然而，SocialMessage.images 期望一个字符串列表。
                        # 让我们暂时追加 URL 作为回退/占位符。
                        images.append(url)

            # 创建消息对象
            msg = SocialMessage(
                msg_id=msg_id,
                sender_id=sender_id,
                sender_name=sender_name,
                content=content,
                timestamp=datetime.now(),
                raw_event=event,
                images=images,
                image_tasks=image_tasks,
            )

            # 获取会话 (多代理: 传递 agent_id)
            session = self.get_or_create_session(
                session_id, msg_type, session_name, agent_id=agent_id
            )

            # [Preemption] 检查并取消正在进行的秘书/主动搭话任务
            if session.active_response_task and not session.active_response_task.done():
                logger.info(
                    f"[{session_id}] 检测到用户新输入，正在打断之前的主动搭话任务..."
                )
                session.active_response_task.cancel()
                session.active_response_task = None

            # [动态扫描周期] 如果是私聊且有新消息，重置下一次扫描周期为短周期 (2-4分钟)
            if msg_type == "private":
                import random
                from datetime import timedelta

                # 设置为 2-4 分钟后
                next_scan = datetime.now() + timedelta(seconds=random.randint(120, 240))
                session.next_scan_time = next_scan
                logger.debug(
                    f"[{session_id}] 私聊活跃，下次主动审视时间重置为: {next_scan.strftime('%H:%M:%S')}"
                )

            # [持久化] 立即保存用户消息
            await self._persist_message(session, msg, "user")

            # 2. 检查触发器 (提及 / 状态)
            is_mentioned = self._check_is_mentioned(content, event)

            # [修复] 在私聊中，始终视为被提及
            if msg_type == "private":
                is_mentioned = True

            # [状态逻辑] 续订活跃状态或进入活跃状态
            if is_mentioned:
                # 进入或续订活跃状态
                session.last_active_time = datetime.now()
                logger.info(f"[{session_id}] 检测到提及！更新 last_active_time。")
            elif session.state == "active":
                # [续订] 活跃状态下的普通消息续订会话
                # 检查是否在窗口内 (例如 2 分钟)
                # 但由于我们处于活跃状态 (这由扫描循环中的 last_active_time 决定)，
                # 我们应该只更新它。
                # 双重检查：状态属性是否实时更新？
                # 目前状态在 flush_callback 或 scan_loop 中更新？
                # 实际上状态是会话的属性。
                # 让我们确保它保持活跃。
                session.last_active_time = datetime.now()
                logger.info(f"[{session_id}] 活跃会话被普通消息续订。")

            # 3. 添加到缓冲区
            session.add_message(msg)

            # 4. 确定动作
            # 如果已经被召唤/活跃，或被严格提及 -> 立即刷新？
            # 设计上说：“被召唤 -> 立即回复”。
            # “活跃” -> “更敏感”，可能是更短的缓冲区或立即？
            # 对于 MVP 第一阶段：提及 = 立即刷新。

            # [重构] 实现被召唤状态的累积缓冲区
            # 私聊: 7s, 群聊: 15s
            if is_mentioned:
                if session.state != "summoned":
                    # 首次提及：切换状态并启动固定计时器
                    session.state = "summoned"

                    # 根据会话类型确定缓冲区持续时间
                    buffer_duration = 7 if msg_type == "private" else 15

                    logger.info(
                        f"[{session_id}] 被提及唤醒 ({msg_type})！启动 {buffer_duration}秒 累积计时器。"
                    )

                    # 取消任何现有的非活跃计时器
                    if session.flush_timer_task:
                        session.flush_timer_task.cancel()

                    # 启动固定计时器
                    # 此计时器不会被后续消息重置，因为下面的状态检查
                    session.flush_timer_task = asyncio.create_task(
                        self._timer_callback(session, buffer_duration)
                    )
                else:
                    # 已经被召唤：什么都不做（累积）
                    logger.info(f"[{session_id}] 在累积期间再次被提及。继续等待。")

            elif len(session.buffer) >= self.BUFFER_MAX_SIZE:
                logger.info(f"[{session_id}] 缓冲区已满！")
                await self._trigger_flush(session, reason="buffer_full")
            else:
                # 普通消息
                if session.state == "summoned":
                    # 我们处于被召唤状态（等待 15s 计时器）。
                    # 不要重置计时器。让它累积。
                    pass
                else:
                    # 标准观察模式 -> 重置非活跃计时器 (20s)
                    self._reset_flush_timer(session)

        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}", exc_info=True)

    def _check_is_mentioned(self, content: str, event: dict) -> bool:
        # 检查 OneBot "at" 片段
        # raw_message 通常包含 CQ 码，如 [CQ:at,qq=123]
        # 但更简单的方法是检查 OneBot v11 中的 'message' 数组
        message_chain = event.get("message", [])
        for segment in message_chain:
            if segment["type"] == "at":
                # 检查是否 at 我
                # 我们需要 self_id。通常在 event['self_id'] 中
                self_id = str(event.get("self_id"))
                target_id = str(segment["data"].get("qq"))
                if target_id == self_id:
                    return True

        # 回退：检查关键词 (昵称)
        # if "pero" in content.lower() or "Pero" in content:
        #    return True

        return False

    def _reset_flush_timer(self, session: SocialSession, timeout: int = 20):
        # 取消现有计时器
        if session.flush_timer_task:
            session.flush_timer_task.cancel()

        # 创建新计时器
        session.flush_timer_task = asyncio.create_task(
            self._timer_callback(session, timeout)
        )

    async def _timer_callback(self, session: SocialSession, timeout: int):
        try:
            await asyncio.sleep(timeout)
            # 计时器过期
            # 根据状态检查原因
            reason = (
                "summon_timeout" if session.state == "summoned" else "buffer_timeout"
            )
            await self._trigger_flush(session, reason=reason)
        except asyncio.CancelledError:
            pass  # 计时器被重置或刷新

    async def _trigger_flush(self, session: SocialSession, reason: str):
        # 如果正在运行，取消计时器
        if session.flush_timer_task:
            session.flush_timer_task.cancel()
            session.flush_timer_task = None

        if not session.buffer:
            return

        logger.debug(
            f"[{session.session_id}] 正在刷新缓冲区。原因: {reason}。消息数: {len(session.buffer)}"
        )

        # 调用回调 (SocialService 逻辑)
        try:
            await self.flush_callback(session)
        except Exception as e:
            logger.error(f"刷新回调错误: {e}", exc_info=True)
        finally:
            # 刷新后始终清除缓冲区以避免重复
            session.clear_buffer()

    def get_active_sessions(
        self, limit: int = 5, session_type: Optional[str] = None
    ) -> list[SocialSession]:
        """
        获取活跃会话列表（按活跃时间倒序）。

        Args:
            limit: 返回数量限制
            session_type: 筛选类型 "group" 或 "private"。None 表示不筛选。
        """
        candidates = self.sessions.values()

        if session_type:
            candidates = [s for s in candidates if s.session_type == session_type]

        # 按 last_message_time 倒序排序 (寻找最近有消息的群，无论 Bot 是否参与)
        sorted_sessions = sorted(
            candidates, key=lambda s: s.last_message_time, reverse=True
        )
        return sorted_sessions[:limit]
