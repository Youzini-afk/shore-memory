"""
AuraVision Service - 视觉意图感知服务 (V3.0 多模态版)

使用 Rust 原生推理引擎，实现技术文档设计的完整链路：
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
import cv2
import numpy as np
import base64
import os
from typing import Optional, List, Dict, Any
from loguru import logger

from services.screenshot_service import screenshot_manager
from services.mdp.manager import mdp

# 多模态协调器 (V3.0)
try:
    from services.multimodal_trigger_service import (
        MultimodalTriggerCoordinator, TriggerMode, multimodal_coordinator
    )
    MULTIMODAL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[AuraVision] 多模态协调器不可用: {e}")
    MULTIMODAL_AVAILABLE = False
    multimodal_coordinator = None

# 尝试导入 Rust 核心模块
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
    """
    视觉意图感知服务
    
    核心功能:
    1. 定期截取屏幕 -> 脱敏处理 -> 意图编码
    2. 匹配意图锚点 -> 触发扩散激活 -> 唤醒相关记忆
    3. 饱和度检测 -> 决定是否主动对话
    """
    
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
            "models", "AuraVision", "weights", "auravision_v1.onnx"
        )
        
        # 锚点数据路径
        base_dir = os.environ.get("PERO_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.anchors_path = os.path.join(base_dir, "data", "rust_db", "intent_anchors.json")
        
        # 配置参数
        self.observation_interval = 30  # 秒
        self.ema_alpha = 0.3
        self.similarity_threshold = 0.85
        self.saturation_threshold = 0.7
        
        self._initialized = True
        logger.info("[AuraVision] 服务初始化完成")

    def initialize(self) -> bool:
        """
        初始化 Rust 视觉引擎
        
        Returns:
            bool: 是否初始化成功
        """
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
                saturation_threshold=self.saturation_threshold
            )
            
            # 尝试加载已保存的锚点
            if os.path.exists(self.anchors_path):
                try:
                    self.manager.load_anchors(self.anchors_path)
                    logger.info(f"[AuraVision] 加载了 {self.manager.anchor_count()} 个锚点")
                except Exception as e:
                    logger.warning(f"[AuraVision] 加载锚点失败: {e}")
            
            logger.info(f"[AuraVision] Rust 引擎初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"[AuraVision] 初始化失败: {e}")
            return False

    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        return self.manager is not None and self.manager.is_model_loaded()

    def load_intent_anchors(self, anchors: List[Dict[str, Any]]) -> int:
        """
        加载意图锚点
        
        Args:
            anchors: 锚点列表，每个锚点包含:
                - id: int
                - vector: List[float] (384维)
                - description: str
                - importance: float (0-1, 可选)
                - tags: str (可选)
        
        Returns:
            int: 成功加载的锚点数量
        """
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
                    tags=anchor.get("tags", "")
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
        """
        加载记忆关联边 (用于扩散激活)
        
        Args:
            connections: [(source_id, target_id, weight), ...]
        """
        if not self.manager:
            return
        
        self.manager.add_memory_connections(connections)
        logger.info(f"[AuraVision] 加载了 {len(connections)} 条记忆关联")

    def _preprocess_screenshot(self, img_bgr: np.ndarray) -> List[float]:
        """
        预处理截图为模型输入
        
        流程:
        1. 缩放到 64x64
        2. 灰度化
        3. Canny 边缘检测 (隐私脱敏)
        4. 归一化到 [-1, 1]
        
        Args:
            img_bgr: BGR 格式的图像 (OpenCV 默认)
        
        Returns:
            List[float]: 4096 个像素值
        """
        # 1. 缩放
        img_resized = cv2.resize(img_bgr, (64, 64), interpolation=cv2.INTER_AREA)
        
        # 2. 灰度化
        img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
        
        # 3. Canny 边缘检测 (隐私脱敏的关键步骤)
        img_edges = cv2.Canny(img_gray, 100, 200)
        
        # 4. 归一化到 [-1, 1]
        pixels = (img_edges.astype(np.float32) / 255.0 - 0.5) / 0.5
        
        return pixels.flatten().tolist()

    async def process_current_screen(self) -> Optional[VisionProcessResult]:
        """
        处理当前屏幕并返回视觉感知结果
        
        Returns:
            VisionProcessResult: 处理结果，包含:
                - triggered: 是否应触发主动对话
                - top_anchor_id: 最匹配的锚点 ID
                - top_similarity: 匹配相似度
                - top_description: 锚点描述
                - activated_memory_ids: 唤醒的记忆 ID 列表
                - saturation: 上下文饱和度
        """
        if not self.is_ready():
            logger.debug("[AuraVision] 服务未就绪，跳过处理")
            return None
        
        try:
            # 1. 截图
            shot_data = screenshot_manager.capture()
            if not shot_data or not shot_data.get("base64"):
                logger.debug("[AuraVision] 截图失败")
                return None
            
            # 2. 解码 Base64
            img_data = base64.b64decode(shot_data["base64"])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                logger.warning("[AuraVision] 图像解码失败")
                return None
            
            # 3. 预处理
            pixels = self._preprocess_screenshot(img)
            
            # 4. Rust 引擎处理
            result = self.manager.process_visual_input(
                pixels=pixels,
                propagation_steps=2,
                propagation_decay=0.5
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[AuraVision] 处理失败: {e}")
            return None

    async def start_vision_loop(self, interval: int = None):
        """
        启动视觉感知循环 (V3.0 多模态版)
        
        Args:
            interval: 初始观察间隔 (秒)，之后会自适应调整
        """
        if self.is_running:
            logger.warning("[AuraVision] 循环已在运行")
            return
        
        if interval:
            self.observation_interval = interval
        
        self.is_running = True
        
        # 通知协调器会话开始
        if MULTIMODAL_AVAILABLE:
            multimodal_coordinator.update_session_start()
        
        logger.info(f"[AuraVision] 视觉感知循环已启动 (初始间隔: {self.observation_interval}s, 多模态: {MULTIMODAL_AVAILABLE})")
        
        try:
            while self.is_running:
                result = await self.process_current_screen()
                
                if result and MULTIMODAL_AVAILABLE:
                    # V3.0: 使用多模态协调器进行决策
                    decision = await self._multimodal_decision(result)
                    
                    if decision.should_trigger:
                        logger.info(
                            f"[AuraVision] 🎯 多模态触发! "
                            f"模式: {decision.mode.value}, "
                            f"综合得分: {decision.final_score:.4f}, "
                            f"理由: {decision.reasoning}"
                        )
                        
                        # 异步触发主动对话 (使用协调器生成的上下文)
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
                    current_interval = multimodal_coordinator.get_current_sample_interval()
                    
                elif result:
                    # 降级到 V2.0 逻辑
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
        """
        使用多模态协调器进行决策
        
        Args:
            visual_result: VisionProcessResult 对象
        
        Returns:
            MultimodalDecision: 融合决策结果
        """
        # 转换 VisionProcessResult 为 dict
        visual_dict = {
            "top_similarity": visual_result.top_similarity,
            "top_description": visual_result.top_description,
            "top_anchor_id": visual_result.top_anchor_id,
            "saturation": visual_result.saturation,
            "activated_memory_ids": visual_result.activated_memory_ids,
        }
        
        # 构建语义扩散分数 (从激活的记忆 ID)
        activated_ids = visual_result.activated_memory_ids
        semantic_scores = {mid: 0.5 for mid in activated_ids}  # 简化: 统一激活分数
        
        # 调用协调器
        decision = multimodal_coordinator.compute_decision(
            visual_result=visual_dict,
            semantic_memories=activated_ids,
            semantic_scores=semantic_scores,
            force_time_check=True
        )
        
        return decision

    async def _trigger_proactive_dialogue_v3(self, decision):
        """
        V3.0 多模态版主动对话触发
        
        使用协调器生成的完整上下文
        """
        try:
            from services.agent_service import AgentService
            from database import get_session
            
            # 使用协调器生成的上下文
            internal_prompt = decision.context_for_llm
            
            async for session in get_session():
                agent = AgentService(session)
                response_text = ""
                
                async for chunk in agent.chat(
                    messages=[],
                    source="vision",
                    session_id="proactive",
                    system_trigger_instruction=internal_prompt
                ):
                    response_text += chunk
                
                # 检查是否选择不说话
                if "<NOTHING>" in response_text.upper():
                    logger.info("[AuraVision] Agent 选择保持沉默")
                else:
                    logger.info(f"[AuraVision] Agent 主动发言: {response_text[:100]}...")
                    
                    # 清空感知日志 (已经转化为对话)
                    if MULTIMODAL_AVAILABLE:
                        multimodal_coordinator.clear_perception_log()
                
                break
                
        except Exception as e:
            logger.error(f"[AuraVision] V3 触发对话失败: {e}")

    async def _trigger_proactive_dialogue(self, result: VisionProcessResult):
        """
        触发主动对话
        
        将视觉感知结果转化为 AgentService 可理解的内部提示
        """
        try:
            from services.agent_service import AgentService
            from database import get_session
            
            # 构建内部感知提示词
            memory_ids_str = ", ".join(str(id) for id in result.activated_memory_ids[:5])
            
            internal_prompt = mdp.render("tasks/perception/aura", {
                "visual_intent": result.top_description,
                "confidence": f"{result.top_similarity:.4f}",
                "saturation": f"{result.saturation:.4f}",
                "memory_ids": memory_ids_str
            })
            
            async for session in get_session():
                agent = AgentService(session)
                response_text = ""
                
                async for chunk in agent.chat(
                    messages=[],
                    source="vision",
                    session_id="proactive",
                    system_trigger_instruction=internal_prompt
                ):
                    response_text += chunk
                
                # 检查是否选择不说话
                if "<NOTHING>" in response_text.upper():
                    logger.info("[AuraVision] Agent 选择保持沉默")
                else:
                    logger.info(f"[AuraVision] Agent 主动发言: {response_text[:100]}...")
                
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
        saturation_threshold: float = None
    ):
        """
        配置服务参数
        
        Args:
            observation_interval: 观察间隔 (秒)
            ema_alpha: EMA 平滑系数 (0-1)
            similarity_threshold: 相似度触发阈值 (0-1)
            saturation_threshold: 饱和度抑制阈值 (0-1)
        """
        if observation_interval is not None:
            self.observation_interval = observation_interval
        
        if self.manager:
            self.manager.configure(
                ema_alpha=ema_alpha,
                similarity_threshold=similarity_threshold,
                saturation_threshold=saturation_threshold
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
            }
        }


# 全局单例
aura_vision_service = AuraVisionService()
