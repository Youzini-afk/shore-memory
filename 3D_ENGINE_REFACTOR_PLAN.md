# 3D 渲染引擎重构：后续实施方案建议

在完成 [parser.rs](src/components/avatar/native/src/parser.rs) 的核心几何体解析逻辑重构后，为了实现 [REFACTORING_3D_ENGINE.md](REFACTORING_3D_ENGINE.md) 中定义的长期目标，建议从以下三个维度推进下一步工作：

---

## 方案 A：完善 Rust 安全核心 (Security Core)

**优先级：极高 (推荐)**

该方案旨在将当前的解析逻辑提升为真正的资产保护层。

### 1. 核心任务

- **定义 `.pero` 文件格式**：
  - 设计二进制文件头（Magic Number: `PERO`）。
  - 实现元数据段（版本、加密算法 ID）与加密数据段的划分。
- **实现解密逻辑**：
  - 在 Rust 侧集成加密库。
  - 实现基于密钥的解密流，确保数据在内存中直接解析，不落地 JSON。
- **完善 N-API 导出**：
  - 导出 `load_pero_model` 函数。
  - 实现与 [PeroSecureProvider.ts](src/components/avatar/lib/adapter/PeroSecureProvider.ts) 的完整对接。

### 2. 预期效果

- 模型资产（JSON/PNG）得到加密保护，无法被简单提取。
- 建立起从二进制流到 3D 场景的完整安全闭环。

---

## 方案 B：TS 侧彻底解耦 (TS Decoupling)

**优先级：高**

该方案旨在消除前端代码中所有关于特定模型（如 Rossi）的硬编码引用。

### 1. 核心任务

- **实现通用加载流程**：
  - 重构 [BedrockAvatar.vue](src/components/avatar/BedrockAvatar.vue)，使其基于 [IAvatarManifest.ts](src/components/avatar/lib/adapter/IAvatarManifest.ts) 驱动。
- **清单化配置**：
  - 将 Rossi 的所有参数（部件映射、Z轴偏移、材质粗糙度等）提取到 `manifest.json` 或嵌入 `.pero` 文件。
- **抽象组件逻辑**：
  - 将功能按钮的生成逻辑完全交给适配器层。

### 2. 预期效果

- 代码中不再出现 "Rossi" 字样。
- 只需更换一个 Manifest 文件即可加载完全不同的模型。

---

## 方案 C：几何体生成性能极致优化

**优先级：中**

该方案旨在利用 Rust 的内存操作优势，进一步压榨加载性能。

### 1. 核心任务

- **原生数组返回**：
  - 修改 N-API 接口，不再返回 `cubes_json` 字符串。
  - 在 Rust 侧直接构建并返回 `Float32Array` (顶点/UV) 和 `Uint16Array` (索引)。
- **批量数据传输**：
  - 减少 N-API 的调用次数和序列化开销。

### 2. 预期效果

- 消除 JS 侧 `JSON.parse` 的开销。
- 大型模型的加载速度提升 30%~50%。

---

## 建议行动建议

**推荐路径：A -> B -> C**

1. **先做 A**：趁热打铁，把 Rust 侧的安全能力补全。
2. **再做 B**：在有了安全加载能力后，通过解耦让引擎支持多模型切换。
3. **最后做 C**：在系统稳定后进行性能压榨。
