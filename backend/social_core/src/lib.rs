use pyo3::prelude::*;
use std::collections::HashMap;
use rayon::prelude::*;

mod simhash;
use simhash::SimHash;

#[derive(Clone)]
struct Node {
    id: i64,
    #[allow(dead_code)]
    content: String,
    simhash: u64,
    #[allow(dead_code)]
    timestamp: u64,
    vector: Vec<f32>,
    #[allow(dead_code)]
    keywords: Vec<String>,
}

#[pyclass]
struct SocialMemoryEngine {
    nodes: HashMap<i64, Node>,
}

#[pymethods]
impl SocialMemoryEngine {
    #[new]
    fn new() -> Self {
        SocialMemoryEngine {
            nodes: HashMap::new(),
        }
    }

    /// 添加一条记忆
    /// timestamp: Unix 时间戳 (秒)
    /// vector: 嵌入向量 (f32 list)
    #[pyo3(text_signature = "($self, id, content, timestamp, vector, keywords)")]
    fn add_memory(&mut self, id: i64, content: String, timestamp: u64, vector: Vec<f32>, keywords: Vec<String>) {
        // 简单情感/类型推断 (TODO: 更复杂的逻辑)
        let mut emotion = 0u8;
        if content.contains("开心") { emotion |= SimHash::EMOTION_JOY; }
        
        let simhash = SimHash::compute_multimodal(&content, timestamp, emotion, SimHash::TYPE_EVENT);
        
        let node = Node {
            id,
            content,
            simhash,
            timestamp,
            vector,
            keywords,
        };
        self.nodes.insert(id, node);
    }

    /// 搜索记忆
    /// query: 查询文本
    /// ref_time: 参考时间戳 (用于解析"昨天"等)
    /// top_k: 返回数量
    /// query_vector: 查询向量 (可选，若提供则进行混合检索)
    #[pyo3(text_signature = "($self, query, ref_time, top_k, query_vector)")]
    fn search(&self, query: String, ref_time: u64, top_k: usize, query_vector: Option<Vec<f32>>) -> Vec<(i64, f32)> {
        let query_simhash = SimHash::compute_for_query(&query, ref_time);
        
        // Step 1: 粗排 (SimHash Hamming Distance)
        // 计算每个节点的 SimHash 相似度
        let mut candidates: Vec<(&Node, f32)> = self.nodes.values()
            .par_bridge() // 并行迭代
            .map(|node| {
                let xor = node.simhash ^ query_simhash;
                let dist = xor.count_ones();
                
                // 相似度打分 (基于 Hamming Distance)
                // 64位指纹，每位不同扣除 1/64 分
                let sim_score = 1.0 - (dist as f32 / 64.0);
                
                (node, sim_score)
            })
            .collect();

        // 排序并截断 (保留 Top 500 进行精排)
        candidates.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let coarse_k = std::cmp::min(candidates.len(), 500);
        let candidates = &candidates[..coarse_k];

        // Step 2: 精排 (Vector Cosine Similarity)
        if let Some(q_vec) = query_vector {
            let mut final_results: Vec<(i64, f32)> = candidates.iter()
                .map(|(node, sim_score)| {
                    let vec_score = cosine_similarity(&node.vector, &q_vec);
                    
                    // 混合打分: 0.3 * SimHash + 0.7 * Vector
                    // 如果 Vector 为 0 (无效)，则回退到 SimHash
                    let final_score = if vec_score > -1.0 {
                        0.3 * sim_score + 0.7 * vec_score
                    } else {
                        *sim_score
                    };
                    
                    (node.id, final_score)
                })
                .collect();
            
            final_results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            let final_k = std::cmp::min(final_results.len(), top_k);
            return final_results[..final_k].to_vec();
        } else {
            // 仅使用 SimHash 分数
            let final_results: Vec<(i64, f32)> = candidates.iter()
                .map(|(node, score)| (node.id, *score))
                .collect();
             let final_k = std::cmp::min(final_results.len(), top_k);
             return final_results[..final_k].to_vec();
        }
    }
    
    fn clear(&mut self) {
        self.nodes.clear();
    }
}

fn cosine_similarity(v1: &[f32], v2: &[f32]) -> f32 {
    if v1.len() != v2.len() || v1.is_empty() {
        return 0.0;
    }
    let mut dot = 0.0;
    let mut norm1 = 0.0;
    let mut norm2 = 0.0;
    for i in 0..v1.len() {
        dot += v1[i] * v2[i];
        norm1 += v1[i] * v1[i];
        norm2 += v2[i] * v2[i];
    }
    if norm1 == 0.0 || norm2 == 0.0 {
        return 0.0;
    }
    dot / (norm1.sqrt() * norm2.sqrt())
}

#[pymodule]
fn pero_social_core(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SocialMemoryEngine>()?;
    Ok(())
}
