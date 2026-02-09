import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentProfile:
    """
    表示已加载的代理配置文件。
    """

    id: str
    name: str
    description: str = ""
    work_custom_persona: str = ""
    work_traits: List[str] = field(default_factory=list)
    social_custom_persona: str = ""
    social_traits: List[str] = field(default_factory=list)
    model_config: Dict[str, Any] = field(default_factory=dict)
    social_binding: Dict[str, Any] = field(default_factory=dict)
    config_path: str = ""
    prompt_path: str = ""
    tool_policies: Dict[str, Any] = field(default_factory=dict)
    use_stickers: bool = False


class AgentManager:
    """
    管理代理的生命周期、配置和发现。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 代理的基础目录 (内置)
        self.agents_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "mdp", "agents")
        )

        # 用户自定义代理目录: 优先使用环境变量
        data_dir = os.environ.get(
            "PERO_DATA_DIR",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")),
        )
        self.user_agents_dir = os.path.join(data_dir, "agents")

        self.agents: Dict[str, AgentProfile] = {}
        self.active_agent_id: str = "pero"  # 默认活跃代理
        self.enabled_agents: set[str] = set()  # 已启用代理 ID 集合

        self.reload_agents()

        # 从文件加载启动配置
        try:
            config_path = os.path.join(data_dir, "agent_launch_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    launch_config = json.load(f)
                    enabled = launch_config.get("enabled_agents", [])
                    active = launch_config.get("active_agent")

                    if enabled:
                        valid_enabled = [aid for aid in enabled if aid in self.agents]
                        self.enabled_agents = set(valid_enabled)
                        logger.info(
                            f"从启动配置加载已启用的代理: {self.enabled_agents}"
                        )

                    if active and active in self.agents:
                        self.active_agent_id = active
                        logger.info(f"从启动配置加载活跃代理: {active}")
            else:
                logger.info("未找到代理启动配置，使用默认设置。")
                self.enabled_agents = set(self.agents.keys())
        except Exception as e:
            logger.error(f"加载代理启动配置失败: {e}")
            self.enabled_agents = set(self.agents.keys())

        # 回退：如果配置为空或无效，确保默认值
        if not self.enabled_agents and self.agents:
            self.enabled_agents = set(self.agents.keys())

        self._initialized = True

    def reload_agents(self):
        """扫描代理目录并加载所有配置。"""
        self.agents.clear()

        # 1. 加载内置代理
        if not os.path.exists(self.agents_dir):
            logger.warning(f"内置代理目录未找到: {self.agents_dir}")
        else:
            self._scan_and_load_agents(self.agents_dir, is_user_dir=False)

        # 2. 加载用户自定义代理 (可覆盖内置)
        if not os.path.exists(self.user_agents_dir):
            try:
                os.makedirs(self.user_agents_dir)
                logger.info(f"已初始化用户代理目录: {self.user_agents_dir}")
            except Exception as e:
                logger.warning(f"无法创建用户代理目录: {e}")
        else:
            self._scan_and_load_agents(self.user_agents_dir, is_user_dir=True)

        if not self.agents:
            logger.warning("未加载任何代理！请检查 backend/agents 或用户数据目录。")

        # 确保活跃代理在列表中
        if self.active_agent_id not in self.agents and self.agents:
            self.active_agent_id = next(iter(self.agents))

    def _scan_and_load_agents(self, base_dir: str, is_user_dir: bool = False):
        """扫描指定目录下的代理"""
        logger.info(
            f"正在扫描代理目录 ({'User' if is_user_dir else 'Builtin'}): {base_dir}"
        )
        for entry in os.scandir(base_dir):
            if entry.is_dir():
                agent_id = entry.name.lower()
                config_path = os.path.join(entry.path, "config.json")
                prompt_path = os.path.join(entry.path, "system_prompt.md")

                if os.path.exists(config_path):
                    try:
                        profile = self._load_agent_config(
                            agent_id, config_path, prompt_path
                        )
                        self.agents[agent_id] = profile
                        logger.info(
                            f"已加载代理: {profile.name} ({agent_id}) [{'User' if is_user_dir else 'Builtin'}]"
                        )
                    except Exception as e:
                        logger.error(f"加载代理 {agent_id} 失败: {e}")

    def _load_agent_config(
        self, agent_id: str, config_path: str, prompt_path: str
    ) -> AgentProfile:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        agent_dir = os.path.dirname(config_path)

        # 加载人设内容的辅助函数
        def load_persona(type_key: str, legacy_key: str) -> str:
            # 首先尝试从文件加载
            personas = config.get("personas", {})
            if type_key in personas:
                rel_path = personas[type_key]
                abs_path = os.path.join(agent_dir, rel_path)
                try:
                    if os.path.exists(abs_path):
                        with open(abs_path, "r", encoding="utf-8") as pf:
                            return pf.read()
                    else:
                        logger.warning(f"人设文件未找到: {abs_path}")
                except Exception as e:
                    logger.error(f"读取人设文件 {abs_path} 错误: {e}")

            # 回退到配置中的旧键
            return config.get(legacy_key, "")

        work_persona = load_persona("work", "work_custom_persona")
        social_persona = load_persona("social", "social_custom_persona")

        # 处理特征 (兼容新旧结构)
        traits = config.get("traits", {})
        work_traits = traits.get("work", config.get("work_traits", []))
        social_traits = traits.get("social", config.get("social_traits", []))

        social_binding = config.get("social", {})
        use_stickers = social_binding.get("use_stickers", False)

        return AgentProfile(
            id=agent_id,
            name=config.get("name", agent_id.capitalize()),
            description=config.get("description", ""),
            work_custom_persona=work_persona,
            work_traits=work_traits,
            social_custom_persona=social_persona,
            social_traits=social_traits,
            model_config=config.get("model_config", {}),
            social_binding=config.get("social", {}),  # Updated to read 'social' block
            config_path=config_path,
            prompt_path=prompt_path,
            tool_policies=config.get("tool_policies", {}),
            use_stickers=use_stickers,
        )

    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        return self.agents.get(agent_id.lower())

    def get_active_agent(self) -> Optional[AgentProfile]:
        return self.agents.get(self.active_agent_id)

    def set_active_agent(self, agent_id: str) -> bool:
        if agent_id.lower() in self.agents:
            self.active_agent_id = agent_id.lower()
            logger.info(f"已切换活跃代理为: {agent_id}")

            # 广播变更
            self._broadcast_agent_change(self.active_agent_id)
            # [修复] 立即广播状态以更新 UI (状态栏)
            self._broadcast_current_state(self.active_agent_id)

            return True
        logger.warning(f"无法切换到未知代理: {agent_id}")
        return False

    def _broadcast_current_state(self, agent_id: str):
        """广播代理当前的 PetState"""
        try:
            import asyncio

            from sqlalchemy.orm import sessionmaker
            from sqlmodel import desc, select
            from sqlmodel.ext.asyncio.session import AsyncSession

            from database import engine
            from models import PetState
            from services.gateway_client import gateway_client

            async def _do_broadcast():
                try:
                    # 创建临时会话以获取状态
                    async_session = sessionmaker(
                        engine, class_=AsyncSession, expire_on_commit=False
                    )
                    async with async_session() as session:
                        # 获取该代理的最新状态
                        stmt = (
                            select(PetState)
                            .where(PetState.agent_id == agent_id)
                            .order_by(desc(PetState.updated_at))
                            .limit(1)
                        )
                        state = (await session.exec(stmt)).first()

                        state_dict = {}
                        if state:
                            state_dict = {
                                "mood": state.mood,
                                "vibe": state.vibe,
                                "mind": state.mind,
                            }
                        else:
                            # 如果未找到则使用默认状态
                            state_dict = {
                                "mood": "happy",
                                "vibe": "active",
                                "mind": "...",
                            }

                        await gateway_client.broadcast_pet_state(state_dict)
                except Exception as e:
                    logger.error(f"Failed to fetch/broadcast agent state: {e}")

            # Schedule the task
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_do_broadcast())
            except RuntimeError:
                # 如果没有运行循环（在此上下文中很少见），我们可能会跳过或同步运行？
                # 但数据库访问是异步的。
                pass

        except Exception as e:
            logger.error(f"广播代理状态失败: {e}")

    def _broadcast_agent_change(self, agent_id: str):
        """Broadcast agent change event"""
        try:
            import asyncio
            import time
            import uuid

            from peroproto import perolink_pb2
            from services.gateway_client import gateway_client

            async def _send():
                envelope = perolink_pb2.Envelope()
                envelope.id = str(uuid.uuid4())
                envelope.source_id = "agent_manager"
                envelope.target_id = "broadcast"
                envelope.timestamp = int(time.time() * 1000)

                envelope.request.action_name = "agent_changed"
                envelope.request.params["agent_id"] = agent_id

                await gateway_client.send(envelope)

            # 检查是否有正在运行的循环
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_send())
            except RuntimeError:
                asyncio.run(_send())
        except Exception as e:
            logger.error(f"广播代理变更失败: {e}")

    def set_enabled_agents(self, agent_ids: List[str]):
        """设置已启用的代理列表。"""
        valid_ids = [aid.lower() for aid in agent_ids if aid.lower() in self.agents]
        self.enabled_agents = set(valid_ids)
        logger.info(f"已启用代理更新: {self.enabled_agents}")

        # 如果活跃代理不在启用列表中，警告或切换？
        # 目前仅警告，因为用户可能是在为未来配置。
        if self.active_agent_id not in self.enabled_agents and self.enabled_agents:
            logger.warning(f"活跃代理 {self.active_agent_id} 不在启用列表中！")

    def get_enabled_agents(self) -> List[str]:
        return list(self.enabled_agents)

    def is_agent_enabled(self, agent_id: str) -> bool:
        return agent_id.lower() in self.enabled_agents

    def list_agents(self) -> List[Dict[str, Any]]:
        # 防御性编程：如果未加载代理，尝试重新加载一次
        if not self.agents:
            logger.info("内存中未找到代理，尝试重新加载...")
            self.reload_agents()
            # 如果仍然为空，确保 enabled_agents 也被清除以避免不一致
            if not self.agents:
                self.enabled_agents.clear()
            else:
                # 如果已加载，且没有启用任何代理，则默认启用所有 (首次运行场景)
                if not self.enabled_agents:
                    self.enabled_agents = set(self.agents.keys())

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "is_active": p.id == self.active_agent_id,
                "is_enabled": p.id in self.enabled_agents,
            }
            for p in self.agents.values()
        ]


# 全局实例访问器
_agent_manager_instance = None


def get_agent_manager() -> AgentManager:
    global _agent_manager_instance
    if _agent_manager_instance is None:
        _agent_manager_instance = AgentManager()
    return _agent_manager_instance
