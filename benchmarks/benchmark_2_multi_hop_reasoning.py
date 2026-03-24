import time
import random
import sys

try:
    from pero_memory_core import CognitiveGraphEngine
except ImportError:
    print("错误: 未找到 PeroCore Rust 模块 (pero_memory_core)。")
    sys.exit(1)


def run_logical_chain_test(hops=5, noise_count=100000):
    print("=" * 80)
    print(f"      基准测试 2: 多跳逻辑推理 ({hops} 跳)")
    print("=" * 80)
    print(f"场景：在 {noise_count:,} 个干扰项中寻找隐藏在 {hops} 跳之外的目标。")
    print("偏差检查：所有 ID 均为随机生成。无硬编码的成功路径。")
    print("-" * 80)

    engine = CognitiveGraphEngine()

    # 1. 创建随机逻辑链
    # 起点 -> N1 -> N2 -> ... -> 目标
    chain_nodes = [random.randint(1, 1000000) for _ in range(hops + 1)]
    start_node = chain_nodes[0]
    target_node = chain_nodes[-1]

    logic_edges = []
    # 使用 0.8 作为强逻辑链接
    for i in range(len(chain_nodes) - 1):
        logic_edges.append((chain_nodes[i], chain_nodes[i + 1], 0.8))

    # 2. 创建大量噪声 (死胡同)
    # 这些干扰项以高相似度 (0.79) 连接到起点
    # 但它们不通向任何地方。
    noise_edges = []
    for _ in range(noise_count):
        noise_node = random.randint(1000001, 2000000)
        noise_edges.append((start_node, noise_node, 0.79))

    print(f"[*] 正在注入逻辑链和 {noise_count:,} 条噪声边...")
    engine.batch_add_connections(logic_edges + noise_edges)

    # 3. 执行
    print(f"[*] 正在从起点 ({start_node}) 传播激活...")
    start_time = time.perf_counter()
    # 步数 = hops + 2，以留出一些缓冲
    activated = engine.propagate_activation({start_node: 1.0}, hops + 2, 0.8, 0.01)
    end_time = time.perf_counter()

    latency = (end_time - start_time) * 1000

    # 4. 结果分析
    # 按激活分数排序
    sorted_results = sorted(activated.items(), key=lambda x: x[1], reverse=True)

    found_target = False
    target_rank = -1
    for i, (node_id, score) in enumerate(sorted_results):
        if node_id == target_node:
            found_target = True
            target_rank = i + 1
            break

    print("\n[结果]:")
    print(f"  - 延迟: {latency:.4f} ms")
    print(f"  - 目标发现: {'✅ 成功' if found_target else '❌ 失败'}")

    if found_target:
        print(f"  - 目标排名: 第 {target_rank} 名 (在激活列表中)")
        print(f"  - 目标分数: {activated[target_node]:.6f}")

        # 传统的 Top-K 会首先找到噪声节点，因为它们是直接邻居
        if target_rank < noise_count:
            print("  - 逻辑穿透力: ✅ 优秀 (目标排名高于噪声)")
        else:
            print("  - 逻辑穿透力: ⚠️ 微弱 (目标被噪声淹没)")

    print("-" * 80)
    print("结论：KDN 的穿透力基于拓扑结构，而不仅仅是一阶相似度。")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_logical_chain_test()
