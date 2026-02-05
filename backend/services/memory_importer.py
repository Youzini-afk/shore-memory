import json
import logging
from typing import List, Dict, Any, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from services.mdp.manager import mdp
from services.llm_service import LLMService
from services.memory_service import MemoryService
from services.agent_service import AgentService

logger = logging.getLogger(__name__)

class MemoryImporter:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_story(self, story_text: str, agent_id: str = "pero") -> Dict[str, Any]:
        """
        Import a long story, split it into events using LLM, and save to memory.
        """
        if not story_text or len(story_text.strip()) == 0:
             return {"success": False, "message": "Story text is empty."}

        # 1. Prepare Prompt
        print(f"[MemoryImporter] 正在处理故事导入 (Agent: {agent_id})...")
        prompt = mdp.render("tasks/memory/story_extract", {"story": story_text})
        
        # 2. Call LLM
        agent_service = AgentService(self.session)
        try:
            llm_config = await agent_service._get_llm_config()
        except Exception as e:
            return {"success": False, "message": f"Failed to get LLM config: {e}"}
        
        llm = LLMService(
            api_key=llm_config.get("api_key"),
            api_base=llm_config.get("api_base"),
            model=llm_config.get("model")
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            print("[MemoryImporter] 调用 LLM 进行事件拆解...")
            response = await llm.chat(messages, temperature=0.3) # Low temp for structured output
            content = response["choices"][0]["message"]["content"]
            
            # Clean JSON
            json_str = content.strip()
            
            # Remove Markdown code blocks if present (more robust)
            import re
            json_match = re.search(r'\[\s*\{.*\}\s*\]', json_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Fallback to existing cleaning logic if regex fails to find a list
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                elif json_str.startswith("```"):
                    json_str = json_str[3:]
                
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
            
            json_str = json_str.strip()
            
            try:
                events = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback: try to find the first '[' and last ']'
                start = json_str.find('[')
                end = json_str.rfind(']')
                if start != -1 and end != -1:
                    json_str = json_str[start:end+1]
                    events = json.loads(json_str)
                else:
                    raise ValueError("Failed to parse JSON response from LLM")

            if not isinstance(events, list):
                # Try to find list inside specific keys
                if isinstance(events, dict):
                    for key in ["events", "items", "memories"]:
                        if key in events and isinstance(events[key], list):
                            events = events[key]
                            break
                    else:
                         raise ValueError("Output JSON is not a list and contains no list wrapper.")
                else:
                    raise ValueError("Output is not a list")
            
            print(f"[MemoryImporter] 提取到 {len(events)} 个事件。开始入库...")
            
            # 3. Save to Memory
            saved_count = 0
            for event in events:
                # Extract fields with safe defaults
                content = event.get("content")
                if not content: continue
                
                tags = event.get("tags", "")
                if isinstance(tags, list):
                    tags = ",".join(tags)
                
                # Convert importance to int safely
                try:
                    importance = int(event.get("importance", 1))
                except:
                    importance = 1
                
                memory_type = event.get("type", "event")
                
                # Use timestamp_hint if we want to store it in metadata or log it
                # Currently MemoryService doesn't support custom timestamp overrides easily 
                # (it uses realTime=now, timestamp=now).
                # But sequential saving preserves the logical chain (prev_id/next_id).
                # We can append hint to tags or content if needed.
                timestamp_hint = event.get("timestamp_hint")
                if timestamp_hint:
                    # Append to tags for searchability
                    tags = f"{tags},Time:{timestamp_hint}" if tags else f"Time:{timestamp_hint}"

                await MemoryService.save_memory(
                    session=self.session,
                    content=content,
                    tags=tags,
                    importance=importance,
                    memory_type=memory_type,
                    agent_id=agent_id
                )
                saved_count += 1
                
            print(f"[MemoryImporter] 导入完成。共保存 {saved_count} 条记忆。")
            return {
                "success": True,
                "message": f"Successfully imported {saved_count} events.",
                "count": saved_count
            }
            
        except Exception as e:
            logger.error(f"Story import failed: {e}")
            return {
                "success": False,
                "message": str(e)
            }
