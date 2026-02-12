"""
AuraVision Service - 视觉意图感知服务(V3.0多模态版)

使用Rust原生推理引擎实现完整链路：
- 视觉编码 -> 384D 向量
- EMA 时序平滑
- 意图锚点匹配
- 扩散激活记忆唤醒
- 上下文饱和度检测

V3.0 新增:
- 多模态主动触发协调器集成
- 自适应采样频率
- 时间感知融合

版本: 3.0.0
"""

import asyncio
import base64
import os
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from loguru import logger

from services.mdp.manager import mdp
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

# 尝试导入Rust核心模块
try:
    from pero_memory_core import VisionIntentMemoryManager, VisionProcessResult

    RUST_VISION_AVAILABLE = True
    logger.info("[AuraVision] Rust 视觉模块加载成功")
except ImportError as e:
    logger.warning(f"[AuraVision] Rust 视觉模块不可用: {e}")
    RUST_VISION_AVAILABLE = False
    VisionIntentMemoryManager = None
    VisionProcessResult = None


class AuraVisionService:
    """视觉意图感知服务：截屏脱敏编码->锚点匹配->扩散激活->饱和度检测。"""

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
        self.manager: Optional[VisionIntentMemoryManager] = None

        # 模型路径
        self.model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models",
            "AuraVision",
            "weights",
            "auravision_v1.onnx",
        )

        # 锚点数据路径
        base_dir = os.environ.get(
            "PERO_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.anchors_path = os.path.join(
            base_dir, "data", "rust_db", "intent_anchors.json"
        )

        # 配置参数
        self.observation_interval = 30  # 秒
        self.ema_alpha = 0.3
        self.similarity_threshold = 0.85
        self.saturation_threshold = 0.7

        self._initialized = True
        logger.info("[AuraVision] 服务初始化完成")

    def initialize(self) -> bool:
        """初始化Rust视觉引擎"""
        if not RUST_VISION_AVAILABLE:
            logger.error("[AuraVision] Rust 模块不可用，无法初始化")
            return False

        try:
            # 检查模型文件是否存在
            if not os.path.exists(self.model_path):
                logger.warning(f"[AuraVision] 模型文件不存在: {self.model_path}")
                # 创建管理器但不加载模型
                self.manager = VisionIntentMemoryManager(None, 384)
                logger.info("[AuraVision] 管理器已创建 (无模型)")
                return True

            # 创建并加载模型
            self.manager = VisionIntentMemoryManager(self.model_path, 384)

            # 配置参数
            self.manager.configure(
                ema_alpha=self.ema_alpha,
                similarity_threshold=self.similarity_threshold,
                saturation_threshold=self.saturation_threshold,
            )

            # 尝试加载已保存锚点
            if os.path.exists(self.anchors_path):
                try:
                    self.manager.load_anchors(self.anchors_path)
                    logger.info(
                        f"[AuraVision] 加载了 {self.manager.anchor_count()} 个锚点"
                    )
                except Exception as e:
                    logger.warning(f"[AuraVision] 加载锚点失败: {e}")

            logger.info("[AuraVision] Rust 引擎初始化成功")
            return True

        except Exception as e:
            logger.error(f"[AuraVision] 初始化失败: {e}")
            return False

    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        return self.manager is not None and self.manager.is_model_loaded()

    def load_intent_anchors(self, anchors: List[Dict[str, Any]]) -> int:
        """加载意图锚点"""
        if not self.manager:
            logger.error("[AuraVision] 管理器未初始化")
            return 0

        count = 0
        for anchor in anchors:
            try:
                self.manager.add_intent_anchor(
                    id=anchor["id"],
                    vector=anchor["vector"],
                    description=anchor["description"],
                    importance=anchor.get("importance", 1.0),
                    tags=anchor.get("tags", ""),
                )
                count += 1
            except Exception as e:
                logger.warning(f"[AuraVision] 添加锚点 {anchor.get('id')} 失败: {e}")

        logger.info(f"[AuraVision] 加载了 {count}/{len(anchors)} 个意图锚点")

        # 保存锚点
        try:
            os.makedirs(os.path.dirname(self.anchors_path), exist_ok=True)
            self.manager.save_anchors(self.anchors_path)
        except Exception as e:
            logger.warning(f"[AuraVision] 保存锚点失败: {e}")

        return count

    def load_memory_connections(self, connections: List[tuple]) -> None:
        """加载记忆关联边(用于扩散激活)"""
        if not self.manager:
            return

        self.manager.add_memory_connections(connections)
        logger.info(f"[AuraVision] 加载了 {len(connections)} 条记忆关联")

    def _preprocess_screenshot(self, img_bgr: np.ndarray) -> List[float]:
        """预处理截图为模型输入(缩放/灰度/Canny边缘/归一化)。"""
        # 1. 缩放
        img_resized = cv2.resize(img_bgr, (64, 64), interpolation=cv2.INTER_AREA)

        # 2. 灰度化
        img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

        # 3. Canny边缘检测(隐私脱敏关键)
        img_edges = cv2.Canny(img_gray, 100, 200)

        # 4. 归一化[-1, 1]
        pixels = (img_edges.astype(np.float32) / 255.0 - 0.5) / 0.5

        return pixels.flatten().tolist()

    async def process_current_screen(self) -> Optional[VisionProcessResult]:
        """处理当前屏幕返回视觉感知结果"""
        if not self.is_ready():
            logger.debug("[AuraVision] 服务未就绪，跳过处理")
            return None

        try:
            # 1. 截图
            shot_data = screenshot_manager.capture()
            if not shot_data or not shot_data.get("base64"):
                logger.debug("[AuraVision] 截图失败")
                return None

            # 2. 解码Base64
            img_data = base64.b64decode(shot_data["base64"])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                logger.warning("[AuraVision] 图像解码失败")
                return None

            # 3. 预处理
            pixels = self._preprocess_screenshot(img)

            # 4. Rust引擎处理
            result = self.manager.process_visual_input(
                pixels=pixels, propagation_steps=2, propagation_decay=0.5
            )

            return result

        except Exception as e:
            logger.error(f"[AuraVision] 处理失败: {e}")
            return None

    async def start_vision_loop(self, interval: int = None):
        """启动视觉感知循环(V3.0多模态版)"""
        if self.is_running:
            logger.warning("[AuraVision] 循环已在运行")
            return

        if interval:
            self.observation_interval = interval

        self.is_running = True

        # 通知协调器会话开始
        if MULTIMODAL_AVAILABLE:
            multimodal_coordinator.update_session_start()

        logger.info(
            f"[AuraVision] 视觉感知循环已启动 (初始间隔: {self.observation_interval}s, 多模态: {MULTIMODAL_AVAILABLE})"
        )

        try:
            while self.is_running:
                result = await self.process_current_screen()

                if result and MULTIMODAL_AVAILABLE:
                    # V3.0: 使用多模态协调器决策
                    decision = await self._multimodal_decision(result)

                    if decision.should_trigger:
                        logger.info(
                            f"[AuraVision] 🎯 多模态触发! "
                            f"模式: {decision.mode.value}, "
                            f"综合得分: {decision.final_score:.4f}, "
                            f"理由: {decision.reasoning}"
                        )

                        # 异步触发主动对话(使用协调器上下文)
                        asyncio.create_task(
                            self._trigger_proactive_dialogue_v3(decision)
                        )

                    elif decision.mode == TriggerMode.INTERNAL:
                        logger.debug(
                            f"[AuraVision] 📝 感知已记录 (得分: {decision.final_score:.4f})"
                        )

                    else:
                        logger.debug(
                            f"[AuraVision] 👀 静默观察 (得分: {decision.final_score:.4f})"
                        )

                    # 使用自适应采样间隔
                    current_interval = (
                        multimodal_coordinator.get_current_sample_interval()
                    )

                elif result:
                    # 降级V2.0逻辑
                    if result.triggered:
                        logger.info(
                            f"[AuraVision] 🎯 触发主动感知! "
                            f"锚点: {result.top_description[:30]}... "
                            f"(相似度: {result.top_similarity:.4f}, "
                            f"饱和度: {result.saturation:.4f})"
                        )
                        asyncio.create_task(self._trigger_proactive_dialogue(result))
                    else:
                        logger.debug(
                            f"[AuraVision] 观察中... "
                            f"最佳匹配: {result.top_similarity:.4f} "
                        )
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
        """使用多模态协调器决策"""
        # 转换VisionProcessResult为dict
        visual_dict = {
            "top_similarity": visual_result.top_similarity,
            "top_description": visual_result.top_description,
            "top_anchor_id": visual_result.top_anchor_id,
            "saturation": visual_result.saturation,
            "activated_memory_ids": visual_result.activated_memory_ids,
        }

        # 构建语义扩散分数(从激活记忆ID)
        activated_ids = visual_result.activated_memory_ids
        semantic_scores = dict.fromkeys(activated_ids, 0.5)  # 简化: 统一激活分数

        # 调用协调器
        decision = multimodal_coordinator.compute_decision(
            visual_result=visual_dict,
            semantic_memories=activated_ids,
            semantic_scores=semantic_scores,
            force_time_check=True,
        )

        return decision

    async def _trigger_proactive_dialogue_v3(self, decision):
        """V3.0多模态主动对话触发(使用协调器上下文)。"""
        try:
            from database import get_session
            from services.agent.agent_service import AgentService

            # 使用协调器生成的上下文
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

                # 检查是否选择不说话
                if "<NOTHING>" in response_text.upper():
                    logger.info("[AuraVision] Agent 选择保持沉默")
                else:
                    logger.info(
                        f"[AuraVision] Agent 主动发言: {response_text[:100]}..."
                    )

                    # 清空感知日志(已转对话)
                    if MULTIMODAL_AVAILABLE:
                        multimodal_coordinator.clear_perception_log()

                break

        except Exception as e:
            logger.error(f"[AuraVision] V3 触发对话失败: {e}")

    async def _trigger_proactive_dialogue(self, result: VisionProcessResult):
        """触发主动对话(转为AgentService内部提示)。"""
        try:
            from database import get_session
            from services.agent.agent_service import AgentService

            # 构建内部感知提示词
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

                # 检查是否选择不说话
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
        """停止视觉感知循环"""
        self.is_running = False
        logger.info("[AuraVision] 视觉感知循环已停止")

    def configure(
        self,
        observation_interval: int = None,
        ema_alpha: float = None,
        similarity_threshold: float = None,
        saturation_threshold: float = None,
    ):
        """配置服务参数"""
        if observation_interval is not None:
            self.observation_interval = observation_interval

        if self.manager:
            self.manager.configure(
                ema_alpha=ema_alpha,
                similarity_threshold=similarity_threshold,
                saturation_threshold=saturation_threshold,
            )

        # 保存到实例变量
        if ema_alpha is not None:
            self.ema_alpha = ema_alpha
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
        if saturation_threshold is not None:
            self.saturation_threshold = saturation_threshold

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "rust_available": RUST_VISION_AVAILABLE,
            "model_loaded": self.is_ready(),
            "is_running": self.is_running,
            "anchor_count": self.manager.anchor_count() if self.manager else 0,
            "config": {
                "observation_interval": self.observation_interval,
                "ema_alpha": self.ema_alpha,
                "similarity_threshold": self.similarity_threshold,
                "saturation_threshold": self.saturation_threshold,
            },
        }


# 全局单例
aura_vision_service = AuraVisionService()
