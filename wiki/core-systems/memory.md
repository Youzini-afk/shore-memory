# 记忆系统 (Memory System) - GraphRAG

PeroCore 的记忆系统是一个增强型的 **GraphRAG（基于图的检索增强生成）** 数据库。它在传统向量检索的基础上，引入了 **加权图遍历 (Weighted Graph Traversal)** 机制，让 AI 能够通过逻辑关联检索信息，而不仅仅是关键词匹配。

## 1. 核心架构 (Core Architecture)

记忆系统采用 **Python + Rust** 的混合架构，兼顾了业务逻辑的灵活性和计算的高性能。

Python 层负责存储和业务逻辑，Rust 层作为计算引擎处理向量搜索和图谱遍历。

<ArchitectureGraph />

## 2. 核心组件 (Core Components)

### 2.1. 图遍历引擎 (Graph Traversal Engine)

位于 `backend/rust_core`，这是记忆系统的核心。它维护了一个内存中的动态图结构。

- **PEDSA 算法 (Parallel Energy-Decay Spreading Activation)**:
  这是我们核心的加权图遍历算法。当一个记忆节点被检索命中（例如通过语义搜索），搜索算法会沿着关联边（Edges）向四周进行加权传播。
  - **权重衰减 (Decay)**: 传播分数在多跳过程中会随距离衰减，确保只有真正相关的上下文被检索。
  - **并行计算**: 利用 Rust 的并发特性，高效处理大规模节点的遍历。

- **Simulated CSR (Compressed Sparse Row)**:
  为了极致的内存效率，我们在 Rust 中使用 `SmallVec` 实现了一种动态的邻接表结构，模拟 CSR 的紧凑性，同时支持动态更新。这使得我们能够在有限的内存中存储数百万级的关联关系。

### 2.2. 向量检索引擎 (Vector Search Engine)

同样位于 `backend/rust_core`。

- **SIMD 加速**: 利用 AVX2 (x86) 或 NEON (ARM) 指令集加速向量点积运算（Cosine Similarity）。
- **功能**: 负责将用户的自然语言输入转化为高维空间中的坐标，并快速定位图谱中的"入口节点"。

### 2.3. 存储层 (Storage Layer)

位于 `backend/models.py` 和 `backend/services/memory_service.py`。

<MemoryNetworkGraph />

- **Memory Table**: 存储记忆的具体内容、Embedding 向量和重要性权重。
- **MemoryRelation Table**: 存储记忆之间的关联（Edges），定义了图谱的拓扑结构。
- **ConversationLog**: 对话日志（Conversation Log），用于暂存短期对话流。

## 3. 记忆动力学 (Memory Dynamics)

PeroCore 的记忆不是静态存储的，而是具有动态权重，随时间推移和访问频率而变化。

### 3.1. 权重计算公式 (Weight Calculation)

每个记忆节点在检索时的最终得分（Retrieval Score）由以下公式决定：

$$ Score = (Sim \times 0.7) + ClusterBonus + (Importance \times 0.3 \times Decay(t)) + RecencyBonus $$

- **Sim (Similarity)**: 向量检索的原始相似度分数。
- **ClusterBonus**: **记忆簇 (Memory Cluster)** 奖励。如果当前对话意图命中特定的簇（如"计划"、"创造"、"反思"），且记忆节点属于该簇，则给予额外加分（+0.15）。这有助于让 AI 在特定语境下更"专注"。
- **Importance**: 记忆的基础重要性（归一化到 0-1），由 Scorer 在写入时评估。
- **Decay(t)**: **艾宾浩斯遗忘曲线 (Ebbinghaus Forgetting Curve)**。
- **RecencyBonus**: 近期性奖励。短期记忆（<1天）会获得线性提升的额外权重，模拟"工作记忆"的高权重。

### 3.2. 权重更新机制 (Weight Update Mechanism)

我们模拟了遗忘规律，确保 AI 不会被陈旧的琐事困扰，但又能保留重要的核心事实。

- **衰减函数**: $Decay(t) = e^{-0.023 \times \Delta t_{days}}$
  - 这意味着一个记忆在 30 天后，其基于重要性的权重分量会衰减至约 50%。
  - **对抗衰减**: 每次记忆被成功检索并使用（Re-activation），其 `importance` 会获得微小提升，从而抵抗未来的衰减。这实现了"常用的知识权重更高"。

## 4. 时序与上下文 (Temporal Context)

为了解决 RAG 系统常见的"碎片化"问题（即只检索到孤立的片段，丢失了前因后果），我们引入了双向链表结构。

- **prev_id / next_id**: 每个记忆节点都存储了其前驱和后继节点的 ID。
- **上下文注入**: 在 Rust 图遍历过程中，除了语义关联，搜索也会沿着时间轴（Prev/Next）进行。
- **叙事重构**: 当检索到一个关键事件时，系统会自动拉取其前后的节点，重组为一个完整的"情景记忆 (Episodic Memory)"片段，让 AI 理解事情的来龙去脉。

## 5. 后台维护服务 (Background Services)

记忆系统的健康运行依赖于一系列后台异步服务（Workers）：

### 5.1. ScorerService (评分器)

- **职责**: 实时监听 `ConversationLog`。
- **动作**: 当一段对话结束，Scorer 会调用 LLM 分析对话内容，提取关键信息（Fact/Event），计算情感（Sentiment）和重要性，并生成新的记忆节点。
- **去噪**: 自动过滤掉"Thinking"过程和无意义的寒暄，只保留核心交互。

### 5.2. ReflectionService (整合服务)

- **职责**: 周期性维护长期记忆的质量。
- **Consolidation (记忆整合)**: 扫描那些陈旧（>3天）且重要性较低（Importance < 4）的碎片记忆。
- **压缩**: 调用 LLM 将这些碎片合并为一条更概括的"陈述性记忆"（例如将"周一吃了苹果"、"周二吃了香蕉"合并为"用户喜欢吃水果"），然后删除原始碎片。这极大地节省了存储空间并提高了检索质量。

## 6. 检索全流程详解 (Retrieval Pipeline)

当用户发送一条消息时，系统按以下步骤决定注入哪些记忆：

1.  **Trigger (触发)**:
    - 对用户输入进行 Embedding。
    - **Intent Clustering**: 检测输入是否属于特定意图簇（如"制定计划"）。
    - **Vector Recall**: 从 VectorDB 召回 Top-60 个语义相似的候选节点。

2.  **Spreading (图遍历 - Rust)**:
    - 将召回的节点作为"锚点 (Anchors)"注入图谱引擎。
    - 执行 **PEDSA** 算法，在语义网络和时间轴上进行 1-2 跳的加权遍历。
    - 收集所有被命中的节点 ID（包括锚点和被关联命中的节点）。

3.  **Ranking (排序)**:
    - 应用上述的 **权重计算公式**。
    - 结合语义分数、簇奖励、时间衰减和近期奖励，计算最终得分。
    - 截取 Top-K（通常为 10-20 个）。

4.  **Rerank (重排序)**:
    - (可选) 使用 Cross-Encoder 对 Top-K 结果进行精细的语义重排序，确保相关性最高。

5.  **Reconstruction (重构)**:
    - 将最终选定的节点格式化为自然语言文本，注入到 Prompt 的 `Context` 部分。

## 7. 数据结构 (Data Structures)

### 7.1. Memory Node (记忆节点)

```python
class Memory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str          # 记忆内容
    tags: str = ""        # 索引标签
    importance: int = 1   # 基础权重
    embedding_json: str   # 向量数据 (JSON string)

    # 双向链表结构，用于维护时序上下文
    prev_id: Optional[int]
    next_id: Optional[int]
```

### 7.2. Relation Edge (关联边)

```python
class MemoryRelation(SQLModel, table=True):
    source_id: int        # 源节点 ID
    target_id: int        # 目标节点 ID
    strength: float       # 连接权重 (决定传播效率)
    relation_type: str    # 关系类型 (e.g., "causes", "is_a", "related_to")
```

## 8. 开发者指南 (Developer Guide)

如果你需要修改记忆系统，请参考以下文件：

- **核心算法 (Rust)**: `backend/rust_core/src/lib.rs` (包含 `CognitiveGraphEngine` 实现)
- **向量搜索 (Rust)**: `backend/rust_core/src/intent_engine.rs`
- **业务编排 (Python)**: `backend/services/memory_service.py`
- **数据模型 (Python)**: `backend/models.py`
