"""
AuraVision Service - 视觉意图感知服务(V3.0多模态版)

使用Rust原生推理引擎实现早期链路，加上 TriviumDB 接管后期记忆检索:
- 视觉编码 -> 384D 向量 (pero_vision_core)
- EMA 时序平滑 (pero_vision_core)
- 意图锚点匹配 (TriviumDB)
- 扩散激活记忆唤醒 (TriviumDB Graph)
- 上下文饱和度检测 (Python)

版本: 3.1.0 (TriviumDB-Powered)
"""

import asyncio
import base64
import json
import os
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from loguru import logger

from services.mdp.manager import mdp
from services.memory.trivium_store import trivium_store
from services.perception.screenshot_service import screenshot_manager

# 多模态协调器(V3.0)
try:
    from services.perception.multimodal_trigger_service import (
        TriggerMode,
        multimodal_coordinator,
    )

    MULTIMODAL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[AuraVision] 多模态协调器不可用: {e}")
    MULTIMODAL_AVAILABLE = False
    multimodal_coordinator = None

# 尝试导入Rust核心模块 (仅包含视频预处理和ONNX编码)
try:
    from pero_vision_core import VisionEncoderManager

    RUST_VISION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[AuraVision] Rust 视觉模块不可用: {e}")
    RUST_VISION_AVAILABLE = False
    VisionEncoderManager = None


class VisionProcessResult:
    def __init__(
        self,
        triggered: bool,
        top_anchor_id: int,
        top_similarity: float,
        top_description: str,
        activated_memory_ids: List[int],
        saturation: float,
    ):
        self.triggered = triggered
        self.top_anchor_id = top_anchor_id
        self.top_similarity = top_similarity
        self.top_description = top_description
        self.activated_memory_ids = activated_memory_ids
        self.saturation = saturation


class AuraVisionService:
    """视觉意图感知服务：截屏脱敏编码(Rust) -> 锚点匹配与记忆唤醒(TriviumDB)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.is_running = False
        self.manager: Optional[VisionEncoderManager] = None

        # 直接复用主记忆库：视觉锚点本就是角色的记忆节点
        self.trivium_store = trivium_store

        # 数据状态缓存
        self.recent_activated_ids: List[int] = []

        # 模型路径
        self.model_path = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "models",
            "AuraVision",
            "weights",
            "auravision_v1.onnx",
        )

        # 旧版锚点数据路径 (用于兼容迁移)
        base_dir = os.environ.get(
            "PERO_DATA_DIR",
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
        )
        self.legacy_anchors_path = os.path.join(
            base_dir, "data", "rust_db", "intent_anchors.json"
        )
        self.dim = 512  # TriviumDB的联合维度，AuraVision原输出为384，后台强制补齐为512

        self.observation_interval = 30  # 秒
        self.ema_alpha = 0.3
        self.similarity_threshold = 0.85
        self.saturation_threshold = 0.7

        self._initialized = True
        logger.info("[AuraVision] 服务初始化完成")

    async def initialize(self) -> bool:
        """初始化服务，包括Rust模型和DB数据"""
        if not RUST_VISION_AVAILABLE:
            logger.error("[AuraVision] Rust 模块不可用，无法初始化")
            return False

        try:
            # 1. 尝试加载视觉模型
            if not os.path.exists(self.model_path):
                logger.warning(f"[AuraVision] 模型文件不存在: {self.model_path}")
                self.manager = VisionEncoderManager(None)
            else:
                self.manager = VisionEncoderManager(self.model_path)
                self.manager.configure(ema_alpha=self.ema_alpha)

            # 2. 检查 TriviumDB 数据同步(如果TriviumDB为空，迁移旧的JSON数据)
            await self._migrate_legacy_anchors()

            logger.info("[AuraVision] 引擎初始化成功")
            return True

        except Exception as e:
            logger.error(f"[AuraVision] 初始化失败: {e}")
            return False

    def is_ready(self) -> bool:
        return self.manager is not None and self.manager.is_model_loaded()

    async def _migrate_legacy_anchors(self):
        """兼容性机制：将 JSON 迁移至 TriviumDB"""
        if self.trivium_store.count() > 0:
            return  # TriviumDB 已经有数据了

        if not os.path.exists(self.legacy_anchors_path):
            return

        logger.info(
            "[AuraVision] 检测到旧版 intent_anchors.json，准备迁移至 TriviumDB..."
        )
        try:
            with open(self.legacy_anchors_path, "r", encoding="utf-8") as f:
                anchors = json.load(f)

            count = 0
            for item in anchors:
                await self.trivium_store.insert(
                    memory_id=item["id"],
                    vector=item["vector"]
                    + [0.0] * 128,  # [零填充兼容] 将旧版384维灌满至512
                    payload={
                        "agent_id": "pero",
                        "description": item.get("description", ""),
                        "importance": item.get("importance", 1.0),
                        "tags": item.get("tags", ""),
                    },
                )
                count += 1
            logger.info(f"[AuraVision] 成功迁移了 {count} 个视觉意图锚点！")
        except Exception as e:
            logger.error(f"[AuraVision] 迁移旧版锚点失败: {e}")

    async def load_intent_anchors(self, anchors: List[Dict[str, Any]]) -> int:
        """重新开放的API：增加新锚点到TriviumDB"""
        count = 0
        for anchor in anchors:
            try:
                await self.trivium_store.insert(
                    memory_id=anchor["id"],
                    vector=anchor["vector"] + [0.0] * 128,  # [零填充兼容] 384补齐至512
                    payload={
                        "agent_id": "pero",
                        "description": anchor["description"],
                        "importance": anchor.get("importance", 1.0),
                        "tags": anchor.get("tags", ""),
                    },
                )
                count += 1
            except Exception as e:
                logger.warning(f"[AuraVision] 添加锚点 {anchor.get('id')} 失败: {e}")

        # 强制落盘并备份回 JSON
        await self.trivium_store.flush()
        logger.info(f"[AuraVision] 当前总锚点数量: {self.trivium_store.count()}")
        return count

    def _preprocess_screenshot(self, img_bgr: np.ndarray) -> List[float]:
        img_resized = cv2.resize(img_bgr, (64, 64), interpolation=cv2.INTER_AREA)
        img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
        img_edges = cv2.Canny(img_gray, 100, 200)
        pixels = (img_edges.astype(np.float32) / 255.0 - 0.5) / 0.5
        return pixels.flatten().tolist()

    def _calculate_saturation(self, activated_ids: List[int]) -> float:
        if not activated_ids:
            return 0.0
        intersection = set(activated_ids).intersection(set(self.recent_activated_ids))
        return len(intersection) / len(activated_ids)

    async def process_current_screen(self) -> Optional[VisionProcessResult]:
        """处理当前屏幕返回视觉感知结果"""
        if not self.is_ready():
            return None

        try:
            # 1. 截图并 Base64 解码提取 opencv 格式
            shot_data = screenshot_manager.capture()
            if not shot_data or not shot_data.get("base64"):
                return None

            img_data = base64.b64decode(shot_data["base64"])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            # 2. 预处理
            pixels = self._preprocess_screenshot(img)

            # 3. Rust进行极速视觉嵌入提取 + EMA自适应平滑 (输出384维)
            vector_384 = self.manager.encode_and_smooth_pixels(pixels)

            # 魔法缝合：用 128 个零把它强行塞满 512 维的空间，以便和文字的 bge 兼容！
            vector = vector_384 + [0.0] * 128

            # 4. 在 TriviumDB 视觉库中比对搜索最相关的锚点
            hits = await self.trivium_store.search(
                query_vector=vector,
                top_k=3,
                expand_depth=2,  # TriviumDB自带扩散唤醒特性替代了原来的 ActivationGraph
                dpp_weight=0.0,
            )

            if not hits:
                return VisionProcessResult(False, -1, 0.0, "", [], 0.0)

            # 取 Top 1 锚点检验
            top_hit = hits[0]
            top_sim = top_hit["score"]
            top_id = top_hit["id"]
            top_desc = top_hit["payload"].get("description", "")

            if top_sim < self.similarity_threshold:
                return VisionProcessResult(False, top_id, top_sim, top_desc, [], 0.0)

            # 收集被关联扩散唤醒的所有周边记忆节点
            activated_ids = [h["id"] for h in hits]

            # 5. 饱和度检测
            saturation = self._calculate_saturation(activated_ids)
            self.recent_activated_ids = activated_ids.copy()

            triggered = saturation < self.saturation_threshold

            return VisionProcessResult(
                triggered=triggered,
                top_anchor_id=top_id,
                top_similarity=top_sim,
                top_description=top_desc,
                activated_memory_ids=activated_ids,
                saturation=saturation,
            )

        except Exception as e:
            logger.error(f"[AuraVision] 处理失败: {e}")
            return None

    async def start_vision_loop(self, interval: int = None):
        """启动视觉感知循环(V3.0多模态版)"""
        # 由于依赖异步 DB 操作，确保 initialize 是在 Event Loop 中启动。我们先在此保险一下。
        await self.initialize()

        if self.is_running:
            logger.warning("[AuraVision] 循环已在运行")
            return

        if interval:
            self.observation_interval = interval

        self.is_running = True

        if MULTIMODAL_AVAILABLE:
            multimodal_coordinator.update_session_start()

        logger.info(
            f"[AuraVision] 视觉感知循环已启动 (初始间隔: {self.observation_interval}s, 多模态: {MULTIMODAL_AVAILABLE})"
        )

        try:
            while self.is_running:
                result = await self.process_current_screen()

                if result and MULTIMODAL_AVAILABLE:
                    decision = await self._multimodal_decision(result)
                    if decision.should_trigger:
                        logger.info(
                            f"[AuraVision] 🎯 多模态触发! 模式: {decision.mode.value}, 得分: {decision.final_score:.4f}, 理由: {decision.reasoning}"
                        )
                        asyncio.create_task(
                            self._trigger_proactive_dialogue_v3(decision)
                        )
                    elif decision.mode == TriggerMode.INTERNAL:
                        logger.debug(
                            f"[AuraVision] 📝 感知已记录 (得分: {decision.final_score:.4f})"
                        )

                    current_interval = (
                        multimodal_coordinator.get_current_sample_interval()
                    )

                elif result:
                    if result.triggered:
                        logger.info(
                            f"[AuraVision] 🎯 触发主动感知! 锚点: {result.top_description[:30]}... (相似度: {result.top_similarity:.4f})"
                        )
                        asyncio.create_task(self._trigger_proactive_dialogue(result))
                    current_interval = self.observation_interval
                else:
                    current_interval = self.observation_interval

                await asyncio.sleep(current_interval)

        except asyncio.CancelledError:
            logger.info("[AuraVision] 循环被取消")
        except Exception as e:
            logger.error(f"[AuraVision] 循环崩溃: {e}")
        finally:
            self.is_running = False

    async def _multimodal_decision(self, visual_result):
        visual_dict = {
            "top_similarity": visual_result.top_similarity,
            "top_description": visual_result.top_description,
            "top_anchor_id": visual_result.top_anchor_id,
            "saturation": visual_result.saturation,
            "activated_memory_ids": visual_result.activated_memory_ids,
        }
        semantic_scores = dict.fromkeys(visual_result.activated_memory_ids, 0.5)
        return multimodal_coordinator.compute_decision(
            visual_result=visual_dict,
            semantic_memories=visual_result.activated_memory_ids,
            semantic_scores=semantic_scores,
            force_time_check=True,
        )

    async def _trigger_proactive_dialogue_v3(self, decision):
        try:
            from database import get_session
            from services.agent.agent_service import AgentService

            internal_prompt = decision.context_for_llm
            async for session in get_session():
                agent = AgentService(session)
                response_text = ""
                async for chunk in agent.chat(
                    messages=[],
                    source="vision",
                    session_id="proactive",
                    system_trigger_instruction=internal_prompt,
                ):
                    response_text += chunk

                if "<NOTHING>" in response_text.upper():
                    logger.info("[AuraVision] Agent 选择保持沉默")
                else:
                    logger.info(
                        f"[AuraVision] Agent 主动发言: {response_text[:100]}..."
                    )
                    if MULTIMODAL_AVAILABLE:
                        multimodal_coordinator.clear_perception_log()
                break

        except Exception as e:
            logger.error(f"[AuraVision] V3 触发对话失败: {e}")

    async def _trigger_proactive_dialogue(self, result: VisionProcessResult):
        try:
            from database import get_session
            from services.agent.agent_service import AgentService

            memory_ids_str = ", ".join(
                str(id) for id in result.activated_memory_ids[:5]
            )
            internal_prompt = mdp.render(
                "tasks/perception/aura",
                {
                    "visual_intent": result.top_description,
                    "confidence": f"{result.top_similarity:.4f}",
                    "saturation": f"{result.saturation:.4f}",
                    "memory_ids": memory_ids_str,
                },
            )

            async for session in get_session():
                agent = AgentService(session)
                response_text = ""
                async for chunk in agent.chat(
                    messages=[],
                    source="vision",
                    session_id="proactive",
                    system_trigger_instruction=internal_prompt,
                ):
                    response_text += chunk

                if "<NOTHING>" in response_text.upper():
                    logger.info("[AuraVision] Agent 选择保持沉默")
                else:
                    logger.info(
                        f"[AuraVision] Agent 主动发言: {response_text[:100]}..."
                    )
                break
        except Exception as e:
            logger.error(f"[AuraVision] 触发对话失败: {e}")

    def stop(self):
        self.is_running = False

    def configure(
        self,
        observation_interval: int = None,
        ema_alpha: float = None,
        similarity_threshold: float = None,
        saturation_threshold: float = None,
    ):
        if observation_interval is not None:
            self.observation_interval = observation_interval
        if ema_alpha is not None:
            self.ema_alpha = ema_alpha
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
        if saturation_threshold is not None:
            self.saturation_threshold = saturation_threshold

        if self.manager and ema_alpha is not None:
            self.manager.configure(ema_alpha=ema_alpha)

    def get_status(self) -> Dict[str, Any]:
        return {
            "rust_available": RUST_VISION_AVAILABLE,
            "model_loaded": self.is_ready(),
            "is_running": self.is_running,
            "anchor_count": self.trivium_store.count(),
            "config": {
                "observation_interval": self.observation_interval,
                "ema_alpha": self.ema_alpha,
                "similarity_threshold": self.similarity_threshold,
                "saturation_threshold": self.saturation_threshold,
            },
        }


aura_vision_service = AuraVisionService()
