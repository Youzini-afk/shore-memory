"""
基准测试 4: 检索增强数学算法消融实验

消融实验设计:
  1. 算法正确性验证 (Rust vs Python 结果一致性)
  2. 性能对比 (Rust vs Python 延迟 + 加速比)
  3. 管道组合消融 (逐步开关 NMF/FISTA/DPP 观察检索质量变化)

前置条件:
  - pero_memory_core (Rust) 已安装
  - numpy 已安装

实验原则:
  - 所有数据合成、随机种子固定以保证可复现
  - 延迟指标取 100 次中位数 (排除首次 JIT 预热)
"""

import sys
import time
import numpy as np

# --------------------------------------------------------------------------- #
#  导入算法实现
# --------------------------------------------------------------------------- #

# Python (NumPy) 实现  —  直接导入内部函数
sys.path.insert(0, "../backend")

try:
    from services.memory.retrieval_enhancer import (
        _sparse_code_residual_python as py_fista,
        _dpp_greedy_select_python as py_dpp,
        nmf_query_analysis as py_nmf_analysis,
    )
    PY_AVAILABLE = True
except ImportError:
    PY_AVAILABLE = False
    print("[WARN] Python retrieval_enhancer not found, skipping Python baseline.")

# Rust 实现
try:
    from pero_memory_core import RetrievalMath
    _rust = RetrievalMath()
    RUST_AVAILABLE = True
except ImportError:
    _rust = None
    RUST_AVAILABLE = False
    print("[WARN] Rust RetrievalMath not found, skipping Rust tests.")


# --------------------------------------------------------------------------- #
#  数据生成
# --------------------------------------------------------------------------- #

def generate_test_data(m=50, d=384, seed=42):
    """生成合成 Entity 嵌入矩阵和查询向量 (固定种子)"""
    rng = np.random.RandomState(seed)
    entity_vecs = rng.randn(m, d).astype(np.float32)
    # L2 归一化
    norms = np.linalg.norm(entity_vecs, axis=1, keepdims=True)
    entity_vecs = entity_vecs / np.maximum(norms, 1e-10)

    query_vec = rng.randn(d).astype(np.float32)
    query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-10)

    return entity_vecs, query_vec


def generate_dpp_candidates(n=60, d=384, seed=42):
    """生成 DPP 候选集"""
    rng = np.random.RandomState(seed)
    vecs = rng.randn(n, d).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / np.maximum(norms, 1e-10)
    scores = np.abs(rng.randn(n).astype(np.float32)) * 0.5 + 0.5  # [0.5, 1.0]
    return vecs, scores


# --------------------------------------------------------------------------- #
#  实验 1: 算法正确性 (Rust vs Python 一致性)
# --------------------------------------------------------------------------- #

def experiment_1_correctness():
    print("\n" + "=" * 80)
    print("      Exp 1: Correctness (Rust ~= Python)")
    print("=" * 80)

    if not PY_AVAILABLE or not RUST_AVAILABLE:
        print("  [WARN] Need both Python and Rust to run correctness check.")
        return

    entity_vecs, query_vec = generate_test_data(m=30, d=64, seed=123)

    # --- FISTA ---
    py_alpha, py_residual, py_norm = py_fista(query_vec, entity_vecs, 0.1, 80)
    r_alpha, r_residual, r_norm = _rust.sparse_code_residual(
        query_vec.tolist(), entity_vecs.tolist(), 0.1, 80
    )
    r_alpha = np.array(r_alpha, dtype=np.float32)
    r_residual = np.array(r_residual, dtype=np.float32)

    fista_alpha_diff = np.max(np.abs(py_alpha - r_alpha))
    fista_norm_diff = abs(py_norm - r_norm)
    fista_pass = fista_alpha_diff < 0.05 and fista_norm_diff < 0.05

    print(f"\n  [FISTA] alpha 最大差异: {fista_alpha_diff:.6f}")
    print(f"  [FISTA] 残差范数差异:  {fista_norm_diff:.6f}")
    print(f"  [FISTA] Result: {'PASS' if fista_pass else 'FAIL'}")

    # --- DPP ---
    dpp_vecs, dpp_scores = generate_dpp_candidates(n=30, d=64, seed=456)
    py_sel = py_dpp(dpp_vecs, dpp_scores, 10, 1.0)
    r_sel = _rust.dpp_greedy_select(
        dpp_vecs.tolist(), dpp_scores.tolist(), 10, 1.0
    )
    # DPP 贪心选择在数值精度差异下可能略有不同，重叠度 > 80% 即可
    overlap = len(set(py_sel) & set(r_sel))
    dpp_pass = overlap >= 8  # 至少 80% 重叠

    print(f"\n  [DPP]  Python 选择: {sorted(py_sel)}")
    print(f"  [DPP]  Rust   选择: {sorted(r_sel)}")
    print(f"  [DPP]  重叠度: {overlap}/{len(py_sel)} ({overlap / len(py_sel) * 100:.0f}%)")
    print(f"  [DPP]  Result: {'PASS' if dpp_pass else 'FAIL'}")

    print("-" * 80)


# --------------------------------------------------------------------------- #
#  实验 2: 性能对比 (Rust vs Python)
# --------------------------------------------------------------------------- #

def bench_fn(fn, args, n_iter=100, warmup=5):
    """执行 n_iter 次，返回中位延迟 (ms)"""
    # 预热
    for _ in range(warmup):
        fn(*args)

    times = []
    for _ in range(n_iter):
        t0 = time.perf_counter()
        fn(*args)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    times.sort()
    median = times[len(times) // 2]
    p95 = times[int(len(times) * 0.95)]
    return median, p95


def experiment_2_performance():
    print("\n" + "=" * 80)
    print("      实验 2: 性能对比 (Rust vs Python)")
    print("=" * 80)
    print("  各算法执行 100 次，报告中位延迟与 P95 延迟。")
    print("-" * 80)

    # 测试多个规模
    configs = [
        {"label": "小规模 (m=20, d=384)", "m": 20, "d": 384},
        {"label": "中规模 (m=50, d=384)", "m": 50, "d": 384},
        {"label": "大规模 (m=200, d=384)", "m": 200, "d": 384},
    ]

    for cfg in configs:
        print(f"\n  >> {cfg['label']}")
        entity_vecs, query_vec = generate_test_data(m=cfg["m"], d=cfg["d"], seed=42)

        # --- FISTA ---
        results = {}
        if PY_AVAILABLE:
            med, p95 = bench_fn(py_fista, (query_vec, entity_vecs, 0.1, 80))
            results["fista_py"] = med
            print(f"    FISTA  [Python] median={med:.3f}ms  P95={p95:.3f}ms")

        if RUST_AVAILABLE:
            q_list = query_vec.tolist()
            e_list = entity_vecs.tolist()
            med, p95 = bench_fn(
                _rust.sparse_code_residual, (q_list, e_list, 0.1, 80)
            )
            results["fista_rs"] = med
            print(f"    FISTA  [Rust  ] median={med:.3f}ms  P95={p95:.3f}ms", end="")
            if "fista_py" in results:
                speedup = results["fista_py"] / max(med, 0.001)
                print(f"  → {speedup:.1f}× 加速")
            else:
                print()

        # --- DPP ---
        dpp_n = min(cfg["m"] * 3, 300)
        dpp_vecs, dpp_scores = generate_dpp_candidates(n=dpp_n, d=cfg["d"], seed=42)
        k = 20

        if PY_AVAILABLE:
            med, p95 = bench_fn(py_dpp, (dpp_vecs, dpp_scores, k, 1.0))
            results["dpp_py"] = med
            print(f"    DPP    [Python] median={med:.3f}ms  P95={p95:.3f}ms")

        if RUST_AVAILABLE:
            dv_list = dpp_vecs.tolist()
            ds_list = dpp_scores.tolist()
            med, p95 = bench_fn(
                _rust.dpp_greedy_select, (dv_list, ds_list, k, 1.0)
            )
            results["dpp_rs"] = med
            print(f"    DPP    [Rust  ] median={med:.3f}ms  P95={p95:.3f}ms", end="")
            if "dpp_py" in results:
                speedup = results["dpp_py"] / max(med, 0.001)
                print(f"  → {speedup:.1f}× 加速")
            else:
                print()

        # --- NMF ---
        if PY_AVAILABLE:
            med, p95 = bench_fn(
                py_nmf_analysis,
                (query_vec, entity_vecs, list(range(cfg["m"])), "pero", 15),
            )
            results["nmf_py"] = med
            print(f"    NMF    [Python] median={med:.3f}ms  P95={p95:.3f}ms")

        if RUST_AVAILABLE:
            q_list = query_vec.tolist()
            e_list = entity_vecs.tolist()
            ids_list = list(range(cfg["m"]))
            med, p95 = bench_fn(
                _rust.nmf_query_analysis,
                (q_list, e_list, ids_list, "pero", 15, 100),
            )
            results["nmf_rs"] = med
            print(f"    NMF    [Rust  ] median={med:.3f}ms  P95={p95:.3f}ms", end="")
            if "nmf_py" in results:
                speedup = results["nmf_py"] / max(med, 0.001)
                print(f"  → {speedup:.1f}× 加速")
            else:
                print()

    print("-" * 80)


# --------------------------------------------------------------------------- #
#  实验 3: 管道组合消融 (Pipeline Ablation)
# --------------------------------------------------------------------------- #

def simulate_retrieval_pipeline(
    query_vec, entity_vecs, entity_scores, entity_ids,
    enable_nmf=True, enable_fista=True, enable_dpp=True,
    use_rust=True,
):
    """
    模拟简化版检索管线，依次执行:
      1. (NMF) 查询分析 → novelty 指标
      2. (FISTA) 稀疏编码 → 残差向量用于二次检索
      3. (DPP) 多样性采样 → 最终选择

    返回 (selected_ids, metrics_dict, total_latency_ms)
    """
    t_start = time.perf_counter()
    metrics = {}

    # 1. NMF 查询分析
    novelty = 0.5  # 默认
    if enable_nmf:
        if use_rust and RUST_AVAILABLE:
            r = _rust.nmf_query_analysis(
                query_vec.tolist(), entity_vecs.tolist(),
                entity_ids, "pero", 15, 100,
            )
            novelty = r["novelty"][0]
            metrics["nmf_depth"] = r["semantic_depth"][0]
        elif PY_AVAILABLE:
            r = py_nmf_analysis(query_vec, entity_vecs, entity_ids, "pero", 15)
            novelty = r["novelty"]
            metrics["nmf_depth"] = r["semantic_depth"]
    metrics["novelty"] = novelty

    # 2. FISTA 稀疏编码
    residual_norm = 0.0
    bonus_ids = []
    if enable_fista and novelty > 0.3:
        if use_rust and RUST_AVAILABLE:
            alpha, residual, residual_norm = _rust.sparse_code_residual(
                query_vec.tolist(), entity_vecs.tolist(), 0.1, 80,
            )
            # 二次检索: 找残差方向上最相关的 entity
            residual = np.array(residual, dtype=np.float32)
        elif PY_AVAILABLE:
            _, residual, residual_norm = py_fista(query_vec, entity_vecs, 0.1, 80)

        if residual_norm > 0.3:
            # 用残差向量做点积排序
            res_scores = entity_vecs @ residual
            top_res = np.argsort(res_scores)[-5:][::-1]
            bonus_ids = [entity_ids[i] for i in top_res]

    metrics["residual_norm"] = residual_norm
    metrics["bonus_ids"] = bonus_ids

    # 3. DPP 多样性采样
    # 候选集 = 按原始分数排序的 Top-3k
    k = 10
    n_candidates = min(len(entity_scores), k * 3)
    top_indices = np.argsort(entity_scores)[-n_candidates:][::-1]
    candidate_vecs = entity_vecs[top_indices]
    candidate_scores = entity_scores[top_indices]

    if enable_dpp:
        if use_rust and RUST_AVAILABLE:
            selected_local = _rust.dpp_greedy_select(
                candidate_vecs.tolist(), candidate_scores.tolist(), k, 1.0,
            )
        elif PY_AVAILABLE:
            selected_local = py_dpp(candidate_vecs, candidate_scores, k, 1.0)
        else:
            selected_local = list(range(min(k, len(top_indices))))
    else:
        # 不用 DPP → 直接取 Top-K
        selected_local = list(range(min(k, len(top_indices))))

    selected_ids = [entity_ids[top_indices[i]] for i in selected_local]

    t_end = time.perf_counter()
    total_ms = (t_end - t_start) * 1000

    return selected_ids, metrics, total_ms


def experiment_3_ablation():
    print("\n" + "=" * 80)
    print("      实验 3: 管道组合消融 (Pipeline Ablation)")
    print("=" * 80)
    print("  逐步开关 NMF / FISTA / DPP，观察两个维度的变化:")
    print("  A) 总延迟 (ms)")
    print("  B) 结果多样性 (选中 ID 的平均余弦距离)")
    print("-" * 80)

    m, d = 80, 384
    entity_vecs, query_vec = generate_test_data(m=m, d=d, seed=789)
    entity_ids = list(range(m))
    # 模拟分数: 余弦相似度
    entity_scores = (entity_vecs @ query_vec).astype(np.float32)
    entity_scores = np.maximum(entity_scores, 0.01)

    # 消融组合
    ablation_configs = [
        {"label": "Full Pipeline (NMF+FISTA+DPP)", "nmf": True, "fista": True, "dpp": True},
        {"label": "No DPP (NMF+FISTA only)",       "nmf": True, "fista": True, "dpp": False},
        {"label": "No FISTA (NMF+DPP only)",        "nmf": True, "fista": False, "dpp": True},
        {"label": "No NMF (FISTA+DPP only)",         "nmf": False, "fista": True, "dpp": True},
        {"label": "DPP Only",                       "nmf": False, "fista": False, "dpp": True},
        {"label": "Baseline (Top-K, no enhancements)", "nmf": False, "fista": False, "dpp": False},
    ]

    def measure_diversity(selected_ids, entity_vecs):
        """平均两两余弦距离 (越高 = 越多样)"""
        if len(selected_ids) < 2:
            return 0.0
        vecs = entity_vecs[selected_ids]
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        normed = vecs / np.maximum(norms, 1e-10)
        sim_matrix = normed @ normed.T
        n = len(selected_ids)
        # 平均 off-diagonal similarity
        total_sim = (sim_matrix.sum() - n) / (n * (n - 1))
        return 1.0 - total_sim  # 距离 = 1 - similarity

    print(f"\n  {'配置':<42s} {'延迟(ms)':>10s} {'多样性':>10s} {'残差范数':>10s}")
    print("  " + "-" * 76)

    for cfg in ablation_configs:
        # 多次运行取中位延迟
        latencies = []
        last_selected = None
        last_metrics = None
        for _ in range(50):
            selected, metrics, lat = simulate_retrieval_pipeline(
                query_vec, entity_vecs, entity_scores, entity_ids,
                enable_nmf=cfg["nmf"],
                enable_fista=cfg["fista"],
                enable_dpp=cfg["dpp"],
                use_rust=RUST_AVAILABLE,
            )
            latencies.append(lat)
            last_selected = selected
            last_metrics = metrics

        latencies.sort()
        median_lat = latencies[len(latencies) // 2]
        diversity = measure_diversity(last_selected, entity_vecs)
        res_norm = last_metrics.get("residual_norm", 0.0)

        print(f"  {cfg['label']:<42s} {median_lat:>9.3f}  {diversity:>9.4f}  {res_norm:>9.4f}")

    print("\n  分析说明:")
    print("  - 多样性: 1.0 = 完全正交, 0.0 = 完全冗余")
    print("  - Full Pipeline 应在多样性上显著高于 Baseline (Top-K)")
    print("  - No DPP 的多样性应明显下降 (DPP 是多样性的核心贡献者)")
    print("  - No FISTA 的残差范数 = 0 (弱信号未被捕获)")
    print("-" * 80)


# --------------------------------------------------------------------------- #
#  实验 4: Rust vs Python 全管道端到端延迟
# --------------------------------------------------------------------------- #

def experiment_4_e2e():
    print("\n" + "=" * 80)
    print("      实验 4: Rust vs Python 全管道端到端对比")
    print("=" * 80)

    if not PY_AVAILABLE or not RUST_AVAILABLE:
        print("  [WARN] Need both Python and Rust for this experiment.")
        return

    m, d = 80, 384
    entity_vecs, query_vec = generate_test_data(m=m, d=d, seed=789)
    entity_ids = list(range(m))
    entity_scores = (entity_vecs @ query_vec).astype(np.float32)
    entity_scores = np.maximum(entity_scores, 0.01)

    for backend, use_rust in [("Rust ", True), ("Python", False)]:
        lats = []
        for _ in range(100):
            _, _, lat = simulate_retrieval_pipeline(
                query_vec, entity_vecs, entity_scores, entity_ids,
                enable_nmf=True, enable_fista=True, enable_dpp=True,
                use_rust=use_rust,
            )
            lats.append(lat)

        lats.sort()
        med = lats[len(lats) // 2]
        p95 = lats[int(len(lats) * 0.95)]
        print(f"  [{backend}] 全管道 median={med:.3f}ms  P95={p95:.3f}ms")

    if RUST_AVAILABLE and PY_AVAILABLE:
        # 简单再跑一次取比
        py_lats = []
        rs_lats = []
        for _ in range(100):
            _, _, lat = simulate_retrieval_pipeline(
                query_vec, entity_vecs, entity_scores, entity_ids,
                enable_nmf=True, enable_fista=True, enable_dpp=True,
                use_rust=False,
            )
            py_lats.append(lat)
            _, _, lat = simulate_retrieval_pipeline(
                query_vec, entity_vecs, entity_scores, entity_ids,
                enable_nmf=True, enable_fista=True, enable_dpp=True,
                use_rust=True,
            )
            rs_lats.append(lat)

        py_med = sorted(py_lats)[50]
        rs_med = sorted(rs_lats)[50]
        print(f"\n  总加速比: {py_med / max(rs_med, 0.001):.1f}×")

    print("-" * 80)


# --------------------------------------------------------------------------- #
#  主入口
# --------------------------------------------------------------------------- #

def main():
    print("\n" + "=" * 80)
    print("    PeroCore 检索增强算法消融实验 (Benchmark 4)")
    print("    Ablation Study: NMF / FISTA / DPP Pipeline")
    print("=" * 80)
    print(f"  Backend:  Rust={'[OK]' if RUST_AVAILABLE else '[NO]'}  "
          f"Python={'[OK]' if PY_AVAILABLE else '[NO]'}")
    print(f"  NumPy:    {np.__version__}")
    print("-" * 80)

    experiment_1_correctness()
    experiment_2_performance()
    experiment_3_ablation()
    experiment_4_e2e()

    print("\n" + "=" * 80)
    print("    消融实验全部完成")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
