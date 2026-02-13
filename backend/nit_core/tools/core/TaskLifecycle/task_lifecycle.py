import json
from datetime import datetime
from typing import List, Union

try:
    from sqlmodel import select

    from models import PetState
    from services.core.session_service import _CURRENT_SESSION_CONTEXT
except ImportError:
    from backend.models import PetState
    from backend.services.core.session_service import _CURRENT_SESSION_CONTEXT
    from sqlmodel import select


async def finish_task(
    summary: str,
    status: str = "success",
    mood: str = None,
    vibe: str = None,
    mind: str = None,
    click_head_msgs: Union[str, List[str]] = None,
    click_chest_msgs: Union[str, List[str]] = None,
    click_body_msgs: Union[str, List[str]] = None,
    idle_msgs: Union[str, List[str]] = None,
    back_msgs: Union[str, List[str]] = None,
    **kwargs,
) -> str:
    """
    更新角色的情绪、动作和交互消息，然后终止当前任务循环。
    注意：在该项目中，状态更新已合并到 finish_task 中。
    调用此函数（或其别名 update_character_status）将同时更新状态并结束 ReAct 循环。

    Args:
        summary (str): 给用户的最终响应消息。
        status (str): "success" 或 "failure"。
        mood (str): 当前情绪 (例如 happy, sad, angry)。
        vibe (str): 当前氛围/动作 (例如 active, idle)。
        mind (str): 内心独白。
        click_*_msgs (str/list): 交互消息。
        idle_msgs (str/list): 闲置消息。
        back_msgs (str/list): 欢迎回来消息。
    """

    # --- 第一部分：更新角色状态 ---
    try:
        triggers = {}
        state_data = {}
        if mood:
            state_data["mood"] = mood
        if vibe:
            state_data["vibe"] = vibe
        if mind:
            state_data["mind"] = mind

        if state_data:
            triggers["state"] = state_data

        click_data = {}
        msg_map = {
            "head": click_head_msgs,
            "chest": click_chest_msgs,
            "body": click_body_msgs,
        }

        for short_key, val in msg_map.items():
            if val:
                if isinstance(val, str):
                    try:
                        parsed = json.loads(val)
                        click_data[short_key] = (
                            parsed if isinstance(parsed, list) else [val]
                        )
                    except Exception:
                        click_data[short_key] = [
                            s.strip() for s in val.split(",") if s.strip()
                        ]
                elif isinstance(val, list):
                    click_data[short_key] = val

        if click_data:
            triggers["click_messages"] = click_data

        if idle_msgs:
            if isinstance(idle_msgs, str):
                try:
                    parsed = json.loads(idle_msgs)
                    triggers["idle_messages"] = (
                        parsed if isinstance(parsed, list) else [idle_msgs]
                    )
                except Exception:
                    triggers["idle_messages"] = [
                        s.strip() for s in idle_msgs.split(",") if s.strip()
                    ]
            elif isinstance(idle_msgs, list):
                triggers["idle_messages"] = idle_msgs

        if back_msgs:
            if isinstance(back_msgs, str):
                try:
                    parsed = json.loads(back_msgs)
                    triggers["back_messages"] = (
                        parsed if isinstance(parsed, list) else [back_msgs]
                    )
                except Exception:
                    triggers["back_messages"] = [
                        s.strip() for s in back_msgs.split(",") if s.strip()
                    ]
            elif isinstance(back_msgs, list):
                triggers["back_messages"] = back_msgs

        # 数据库逻辑
        session = _CURRENT_SESSION_CONTEXT.get("db_session")
        agent_id = _CURRENT_SESSION_CONTEXT.get("agent_id", "pero")

        if session:
            pet_state = (
                await session.exec(
                    select(PetState).where(PetState.agent_id == agent_id).limit(1)
                )
            ).first()
            if not pet_state:
                pet_state = PetState(agent_id=agent_id)
                session.add(pet_state)

            if mood:
                pet_state.mood = mood
            if vibe:
                pet_state.vibe = vibe
            if mind:
                pet_state.mind = mind

            # 正确映射到模型字段（基于原始代码模式）
            # 在 ProjectRoot 中，模型可能使用 click_messages_json 或类似字段
            if click_data:
                field_name = (
                    "click_messages_json"
                    if hasattr(pet_state, "click_messages_json")
                    else "click_messages"
                )
                current_val = getattr(pet_state, field_name)
                current_click = (
                    json.loads(current_val)
                    if current_val and isinstance(current_val, str)
                    else {}
                )
                current_click.update(click_data)
                setattr(
                    pet_state, field_name, json.dumps(current_click, ensure_ascii=False)
                )

            if "idle_messages" in triggers:
                field_name = (
                    "idle_messages_json"
                    if hasattr(pet_state, "idle_messages_json")
                    else "idle_messages"
                )
                setattr(
                    pet_state,
                    field_name,
                    json.dumps(triggers["idle_messages"], ensure_ascii=False),
                )

            if "back_messages" in triggers:
                field_name = (
                    "back_messages_json"
                    if hasattr(pet_state, "back_messages_json")
                    else "back_messages"
                )
                setattr(
                    pet_state,
                    field_name,
                    json.dumps(triggers["back_messages"], ensure_ascii=False),
                )

            pet_state.updated_at = datetime.now()
            session.add(pet_state)
            await session.commit()

            # 网关广播
            try:
                try:
                    import time
                    import uuid

                    from peroproto import perolink_pb2
                    from services.core.gateway_client import gateway_client
                except ImportError:
                    import time
                    import uuid

                    from backend.peroproto import perolink_pb2
                    from backend.services.core.gateway_client import gateway_client

                payload = {}
                if mood:
                    payload["mood"] = mood
                if vibe:
                    payload["vibe"] = vibe
                if mind:
                    payload["mind"] = mind
                if click_data:
                    payload["click_messages"] = click_data
                if "idle_messages" in triggers:
                    payload["idle_messages"] = triggers["idle_messages"]
                if "back_messages" in triggers:
                    payload["back_messages"] = triggers["back_messages"]

                if payload:
                    envelope = perolink_pb2.Envelope()
                    envelope.id = str(uuid.uuid4())
                    envelope.source_id = "backend_task_lifecycle"
                    envelope.target_id = "broadcast"
                    envelope.timestamp = int(time.time() * 1000)
                    envelope.request.action_name = "state_update"

                    for k, v in payload.items():
                        if isinstance(v, (dict, list)):
                            envelope.request.params[k] = json.dumps(
                                v, ensure_ascii=False
                            )
                        else:
                            envelope.request.params[k] = str(v)

                    await gateway_client.send(envelope)
                else:
                    await gateway_client.broadcast_pet_state(pet_state.model_dump())

            except Exception as e:
                print(f"[TaskLifecycle] 广播状态更新失败: {e}")

        else:
            print(
                "[TaskLifecycle] 警告: 无可用数据库会话。更改未持久化。"
            )

        # 实时广播
        if triggers:
            try:
                try:
                    from services.core.realtime_session_manager import (
                        realtime_session_manager,
                    )
                except ImportError:
                    from backend.services.core.realtime_session_manager import (
                        realtime_session_manager,
                    )

                await realtime_session_manager.broadcast(
                    {"type": "triggers", "data": triggers}
                )
            except Exception as e:
                print(f"[TaskLifecycle] 广播触发器失败: {e}")

    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"[TaskLifecycle] 更新状态错误: {str(e)}")

    # --- 第二部分：返回完成消息 ---
    return f"[System] 任务已完成，状态: {status}。摘要: {summary}"


# 向后兼容和 Agent "幻觉" 的别名
async def update_character_status(**kwargs) -> str:
    """
    finish_task 的别名。在该项目中，更新状态意味着完成任务。
    如果缺少 'summary'，则使用 'mind' 或默认消息。
    """
    if "summary" not in kwargs:
        kwargs["summary"] = kwargs.get("mind", "状态已更新。")
    return await finish_task(**kwargs)
