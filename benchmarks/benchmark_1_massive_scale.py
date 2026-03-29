import time
import random
import psutil
import os
import sys
import string
import shutil
import numpy as np

try:
    import triviumdb
except ImportError:
    print("错误: 未找到 triviumdb 模块。请在后端虚拟环境中运行。")
    sys.exit(1)

def get_mem_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def run_massive_scale_test(scale=200000, dim=128):
    print("=" * 80)
    print(f"      TriviumDB 极速版基准测试 1: 大规模性能测试 ({scale:,} 条内存体)")
    print("=" * 80)
    print("目标：测量 TriviumDB (HNSW + R-tree + SQLite) 的大批次写入吞吐与检索延迟。")
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
    
    db_path = "test_massive.tdb"
    cleanup_db(db_path)

    initial_mem = get_mem_mb()
    
    # 1. 实例化新数据库
    start_init = time.perf_counter()
    db = triviumdb.TriviumDB(db_path, dim=dim)
    print(f"[*] 数据库初始化完成: {(time.perf_counter()-start_init)*1000:.2f} ms")

    # 2. 摄入测试
    batch_size = 50000
    print(f"[*] 正在分批插入 {scale:,} 个高维向量，每批 {batch_size:,} 条...")
    start_ingest = time.perf_counter()

    for i in range(0, scale, batch_size):
        b_start = time.perf_counter()
        actual_size = min(batch_size, scale - i)
        
        # 为了测试真实性能，需要不断调用 insert_with_id
        # TriviumDB 内部并发极强，我们可以使用多线程或单线程。此处使用单线程插入循环。
        for j in range(actual_size):
            node_id = i + j + 1
            vec = np.random.rand(dim).tolist()
            payload = {"type": "concept", "val": random.random()}
            db.insert_with_id(node_id, vec, payload)
        
        b_end = time.perf_counter()
        print(f"  - 批次 {i // batch_size + 1}: {(b_end - b_start):.2f} s")

    total_ingest_time = time.perf_counter() - start_ingest
    final_mem = get_mem_mb()
    mem_used = final_mem - initial_mem

    print("\n[摄入指标]:")
    print(f"  - 总耗时: {total_ingest_time:.4f} s")
    print(f"  - 单条耗时: {total_ingest_time * 1000000 / scale:.2f} μs / 条")
    print(f"  - 内存开销: {mem_used:.2f} MB")
    
    # 3. 追加关系图谱测试 (随机生成边)
    print("\n[*] 正在向图中注入 100,000 条随机相连记忆关联...")
    edges = 100000
    e_start = time.perf_counter()
    for _ in range(edges):
        src = random.randint(1, scale)
        dst = random.randint(1, scale)
        db.link(src, dst, "random_link", round(random.uniform(0.1, 1.0), 2))
    print(f"  - 图边创建耗时: {(time.perf_counter() - e_start):.2f} s")

    # 4. 融合检索引擎测试 (混合 HNSW 检索 + 图遍历)
    print("\n[*] 正在测试 TriviumDB 多参数混合检索延迟 (100 次迭代)...")
    latencies = []
    
    # 我们测试开启高级组合流形管道并且允许进行深度遍历的情况
    for _ in range(100):
        q_vec = np.random.rand(dim).tolist()
        p_start = time.perf_counter()
        
        # 参数: query_vector, top_k=20, expand_depth=2, min_score, teleport_alpha=0.1, etc...
        db.search_advanced(
            q_vec, 20, 2, 0.0, 0.1, True, False, 0.1, 80, False, 1.0, False, 1.0, None, None
        )
        latencies.append((time.perf_counter() - p_start) * 1000)

    avg_lat = sum(latencies) / len(latencies)
    sorted_lat = sorted(latencies)
    p95_lat = sorted_lat[int(len(latencies) * 0.95)]
    p99_lat = sorted_lat[int(len(latencies) * 0.99)]

    print(f"  - 平均检索延迟: {avg_lat:.2f} ms")
    print(f"  - P95 延迟:     {p95_lat:.2f} ms")
    print(f"  - P99 延迟:     {p99_lat:.2f} ms")

    print("-" * 80)
    print("结论：验证了 TriviumDB 向量引擎在真实情况下的超高速插入及联合查询表现。")
    print("=" * 80 + "\n")

    # 清理测试
    cleanup_db(db_path)

if __name__ == "__main__":
    test_scale = 200000
    if len(sys.argv) > 1:
        test_scale = int(sys.argv[1])
    run_massive_scale_test(test_scale)
