"""
External Plugin Registry Service
=================================
允许外部进程通过 HTTP Webhook 注册为 PeroCore 插件。
外部插件可以订阅 EventBus 事件（Hook），也可以提供独立的 HTTP 端点。

架构：
  外部插件进程 (独立 FastAPI/Flask/etc.)
       │
       │  POST /api/plugins/register
       ▼
  ExternalPluginRegistry (本模块)
       │
       ├─ 订阅 EventBus 事件 → 代理转发给外部插件 (HTTP Webhook)
       ├─ 定期心跳检查 → 自动清理离线插件
       └─ 提供查询/管理接口
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx

from core.event_bus import EventBus

logger = logging.getLogger("pero.external_plugin")


@dataclass
class ExternalPluginInfo:
    """一个已注册的外部插件的描述"""

    plugin_id: str
    name: str
    url: str  # 插件的 HTTP 基地址 (如 http://localhost:9527)
    description: str = ""
    version: str = "0.0.1"

    # 订阅的 EventBus Hook 事件（pre-hook 可修改 ctx）
    hooks: List[str] = field(default_factory=list)

    # 仅监听事件（只通知，不可修改 ctx）
    events: List[str] = field(default_factory=list)

    # 注册时间
    registered_at: float = field(default_factory=time.time)

    # 最后一次心跳成功时间
    last_heartbeat: float = field(default_factory=time.time)

    # 插件是否在线
    online: bool = True


class ExternalPluginRegistry:
    """
    外部插件注册表。
    管理外部进程插件的注册、事件代理、心跳检测。
    """

    def __init__(self, webhook_timeout: float = 5.0, heartbeat_interval: float = 30.0):
        self._plugins: Dict[str, ExternalPluginInfo] = {}
        self._proxy_handlers: Dict[str, List[Callable]] = {}  # event -> [proxy_handler]
        self._webhook_timeout = webhook_timeout
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self._webhook_timeout)
        return self._http_client

    # ─── 注册 / 注销 ───

    async def register(self, plugin_data: Dict[str, Any]) -> ExternalPluginInfo:
        """
        注册一个外部插件。
        如果同 plugin_id 已存在，先注销旧的再重新注册（支持热重载）。
        """
        plugin_id = plugin_data["plugin_id"]

        # 如果已存在，先注销
        if plugin_id in self._plugins:
            logger.info(f"[ExternalPlugin] 插件 {plugin_id} 已存在，正在热重载...")
            await self.unregister(plugin_id)

        plugin = ExternalPluginInfo(
            plugin_id=plugin_data["plugin_id"],
            name=plugin_data.get("name", plugin_id),
            url=plugin_data["url"].rstrip("/"),
            description=plugin_data.get("description", ""),
            version=plugin_data.get("version", "0.0.1"),
            hooks=plugin_data.get("hooks", []),
            events=plugin_data.get("events", []),
        )

        self._plugins[plugin_id] = plugin

        # 注册 EventBus 代理
        await self._register_event_proxies(plugin)

        # 启动心跳（如果还没启动）
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(
            f"[ExternalPlugin] ✔ 注册成功: {plugin.name} ({plugin_id}) "
            f"@ {plugin.url} | hooks={plugin.hooks}, events={plugin.events}"
        )
        return plugin

    async def unregister(self, plugin_id: str) -> bool:
        """注销一个外部插件，同时移除其 EventBus 代理"""
        plugin = self._plugins.pop(plugin_id, None)
        if not plugin:
            return False

        # 移除该插件的所有 EventBus 代理
        for event_name, handlers in list(self._proxy_handlers.items()):
            for handler in handlers[:]:
                if getattr(handler, "_plugin_id", None) == plugin_id:
                    EventBus.unsubscribe(event_name, handler)
                    handlers.remove(handler)

        logger.info(f"[ExternalPlugin] ✖ 已注销: {plugin.name} ({plugin_id})")
        return True

    # ─── EventBus 代理 ───

    async def _register_event_proxies(self, plugin: ExternalPluginInfo):
        """为插件的 hooks 和 events 创建 EventBus 代理处理器"""

        # hooks: 可修改 ctx 的 pre-hook
        for event_name in plugin.hooks:
            handler = self._make_hook_proxy(plugin, event_name)
            EventBus.subscribe(event_name, handler)
            self._proxy_handlers.setdefault(event_name, []).append(handler)

        # events: 只通知，不可修改 ctx（fire-and-forget）
        for event_name in plugin.events:
            handler = self._make_event_proxy(plugin, event_name)
            EventBus.subscribe(event_name, handler)
            self._proxy_handlers.setdefault(event_name, []).append(handler)

    def _make_hook_proxy(self, plugin: ExternalPluginInfo, event_name: str) -> Callable:
        """
        创建 Hook 代理：调用外部插件并将返回的 ctx 修改合并回主流程。
        外部插件应返回 {"ctx": {modified fields...}}
        """

        async def proxy_handler(ctx, **kwargs):
            if not plugin.online:
                return

            url = f"{plugin.url}/hook/{event_name}"
            try:
                serializable_ctx = _make_serializable(ctx)
                resp = await self.http_client.post(url, json={"ctx": serializable_ctx})

                if resp.status_code == 200:
                    data = resp.json()
                    returned_ctx = data.get("ctx")
                    if returned_ctx and isinstance(returned_ctx, dict):
                        for key, value in returned_ctx.items():
                            if key in ctx:
                                ctx[key] = value
                elif resp.status_code == 204:
                    pass  # 插件选择不修改
                else:
                    logger.warning(
                        f"[ExternalPlugin] Hook {event_name} -> {plugin.name}: "
                        f"HTTP {resp.status_code}"
                    )
            except httpx.ConnectError:
                logger.warning(
                    f"[ExternalPlugin] 插件 {plugin.name} 连接失败，标记为离线"
                )
                plugin.online = False
            except Exception as e:
                logger.error(
                    f"[ExternalPlugin] Hook {event_name} -> {plugin.name} 失败: {e}"
                )

        proxy_handler._plugin_id = plugin.plugin_id
        proxy_handler.__name__ = f"hook_proxy_{plugin.plugin_id}_{event_name}"
        return proxy_handler

    def _make_event_proxy(
        self, plugin: ExternalPluginInfo, event_name: str
    ) -> Callable:
        """创建只读事件代理：通知外部插件但不等待/不合并返回值（fire-and-forget）。"""

        async def proxy_handler(ctx=None, **kwargs):
            if not plugin.online:
                return

            url = f"{plugin.url}/event/{event_name}"
            try:
                serializable_ctx = _make_serializable(ctx) if ctx else {}
                asyncio.create_task(
                    self._fire_event(url, serializable_ctx, plugin.name, event_name)
                )
            except Exception as e:
                logger.error(
                    f"[ExternalPlugin] Event {event_name} -> {plugin.name} 失败: {e}"
                )

        proxy_handler._plugin_id = plugin.plugin_id
        proxy_handler.__name__ = f"event_proxy_{plugin.plugin_id}_{event_name}"
        return proxy_handler

    async def _fire_event(self, url: str, ctx: dict, plugin_name: str, event_name: str):
        """异步发送事件通知（不阻塞主流程）"""
        try:
            await self.http_client.post(url, json={"ctx": ctx})
        except httpx.ConnectError:
            logger.debug(f"[ExternalPlugin] Event -> {plugin_name} 连接失败")
        except Exception as e:
            logger.debug(f"[ExternalPlugin] Event {event_name} -> {plugin_name}: {e}")

    # ─── 心跳检测 ───

    async def _heartbeat_loop(self):
        """定期检测所有已注册插件的健康状态"""
        while self._plugins:
            await asyncio.sleep(self._heartbeat_interval)

            for plugin in list(self._plugins.values()):
                try:
                    resp = await self.http_client.get(
                        f"{plugin.url}/health", timeout=3.0
                    )
                    if resp.status_code == 200:
                        plugin.online = True
                        plugin.last_heartbeat = time.time()
                    else:
                        plugin.online = False
                except Exception:
                    if plugin.online:
                        logger.warning(
                            f"[ExternalPlugin] 插件 {plugin.name} 心跳失败，标记为离线"
                        )
                    plugin.online = False

        logger.info("[ExternalPlugin] 无注册插件，心跳循环退出。")

    # ─── 查询接口 ───

    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有已注册的外部插件"""
        return [
            {
                "plugin_id": p.plugin_id,
                "name": p.name,
                "url": p.url,
                "description": p.description,
                "version": p.version,
                "hooks": p.hooks,
                "events": p.events,
                "online": p.online,
                "registered_at": p.registered_at,
                "last_heartbeat": p.last_heartbeat,
            }
            for p in self._plugins.values()
        ]

    def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """获取单个插件信息"""
        p = self._plugins.get(plugin_id)
        if not p:
            return None
        return {
            "plugin_id": p.plugin_id,
            "name": p.name,
            "url": p.url,
            "description": p.description,
            "version": p.version,
            "hooks": p.hooks,
            "events": p.events,
            "online": p.online,
            "registered_at": p.registered_at,
            "last_heartbeat": p.last_heartbeat,
        }

    async def shutdown(self):
        """优雅关闭"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        logger.info("[ExternalPlugin] 已关闭。")


# ─── 工具函数 ───


def _make_serializable(obj: Any) -> Any:
    """将 ctx 中不可 JSON 序列化的对象转为字符串"""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


# ─── 全局单例 ───

_registry_instance: Optional[ExternalPluginRegistry] = None


def get_external_plugin_registry() -> ExternalPluginRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ExternalPluginRegistry()
    return _registry_instance
