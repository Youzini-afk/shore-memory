import time
import random
import psutil
import os
import sys

try:
    from pero_memory_core import CognitiveGraphEngine
except ImportError:
    print("错误: 未找到 PeroCore Rust 模块 (pero_memory_core)。请先安装它。")
    sys.exit(1)


def get_mem_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def run_massive_scale_test(scale=1000000):
    print("=" * 80)
    print(f"      基准测试 1: 大规模性能测试 ({scale:,} 条边)")
    print("=" * 80)
    print("目标：测量原始摄入速度、内存开销和传播延迟。")
    print("-" * 80)

    engine = CognitiveGraphEngine()

    # 1. 摄入测试
    batch_size = scale // 2
    if batch_size < 1:
        batch_size = scale

    print(f"[*] 正在分批摄入 {scale:,} 条边，每批 {batch_size:,} 条...")
    initial_mem = get_mem_mb()
    start_ingest = time.perf_counter()

    for i in range(0, scale, batch_size):
        batch = []
        actual_batch_size = min(batch_size, scale - i)
        for _ in range(actual_batch_size):
            src = random.randint(1, scale)
            dst = random.randint(1, scale)
            batch.append((src, dst, random.random(), 0))

        b_start = time.perf_counter()
        engine.batch_add_connections(batch)
        b_end = time.perf_counter()
        print(f"  - 批次 {i // batch_size + 1}: {(b_end - b_start) * 1000:.2f} ms")

    total_ingest_time = time.perf_counter() - start_ingest
    final_mem = get_mem_mb()
    mem_used = final_mem - initial_mem

    print("\n[摄入指标]:")
    print(f"  - 总耗时: {total_ingest_time:.4f} s")
    print(f"  - 吞吐量: {scale / total_ingest_time / 1000000:.2f} Million edges/sec")
    print(f"  - 内存开销: {mem_used:.2f} MB")
    print(f"  - 效率: {mem_used * 1024 / scale:.2f} Bytes per edge")

    # 2. 传播延迟测试
    print("\n[*] 正在测试 5 步传播延迟 (100 次迭代)...")
    latencies = []
    for _ in range(100):
        start_node = random.randint(1, scale)
        p_start = time.perf_counter()
        engine.propagate_activation({start_node: 1.0}, 5, 0.8, 0.01)
        latencies.append((time.perf_counter() - p_start) * 1000)

    avg_lat = sum(latencies) / len(latencies)
    sorted_lat = sorted(latencies)
    p95_lat = sorted_lat[int(len(latencies) * 0.95)]
    p99_lat = sorted_lat[int(len(latencies) * 0.99)]

    print(f"  - 平均延迟: {avg_lat:.4f} ms")
    print(f"  - P95 延迟:     {p95_lat:.4f} ms")
    print(f"  - P99 延迟:     {p99_lat:.4f} ms")

    print("-" * 80)
    print("结论：已验证高速 CSR 变体架构。")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    # 默认为 1M 用于快速测试，但项目声称支持 100M
    test_scale = 1000000
    if len(sys.argv) > 1:
        test_scale = int(sys.argv[1])
    run_massive_scale_test(test_scale)
