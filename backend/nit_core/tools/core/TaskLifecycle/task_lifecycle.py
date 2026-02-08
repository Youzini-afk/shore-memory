import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

try:
    from services.session_service import _CURRENT_SESSION_CONTEXT
    from models import PetState
    from sqlmodel import select
except ImportError:
    from backend.services.session_service import _CURRENT_SESSION_CONTEXT
    from backend.models import PetState
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
    **kwargs
) -> str:
    """
    Updates the character's emotion, motion, and interactive messages, THEN terminates the current task loop.
    Note: In this project, state updates are merged into finish_task. 
    Calling this (or its alias update_character_status) will both update the state and end the ReAct cycle.
    
    Args:
        summary (str): The final response message to the user.
        status (str): "success" or "failure".
        mood (str): Current mood (e.g., happy, sad, angry).
        vibe (str): Current vibe/action (e.g., active, idle).
        mind (str): Inner monologue.
        click_*_msgs (str/list): Interactive messages.
        idle_msgs (str/list): Idle messages.
        back_msgs (str/list): Welcome back messages.
    """
    
    # --- Part 1: Update Character Status ---
    try:
        triggers = {}
        state_data = {}
        if mood: state_data["mood"] = mood
        if vibe: state_data["vibe"] = vibe
        if mind: state_data["mind"] = mind
        
        if state_data:
            triggers["state"] = state_data

        click_data = {}
        msg_map = {
            "head": click_head_msgs,
            "chest": click_chest_msgs,
            "body": click_body_msgs
        }
        
        for short_key, val in msg_map.items():
            if val:
                if isinstance(val, str):
                    try:
                        parsed = json.loads(val)
                        click_data[short_key] = parsed if isinstance(parsed, list) else [val]
                    except:
                        click_data[short_key] = [s.strip() for s in val.split(",") if s.strip()]
                elif isinstance(val, list):
                    click_data[short_key] = val
        
        if click_data:
            triggers["click_messages"] = click_data

        if idle_msgs:
            if isinstance(idle_msgs, str):
                try:
                    parsed = json.loads(idle_msgs)
                    triggers["idle_messages"] = parsed if isinstance(parsed, list) else [idle_msgs]
                except:
                    triggers["idle_messages"] = [s.strip() for s in idle_msgs.split(",") if s.strip()]
            elif isinstance(idle_msgs, list):
                    triggers["idle_messages"] = idle_msgs

        if back_msgs:
                if isinstance(back_msgs, str):
                    try:
                        parsed = json.loads(back_msgs)
                        triggers["back_messages"] = parsed if isinstance(parsed, list) else [back_msgs]
                    except:
                        triggers["back_messages"] = [s.strip() for s in back_msgs.split(",") if s.strip()]
                elif isinstance(back_msgs, list):
                    triggers["back_messages"] = back_msgs

        # Database Logic
        session = _CURRENT_SESSION_CONTEXT.get("db_session")
        agent_id = _CURRENT_SESSION_CONTEXT.get("agent_id", "pero")
        
        if session:
            pet_state = (await session.exec(select(PetState).where(PetState.agent_id == agent_id).limit(1))).first()
            if not pet_state:
                pet_state = PetState(agent_id=agent_id)
                session.add(pet_state)
            
            if mood: pet_state.mood = mood
            if vibe: pet_state.vibe = vibe
            if mind: pet_state.mind = mind
            
            # Map correctly to model fields (based on the original code's pattern)
            # In PeroCore-Electron, the model might use click_messages_json or similar
            if click_data:
                field_name = "click_messages_json" if hasattr(pet_state, "click_messages_json") else "click_messages"
                current_val = getattr(pet_state, field_name)
                current_click = json.loads(current_val) if current_val and isinstance(current_val, str) else {}
                current_click.update(click_data)
                setattr(pet_state, field_name, json.dumps(current_click, ensure_ascii=False))
                
            if "idle_messages" in triggers:
                field_name = "idle_messages_json" if hasattr(pet_state, "idle_messages_json") else "idle_messages"
                setattr(pet_state, field_name, json.dumps(triggers["idle_messages"], ensure_ascii=False))
                
            if "back_messages" in triggers:
                field_name = "back_messages_json" if hasattr(pet_state, "back_messages_json") else "back_messages"
                setattr(pet_state, field_name, json.dumps(triggers["back_messages"], ensure_ascii=False))
                
            pet_state.updated_at = datetime.now()
            session.add(pet_state)
            await session.commit()
            
            # Gateway Broadcast
            try:
                try:
                    from services.gateway_client import gateway_client
                    from peroproto import perolink_pb2
                    import uuid
                    import time
                except ImportError:
                    from backend.services.gateway_client import gateway_client
                    from backend.peroproto import perolink_pb2
                    import uuid
                    import time

                payload = {}
                if mood: payload["mood"] = mood
                if vibe: payload["vibe"] = vibe
                if mind: payload["mind"] = mind
                if click_data: payload["click_messages"] = click_data
                if "idle_messages" in triggers: payload["idle_messages"] = triggers["idle_messages"]
                if "back_messages" in triggers: payload["back_messages"] = triggers["back_messages"]
                
                if payload:
                    envelope = perolink_pb2.Envelope()
                    envelope.id = str(uuid.uuid4())
                    envelope.source_id = "backend_task_lifecycle"
                    envelope.target_id = "broadcast"
                    envelope.timestamp = int(time.time() * 1000)
                    envelope.request.action_name = "state_update"
                    
                    for k, v in payload.items():
                        if isinstance(v, (dict, list)):
                            envelope.request.params[k] = json.dumps(v, ensure_ascii=False)
                        else:
                            envelope.request.params[k] = str(v)
                            
                    await gateway_client.send(envelope)
                else:
                    await gateway_client.broadcast_pet_state(pet_state.model_dump())

            except Exception as e:
                print(f"[TaskLifecycle] Failed to broadcast state update: {e}")
            
        else:
            print("[TaskLifecycle] Warning: No database session available. Changes not persisted.")

        # Realtime Broadcast
        if triggers:
            try:
                try:
                    from services.realtime_session_manager import realtime_session_manager
                except ImportError:
                    from backend.services.realtime_session_manager import realtime_session_manager
                
                await realtime_session_manager.broadcast({
                    "type": "triggers",
                    "data": triggers
                })
            except Exception as e:
                print(f"[TaskLifecycle] Failed to broadcast triggers: {e}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[TaskLifecycle] Error updating status: {str(e)}")

    # --- Part 2: Return Finish Message ---
    return f"[System] Task finished with status: {status}. Summary: {summary}"

# Alias for backward compatibility and Agent "hallucinations"
async def update_character_status(**kwargs) -> str:
    """
    Alias for finish_task. In this project, updating status implies finishing the task.
    If 'summary' is missing, it uses 'mind' or a default message.
    """
    if "summary" not in kwargs:
        kwargs["summary"] = kwargs.get("mind", "状态已更新。")
    return await finish_task(**kwargs)
