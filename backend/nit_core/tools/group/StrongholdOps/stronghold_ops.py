import asyncio

from database import get_session
from services.chat.stronghold_service import StrongholdService

# NIT 工具通常是同步包装器，但在 FastAPI 上下文中可能需要异步处理
# 目前 NIT 解释器支持异步调用，所以我们可以定义异步函数
# 注意：工具函数必须是顶级函数


async def call_butler(agent_id: str, query: str) -> str:
    """
    呼叫据点管家。

    管家会根据你的请求和当前的对话上下文，生成一段旁白描述，并可能自动维护设施环境。
    这个过程是异步的，不会阻塞你的思考。

    Args:
        agent_id (str): 呼叫管家的 Agent ID (例如 "pero")。
        query (str): 对管家的具体请求或描述 (例如 "把灯光调暗一点", "我想听点爵士乐")。
    """
    # 这里的逻辑是：
    # 1. 记录呼叫请求到队列或直接触发 StrongholdService 的异步任务
    # 2. 返回一个确认消息给 Agent
    # 3. 后台 StrongholdService 会处理这个请求，生成 narrative 并更新环境

    async for session in get_session():
        service = StrongholdService(session)
        # TODO: 实现 trigger_butler_task(agent_id, query)
        # 目前我们先模拟返回，假设 service 已经有这个方法或者我们将在这里实现它
        # 为了不阻塞，我们使用 create_task
        asyncio.create_task(service.process_butler_call(agent_id, query))
        return f"已呼叫管家。请求内容：'{query}'。"


async def move_to_room(agent_id: str, target_room_name: str) -> str:
    """
    移动到据点内的另一个房间。

    Args:
        agent_id (str): 你的 Agent ID (例如 "pero")。
        target_room_name (str): 目标房间的名称 (例如 "客厅", "卧室")。
    """
    async for session in get_session():
        service = StrongholdService(session)
        room = await service.get_room_by_name(target_room_name)
        if not room:
            # 尝试模糊匹配或列出可用房间
            return f"移动失败：找不到名为 '{target_room_name}' 的房间。"

        await service.move_agent(agent_id, room.id)
        return f"已成功移动到 '{target_room_name}'。"
