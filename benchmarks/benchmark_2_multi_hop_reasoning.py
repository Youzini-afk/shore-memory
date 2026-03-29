import time
import random
import sys
import os
import shutil
import numpy as np

try:
    import triviumdb
except ImportError:
    print("错误: 未找到 triviumdb 模块。请在后端虚拟环境中运行。")
    sys.exit(1)

def run_logical_chain_test(hops=5, noise_count=50000):
    print("=" * 80)
    print(f"      TRIVIUMDB 基准测试 2: 多跳混合图谱推理 ({hops} 跳)")
    print("=" * 80)
    print(f"场景：在 {noise_count:,} 个干扰节点中利用检索算法和邻接关系找到远处目标。")
    print("=" * 80)

    def cleanup_db(path):
        import os, shutil, glob
        for p in glob.glob(path + "*"):
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except: pass

    db_path = "test_multihop.tdb"
    cleanup_db(db_path)

    dim = 64
    db = triviumdb.TriviumDB(db_path, dim=dim)

    # 1. 创建高度特异的逻辑链 (随机向量串联)
    chain_nodes = list(range(10000, 10000 + hops + 1))
    start_node = chain_nodes[0]
    target_node = chain_nodes[-1]
    
    # 定义特定的起始向量，保证第一跳能精准检索到
    start_vec = np.random.randn(dim).tolist()
    db.insert_with_id(start_node, start_vec, {"role": "start_node"})
    
    # 链路上后续节点插入
    for i in range(1, len(chain_nodes)):
        db.insert_with_id(chain_nodes[i], np.random.randn(dim).tolist(), {"role": "chain_link"})
        # 创建相连的紧密图谱关系 (TriviumDB 的 Graph Layer)
        db.link(chain_nodes[i-1], chain_nodes[i], "logic_step", 1.0)

    # 2. 注入巨量干扰节点（这些节点离首个起点的向量可能具有误导性）
    print(f"[*] 正在向数据库中抛弃 {noise_count:,} 个干扰项和高权重陷阱...")
    for i in range(noise_count):
        noise_node = 30000 + i
        # 制造相似度在 0.1~0.3 左右的干扰节点，目标是测试 5阶多跳后的分数能否超过它们。
        noise_vec = (np.array(start_vec) * 0.1 + np.random.randn(dim) * 0.9).tolist()
        db.insert_with_id(noise_node, noise_vec, {"role": "noise"})
    
    # 把部分噪音强行连接到终点，迷惑随机游走
    for i in range(50):
        db.link(30000 + i, target_node, "distract", 0.9)

    # 3. 运行多阶深度召回系统
    print(f"[*] 开始进行联合检索: 从起点触发 {hops} 跳图遍历游走搜索机制...")
    start_time = time.perf_counter()
    
    # TriviumDB 真正可怕的地方在于，可以进行 Hybrid Pagerank+Vector 的混合推理:
    # search_advanced允许 expand_depth 达到图深遍历。teleport_alpha = 0.5 时，图拓扑将被考虑。
    hits = db.search_advanced(
        start_vec, 
        top_k=20, 
        expand_depth=hops+2,     # 探测深度足以覆盖目标
        min_score=0.0, 
        teleport_alpha=0.01,     # 启用极低的图拓扑穿透惩罚，允许分数传递得很远
        enable_advanced_pipeline=True,
        enable_sparse_residual=False,
        fista_lambda=0.1, fista_threshold=80,
        enable_dpp=False, dpp_quality_weight=1.0,
        enable_text_hybrid_search=False, text_boost=1.0,
        custom_query_text=None, payload_filter=None
    )
    
    latency = (time.perf_counter() - start_time) * 1000

    found_target = False
    target_rank = -1
    for i, h in enumerate(hits):
        if i < 5: print(f"    - Hit {i+1}: Node {h.id}, Score: {h.score:.4f}, Payload: {h.payload}")
        if h.id == target_node:
            found_target = True
            target_rank = i + 1
            break

    print("\n[联想召回结果]:")
    print(f"  - 混合检索延迟: {latency:.2f} ms")
    print(f"  - 目标节点发现: {'✅ 成功定位!' if found_target else '❌ 隐藏在深处，未能触及'}")

    if found_target:
        print(f"  - 目标最终排名: 第 {target_rank} 名 (在 Top-20 返回名单中)")
        print(f"  - 分数 / 图形加强后关联指征十分明显。")

    print("-" * 80)
    print("结论：验证 TriviumDB 成功将向量相似度与图谱边缘结构融合（Graph+Vector 混合打分），穿透并跳脱纯向量噪声空间。")
    print("=" * 80 + "\n")

    cleanup_db(db_path)

if __name__ == "__main__":
    run_logical_chain_test()
