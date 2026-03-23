"""
[PEDSA 检索增强模块]
提供 4 种独立的数学算法，纯增量嫁接到现有检索管线：

1. NMF 语义分解 - 查询结构理解
2. 稀疏编码残差 - 弱信号发现（FISTA 求解）
3. 共现增益 - Entity 关联统计增强
4. DPP 多样性采样 - 行列式点过程结果去冗余

所有算法独立于第三方项目，出处:
  NMF     → Lee & Seung, 1999 (Nature)
  LASSO   → Tibshirani, 1996 (JRSS)
  FISTA   → Beck & Teboulle, 2009 (SIAM)
  DPP     → Kulesza & Taskar, 2012 (Foundations and Trends in ML)
"""

import json
import logging
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("pero.retrieval_enhancer")

# --------------------------------------------------------------------------- #
#  加载增强参数（支持运行时热更新）
# --------------------------------------------------------------------------- #

_DEFAULT_PARAMS = {
    # 稀疏编码
    "sparse_coding_lambda": 0.1,       # L1 正则强度
    "sparse_coding_iterations": 80,    # FISTA 迭代次数
    "residual_threshold": 0.30,        # 残差范数阈值，超过则触发二次检索
    "residual_topk": 5,                # 二次检索返回数

    # DPP
    "dpp_candidate_multiplier": 3,     # 候选集 = limit × 此倍数
    "dpp_quality_weight": 1.0,         # 质量分权重（影响质量 vs 多样性平衡）

    # 共现增益
    "cooccurrence_bonus_scale": 0.10,  # 共现增益系数
    "cooccurrence_max_neighbors": 10,  # 每个 Entity 最多取多少个共现邻居

    # NMF
    "nmf_n_topics": 15,            # 主题数 k
    "nmf_novelty_threshold": 0.4,  # novelty 超过此阈值可触发稀疏编码

    # PPR
    "teleport_alpha": 0.0,         # 回家概率 (0=不启用)

    # 总开关
    "enable_sparse_coding": True,
    "enable_dpp": True,
    "enable_cooccurrence_boost": True,
    "enable_nmf": True,
}

_params_cache: Optional[Dict] = None
_params_mtime: float = 0.0

PARAMS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "retrieval_params.json",
)


def get_params() -> Dict:
    """读取参数配置文件，支持文件修改时间检测热更新"""
    global _params_cache, _params_mtime

    abs_path = os.path.abspath(PARAMS_FILE)
    try:
        mtime = os.path.getmtime(abs_path)
        if _params_cache is not None and mtime == _params_mtime:
            return _params_cache

        with open(abs_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        _params_cache = {**_DEFAULT_PARAMS, **loaded}
        _params_mtime = mtime
        logger.info(f"已加载检索增强参数: {abs_path}")
        return _params_cache

    except FileNotFoundError:
        if _params_cache is None:
            _params_cache = dict(_DEFAULT_PARAMS)
        return _params_cache


# =========================================================================== #
#  0. NMF 语义分解 (Multiplicative Update)
# =========================================================================== #

# NMF 基矩阵缓存（避免每次查询都重算）
_nmf_cache: Dict[str, Dict] = {}  # agent_id -> {"H": ndarray, "entity_ids": list, "hash": str}


def _nmf_multiplicative_update(
    V: np.ndarray,
    k: int,
    max_iter: int = 100,
    tol: float = 1e-4,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    非负矩阵分解 (Multiplicative Update Rules)
    Lee & Seung, 1999, Nature

    V ≈ W × H
      V: (m, d) 输入矩阵 (非负)
      W: (m, k) Entity × Topic 权重矩阵
      H: (k, d) Topic 向量矩阵

    返回: (W, H)
    """
    m, d = V.shape
    # 随机初始化 (使用 V 的均值尺度)
    avg = np.sqrt(V.mean() / k) if V.mean() > 0 else 0.01
    rng = np.random.RandomState(42)  # 固定种子保证可复现
    W = np.abs(rng.normal(avg, avg * 0.5, size=(m, k))).astype(np.float32) + 1e-6
    H = np.abs(rng.normal(avg, avg * 0.5, size=(k, d))).astype(np.float32) + 1e-6

    eps = 1e-10  # 防除零

    for iteration in range(max_iter):
        # 更新 H: H <- H * (Wᵀ V) / (Wᵀ W H)
        WtV = W.T @ V         # (k, d)
        WtWH = W.T @ W @ H    # (k, d)
        H *= WtV / (WtWH + eps)

        # 更新 W: W <- W * (V Hᵀ) / (W H Hᵀ)
        VHt = V @ H.T         # (m, k)
        WHHt = W @ H @ H.T    # (m, k)
        W *= VHt / (WHHt + eps)

        # 收敛检查 (每 10 次)
        if iteration % 10 == 9:
            residual = np.linalg.norm(V - W @ H) / (np.linalg.norm(V) + eps)
            if residual < tol:
                break

    return W, H


def nmf_query_analysis(
    query_vec: np.ndarray,
    entity_vecs: np.ndarray,
    entity_ids: List[int],
    agent_id: str = "pero",
    n_topics: int = 15,
) -> Dict:
    """
    NMF 语义分解：分析查询向量在已知语义空间中的结构。

    参数:
        query_vec:    查询向量 (d,)
        entity_vecs:  Entity 嵌入矩阵 (m, d)
        entity_ids:   对应的 Entity ID 列表
        agent_id:     Agent ID (用于缓存隔离)
        n_topics:     主题分解数 k

    返回:
        {
            "semantic_depth": float,    # 熵越低 = 查询越聚焦
            "topic_coverage": int,      # 涉及多少个主题
            "novelty": float,           # 查询中未被主题解释的成分比例
            "top_topics": List[float],  # 查询的主题分布
        }
    """
    global _nmf_cache

    m, d = entity_vecs.shape
    if m < 2:
        return {"semantic_depth": 0.0, "topic_coverage": 0, "novelty": 1.0, "top_topics": []}

    k = min(n_topics, m)  # 主题数不超过 Entity 数

    # 缓存检查：Entity 集合是否变化
    cache_hash = f"{m}_{d}_{k}_{hash(tuple(entity_ids[:10]))}"
    cached = _nmf_cache.get(agent_id)

    if cached and cached.get("hash") == cache_hash:
        H = cached["H"]
    else:
        # 取绝对值使输入非负 (embedding 可能有负值)
        V_abs = np.abs(entity_vecs)
        _, H = _nmf_multiplicative_update(V_abs, k, max_iter=100)
        _nmf_cache[agent_id] = {"H": H, "entity_ids": entity_ids, "hash": cache_hash}
        logger.info(f"NMF 基矩阵已更新: {m} entities -> {k} topics")

    # 查询投影到主题空间
    q_abs = np.abs(query_vec)
    # q_topics = softmax(q · Hᵀ)
    raw_scores = q_abs @ H.T  # (k,)
    # softmax
    exp_scores = np.exp(raw_scores - raw_scores.max())  # 数值稳定
    q_topics = exp_scores / (exp_scores.sum() + 1e-10)

    # 指标计算
    # 1. semantic_depth = 负熵 (越高 = 越聚焦)
    entropy = -np.sum(q_topics * np.log(q_topics + 1e-10))
    max_entropy = np.log(k) if k > 1 else 1.0
    semantic_depth = 1.0 - (entropy / max_entropy)  # 归一化到 [0, 1]

    # 2. topic_coverage = 权重超过均匀分布 * 0.5 的主题数
    threshold = 0.5 / k
    topic_coverage = int(np.sum(q_topics > threshold))

    # 3. novelty = 重建残差比例
    # 投影回原空间: q_recon = q_topics · H
    q_reconstructed = q_topics @ H  # (d,)
    novelty = float(
        np.linalg.norm(q_abs - q_reconstructed)
        / (np.linalg.norm(q_abs) + 1e-10)
    )

    return {
        "semantic_depth": float(semantic_depth),
        "topic_coverage": topic_coverage,
        "novelty": float(novelty),
        "top_topics": q_topics.tolist(),
    }


# =========================================================================== #
#  1. 稀疏编码残差发现 (FISTA / LASSO)
# =========================================================================== #

def _soft_threshold(x: np.ndarray, threshold: float) -> np.ndarray:
    """近端算子 (Proximal Operator for L1)"""
    return np.sign(x) * np.maximum(np.abs(x) - threshold, 0.0)


def sparse_code_residual(
    query_vec: np.ndarray,
    entity_vecs: np.ndarray,
    lambda_: float = 0.1,
    max_iter: int = 80,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    使用 FISTA (Fast Iterative Shrinkage-Thresholding) 求解：
        min_α  ½‖q - Eᵀα‖² + λ‖α‖₁

    参数:
        query_vec:   查询向量 (d,)
        entity_vecs: Entity 嵌入矩阵 (m, d)，m 个 Entity
        lambda_:     L1 正则强度
        max_iter:    最大迭代次数

    返回:
        alpha:          稀疏系数 (m,)
        residual:       残差向量 (d,)
        residual_norm:  残差 L2 范数
    """
    m, d = entity_vecs.shape
    if m == 0:
        return np.zeros(0), query_vec.copy(), float(np.linalg.norm(query_vec))

    # 预计算 Gram 矩阵 (m×m) 和投影 (m,)
    # E: (m, d), q: (d,)
    EtE = entity_vecs @ entity_vecs.T   # (m, m)
    Etq = entity_vecs @ query_vec       # (m,)

    # Lipschitz 常数 = 最大特征值的上界 ≤ ‖EᵀE‖_F
    # 快速近似: 使用最大行范数
    L = float(np.linalg.norm(EtE, ord=2))
    if L < 1e-10:
        return np.zeros(m), query_vec.copy(), float(np.linalg.norm(query_vec))

    step = 1.0 / L

    # FISTA (加速近端梯度下降)
    alpha = np.zeros(m)
    y = alpha.copy()
    t = 1.0

    for _ in range(max_iter):
        # 梯度: ∇f(y) = EᵀE·y - Eᵀq
        grad = EtE @ y - Etq

        # 近端步
        alpha_new = _soft_threshold(y - step * grad, lambda_ * step)

        # FISTA 动量
        t_new = (1.0 + math.sqrt(1.0 + 4.0 * t * t)) / 2.0
        y = alpha_new + ((t - 1.0) / t_new) * (alpha_new - alpha)

        alpha = alpha_new
        t = t_new

    # 计算残差
    reconstruction = entity_vecs.T @ alpha  # (d,)
    residual = query_vec - reconstruction
    residual_norm = float(np.linalg.norm(residual))

    return alpha, residual, residual_norm


# =========================================================================== #
#  2. DPP 贪心多样性采样
# =========================================================================== #

def dpp_greedy_select(
    candidate_vecs: np.ndarray,
    candidate_scores: np.ndarray,
    k: int,
    quality_weight: float = 1.0,
) -> List[int]:
    """
    贪心 DPP 采样：每次选择边际行列式增益最大的候选。

    构建 L-ensemble:
        L_ij = q_i · S_ij · q_j
        q_i = quality score, S_ij = cosine similarity

    参数:
        candidate_vecs:   候选向量矩阵 (N, d)
        candidate_scores: 候选质量分 (N,)
        k:                选取数量
        quality_weight:   质量分指数权重

    返回:
        选中的候选索引列表 (长度 k)
    """
    N = len(candidate_scores)
    if N <= k:
        return list(range(N))

    # 归一化向量（用于余弦相似度）
    norms = np.linalg.norm(candidate_vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    normed = candidate_vecs / norms

    # 质量因子 (加权)
    q = np.power(np.maximum(candidate_scores, 1e-10), quality_weight)

    # L-ensemble 核矩阵: L_ij = q_i * (v_i · v_j) * q_j
    S = normed @ normed.T           # (N, N) 余弦相似度
    L = np.outer(q, q) * S          # (N, N)

    # 为数值稳定性添加微小对角正则化
    L += np.eye(N) * 1e-8

    # 贪心选择 (基于 Cholesky 增量分解)
    selected = []
    # 维护 V 矩阵用于增量 Cholesky
    # 这里用简化版: O(N·k²)
    c = np.zeros((k, N))  # Cholesky 增量列
    d = np.diag(L).copy()  # 对角元素（初始边际增益）

    for j in range(k):
        # 边际增益 = d[i] (当前条件方差)
        # 排除已选的
        d_masked = d.copy()
        for s in selected:
            d_masked[s] = -float("inf")

        best = int(np.argmax(d_masked))
        selected.append(best)

        if j == k - 1:
            break

        # 更新 Cholesky 增量
        if d[best] < 1e-10:
            break

        c[j, :] = L[best, :]
        for i in range(j):
            c[j, :] -= c[i, best] * c[i, :]
        c[j, :] /= math.sqrt(d[best])

        # 更新对角方差
        d -= c[j, :] ** 2
        d = np.maximum(d, 0.0)

    return selected


# =========================================================================== #
#  3. Entity 共现增益
# =========================================================================== #

def apply_cooccurrence_boost(
    scores: Dict[int, float],
    cooccurrence_map: Dict[int, List[Tuple[int, int]]],
    scale: float = 0.10,
    max_neighbors: int = 10,
) -> Dict[int, float]:
    """
    在扩散分数之上叠加 Entity 共现增益。

    参数:
        scores:           {memory_id: score} 当前扩散分数
        cooccurrence_map: {entity_id: [(neighbor_entity_id, co_count), ...]}
        scale:            增益系数
        max_neighbors:    每个 Entity 最多取的共现邻居数

    返回:
        增强后的 scores（原地修改并返回）
    """
    boost_additions: Dict[int, float] = {}

    for entity_id, score in scores.items():
        if entity_id not in cooccurrence_map:
            continue

        neighbors = cooccurrence_map[entity_id][:max_neighbors]
        for neighbor_id, co_count in neighbors:
            bonus = score * math.log(1.0 + co_count) * scale
            if neighbor_id in boost_additions:
                boost_additions[neighbor_id] = max(
                    boost_additions[neighbor_id], bonus
                )
            else:
                boost_additions[neighbor_id] = bonus

    # 合并增益
    for nid, bonus in boost_additions.items():
        scores[nid] = scores.get(nid, 0.0) + bonus

    return scores
