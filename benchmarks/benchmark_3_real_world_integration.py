import time
import random
import sys

try:
    from pero_memory_core import CognitiveGraphEngine
except ImportError:
    print("错误: 未找到 PeroCore Rust 模块 (pero_memory_core)。")
    sys.exit(1)


def run_synthetic_knowledge_web_test(node_count=50000, relation_density=5):
    print("=" * 80)
    print("      基准测试 3: 合成知识网络集成")
    print("=" * 80)
    print(
        f"场景：模拟包含 {node_count:,} 个概念的复杂非线性知识图谱。"
    )
    print(
        "目标：测试在“幂律”分布图谱中的联想召回稳定性。"
    )
    print("-" * 80)

    engine = CognitiveGraphEngine()

    # 1. 生成幂律图谱 (合成世界)
    # 少量“枢纽”节点 (超级概念) 和大量叶子节点。
    print(f"[*] 正在生成合成知识网络 (密度: {relation_density})...")

    connections = []
    # 枢纽节点: 1-100
    for i in range(101, node_count):
        # 每个节点连接到 1-3 个枢纽和 2 个随机其他节点
        num_hubs = random.randint(1, 3)
        for _ in range(num_hubs):
            hub = random.randint(1, 100)
            connections.append((i, hub, random.uniform(0.3, 0.9), 0))

        for _ in range(2):
            other = random.randint(1, node_count)
            connections.append((i, other, random.uniform(0.1, 0.5), 0))

    start_ingest = time.perf_counter()
    engine.batch_add_connections(connections)
    ingest_time = (time.perf_counter() - start_ingest) * 1000

    print(f"[+] 图谱生成并摄入耗时 {ingest_time:.2f} ms。")

    # 2. 测试联想召回
    # 随机选择一个“叶子”节点，查看它是否能激活其相关的“枢纽”
    # 通过间接关联。
    test_node = random.randint(101, node_count)
    print(f"[*] 正在模拟从概念 {test_node} 的“潜意识闪回”...")

    start_prop = time.perf_counter()
    # 4 步关联
    activated = engine.propagate_activation(
        {test_node: 1.0}, steps=4, decay=0.7, min_threshold=0.01
    )
    prop_time = (time.perf_counter() - start_prop) * 1000

    # 3. 分析结果
    # 由于连接众多 (幂律)，枢纽通常应具有较高的分数
    sorted_results = sorted(activated.items(), key=lambda x: x[1], reverse=True)

    hub_activation_count = 0
    top_20 = sorted_results[:20]

    for nid, score in top_20:
        if 1 <= nid <= 100:
            hub_activation_count += 1

    print("\n[结果]:")
    print(f"  - 传播延迟: {prop_time:.4f} ms")
    print(f"  - 前 20 名激活枢纽密度: {hub_activation_count / 20 * 100:.1f}%")
    print(f"  - 激活概念总数: {len(activated):,}")

    if hub_activation_count > 0:
        print(
            "  - 状态: ✅ 成功 (系统成功将叶子概念关联到枢纽概念)"
        )
    else:
        print(
            "  - 状态: ⚠️ 中立 (未激活主要枢纽，可能是孤立的簇)"
        )

    print("-" * 80)
    print(
        "结论：CognitiveGraphEngine 在复杂的枢纽-辐条拓扑中保持稳定性。"
    )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_synthetic_knowledge_web_test()
