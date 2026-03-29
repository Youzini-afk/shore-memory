//! 视觉特征编码集成模块
//!
//! 实现技术文档中的早期视觉链路：
//! 视觉编码 -> 特征向量提取 -> EMA 平滑
//!
//! 移除了原本在这个模块的 HNSW 检索图结构，交还给上层 Python 的 TriviumDB 实现

use crate::aura_vision::AuraVisionEncoder;
use pyo3::prelude::*;

/// 视觉特征编码管理器
///
/// 仅负责 ONNX 模型加载和视觉编码、EMA 平滑
#[pyclass]
pub struct VisionEncoderManager {
    /// 视觉编码器
    encoder: Option<AuraVisionEncoder>,

    // === EMA 平滑参数 ===
    /// 上一帧的向量 (用于平滑)
    last_vector: Option<Vec<f32>>,

    /// EMA 系数 (0-1, 越小越平滑)
    ema_alpha: f32,

    /// 模型是否已加载
    model_loaded: bool,
}

#[pymethods]
impl VisionEncoderManager {
    /// 创建新的编码管理器实例
    ///
    /// # Arguments
    /// * `model_path` - ONNX 模型文件路径 (可选)
    #[new]
    #[pyo3(signature = (model_path=None))]
    fn new(model_path: Option<String>) -> PyResult<Self> {
        let mut manager = Self {
            encoder: None,
            last_vector: None,
            ema_alpha: 0.3,
            model_loaded: false,
        };

        // 如果提供了模型路径，尝试加载
        if let Some(path) = model_path {
            manager.load_model(path)?;
        }

        Ok(manager)
    }

    /// 加载视觉编码模型
    fn load_model(&mut self, model_path: String) -> PyResult<()> {
        let encoder = AuraVisionEncoder::load(&model_path).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("加载模型失败: {:?}", e))
        })?;

        self.encoder = Some(encoder);
        self.model_loaded = true;
        Ok(())
    }

    /// 检查模型是否已加载
    fn is_model_loaded(&self) -> bool {
        self.model_loaded
    }

    /// 配置参数
    #[pyo3(signature = (ema_alpha=None))]
    fn configure(&mut self, ema_alpha: Option<f32>) {
        if let Some(v) = ema_alpha {
            self.ema_alpha = v.clamp(0.0, 1.0);
        }
    }

    /// 重置 EMA 状态
    fn reset_ema(&mut self) {
        self.last_vector = None;
    }

    /// 仅进行视觉编码并附加时序 EMA 平滑
    ///
    /// # Arguments
    /// * `pixels` - 预处理后的像素数据 (4096 个值, [-1, 1])
    ///
    /// # Returns
    /// * 384 维向量
    #[pyo3(signature = (pixels))]
    fn encode_and_smooth_pixels(&mut self, pixels: Vec<f32>) -> PyResult<Vec<f32>> {
        let encoder = self
            .encoder
            .as_ref()
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("模型未加载"))?;

        let mut current_vector = encoder.forward_from_pixels(&pixels).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("视觉编码失败: {:?}", e))
        })?;

        // 2. EMA 时序平滑
        if let Some(ref last) = self.last_vector {
            for (cur, prev) in current_vector.iter_mut().zip(last.iter()) {
                *cur = self.ema_alpha * *cur + (1.0 - self.ema_alpha) * prev;
            }
            // 重新归一化
            Self::l2_normalize_static(&mut current_vector);
        }
        self.last_vector = Some(current_vector.clone());

        Ok(current_vector)
    }
}

impl VisionEncoderManager {
    /// L2 归一化
    fn l2_normalize_static(vec: &mut [f32]) {
        let norm: f32 = vec.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 1e-10 {
            let inv_norm = 1.0 / norm;
            for x in vec.iter_mut() {
                *x *= inv_norm;
            }
        }
    }
}
