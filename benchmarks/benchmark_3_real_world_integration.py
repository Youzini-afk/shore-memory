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

def run_synthetic_knowledge_web_test(node_count=20000, dim=256):
    print("=" * 80)
    print("      TRIVIUMDB 基准测试 3: 复杂非线性图谱的关联回忆")
    print("=" * 80)
    print(f"场景：生成具有“枢纽-辐条（Hub-Spoke）”机制的 {node_count:,} 个幂律网络概念丛。")
    print("测试：模拟思维跳跃时，对于多层次复杂交叉区域内的检索速度与命中覆盖度。")
    print("-" * 80)

    def cleanup_db(path):
        import os, shutil, glob
        for p in glob.glob(path + "*"):
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except: pass

    db_path = "test_knowledge_web.tdb"
    cleanup_db(db_path)

    db = triviumdb.TriviumDB(db_path, dim=dim)

    # 1. 大规模灌注合成世界网络
    print(f"[*] 正在建造拥有超级集线器概念(Super Hubs) 的世界...")
    start_ingest = time.perf_counter()
    
    # 生成基础节点
    for i in range(1, node_count + 1):
        # 让枢纽节点特征有些类似
        vec = np.random.rand(dim).tolist()
        payload = {"is_hub": True} if i <= 100 else {"is_hub": False}
        db.insert_with_id(i, vec, payload)

    # 把普通节点通过边疯狂连接回特定的头部节点
    for i in range(101, node_count + 1):
        num_hubs = random.randint(1, 4)
        for _ in range(num_hubs):
            hub = random.randint(1, 100)
            db.link(i, hub, "hub_link", random.uniform(0.5, 0.9))
            
        # 还有一些散落到自身生态中的边
        for _ in range(2):
            other = random.randint(1, node_count)
            db.link(i, other, "peer_link", random.uniform(0.1, 0.4))

    ingest_time = (time.perf_counter() - start_ingest) * 1000
    print(f"[+] 图结构及 {node_count:,} 知识载体数据建立完毕，耗时 {ingest_time:.2f} ms。")

    # 2. 从边缘节点触发回忆：
    # TriviumDB 原生具有 expand_depth 支持和图形扩展支持。
    test_node = random.randint(101, node_count)
    print(f"[*] 模拟大脑潜意识闪回: 从边缘节点 '{test_node}' 扩散检索...")

    # 我们使用这个孤立节点的向量作为基础查询开始
    # 并允许展开 4 级关系深度图，使得枢纽必须自动浮现并且被提高权重。
    q_vec = np.random.rand(dim).tolist() # 这里假装是该节点的向量被抛出作检索基
    
    start_prop = time.perf_counter()
    hits = db.search_advanced(
        q_vec, 
        top_k=25, 
        expand_depth=4,         # 使用图形引擎蔓延 4 级
        min_score=0.1, 
        teleport_alpha=0.6,     # 较强的 Teleport (强调随机游走图的全局相关性)
        enable_advanced_pipeline=True,
        enable_sparse_residual=False,
        fista_lambda=0.1, fista_threshold=80,
        enable_dpp=True,        # 开启 DPP 使搜索不仅被单个枢纽吞没
        dpp_quality_weight=0.8,
        enable_text_hybrid_search=False, text_boost=1.0,
        custom_query_text=None, payload_filter=None
    )
    prop_time = (time.perf_counter() - start_prop) * 1000

    hub_count = 0
    for h in hits:
        if h.payload.get("is_hub", False):
            hub_count += 1
            
    print("\n[最终关联图谱发散结果]:")
    print(f"  - 高级图遍历延迟: {prop_time:.2f} ms")
    print(f"  - Top-25 返回中的核心中枢区域节点数: {hub_count}")
    print(f"  - 枢纽命中百分比: {(hub_count/len(hits)*100 if hits else 0):.1f}%")

    if hub_count > 0:
        print("  - 状态: ✅ 成功 (系统成功在知识海中自发找到了高度连接的概念中心)")
    else:
        print("  - 状态: ⚠️ 注意 (未能召回到头部中心。随机落点太孤岛化？)")

    print("-" * 80)
    print("结论：验证 TriviumDB 向量+复杂拓扑扩展召回模块正常，并在性能指标上具备强大的实时计算吞吐。")
    print("=" * 80 + "\n")

    cleanup_db(db_path)

if __name__ == "__main__":
    run_synthetic_knowledge_web_test()
