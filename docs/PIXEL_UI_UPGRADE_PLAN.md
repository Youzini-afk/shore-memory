# 萌动链接：PeroperoChat！ 像素风 UI 升级技术方案 (Moe Link Edition) 🎮✨

## 1. 核心视觉设计指南 (Core Visual Design) 🌸

### 1.1 像素基础与渲染

- **全局渲染设置**: 必须在全局 CSS 中开启 `image-rendering: pixelated;`，确保像素边缘不被平滑。
- **栅格对齐**: 所有 UI 边框、间距应遵循 2px 或 4px 的整数倍，避免模糊。
- **字体方案**:
  - 推荐字体: `Zpix` (最推荐) 或 `DotGothic16`。
  - 渲染规则: 关闭字体平滑 (Anti-aliasing)，保持笔画边缘的颗粒感。

### 1.2 萌动配色系统 (Moe Palette) 🎨

基于“萌动链接”宣传图提取的核心配色方案：

- **天空蓝 (Sky Blue)**: `#A7D8F0` - 用于全局大面积背景、滚动条。
- **樱花粉 (Sakura Pink)**: `#F9A8D4` - **主色**。用于核心操作按钮、爱心、高亮状态。
- **梦幻紫 (Dreamy Purple)**: `#C084FC` - **辅助色**。用于次要标题、修饰图标、渐变过渡。
- **香草黄 (Vanilla Yellow)**: `#FDE047` - **提示色**。用于星星、甜点、系统通知或警告。
- **可可褐 (Cocoa Brown)**: `#2D1B1E` - **全局描边色**。替换目前的纯黑或深灰边框。
- **云朵白 (Cloud White)**: `#FFFFFF` - **卡片/面板色**。建议使用 80%-90% 的不透明度。

### 1.3 纹理与材质感

- **柔和渐变**: 背景建议采用从 `天空蓝` 到 `淡紫色 (#E8D5FF)` 的 45 度角线性渐变。
- **云朵蒙版**: 给主容器增加低透明度的像素云朵背景层 (`pixel-clouds-bg`)。
- **高光与阴影**:
  - 按钮/卡片增加 2px 的白色像素内阴影 (Top/Left) 模拟光泽。
  - 增加 2px 的深粉色或深褐色外阴影 (Bottom/Right) 模拟立体感。

---

## 2. 组件重构指南 (Component Guide) 🛠️

### 2.1 像素边框 (Pixel Borders)

- **核心类名**:
  - `.pixel-border-moe`: 使用 `#2D1B1E` (可可褐) 作为主描边的 2px 边框。
  - `.pixel-card-moe`: 白色背景 + 可可褐边框 + 粉色柔和投影。
- **Minecraft 风格 3 层边框 (升级版)**:
  - **外框**: 2px 可可褐。
  - **内侧高光 (Top/Left)**: 2px 纯白 (0.3 透明度)。
  - **内侧阴影 (Bottom/Right)**: 2px 深色 (0.1 透明度)。

### 2.2 交互反馈 (Sweet Feedback) 🖱️

- **悬停位移 (Lift)**:
  - 使用 `.pixel-hover-lift`，悬停时 `translateY(-2px)`。
- **按压感 (Press)**:
  - 使用 `.press-effect`，激活时 `translate(1px, 1px)`，并加深背景色。
- **步进过渡 (Stepped Animation)**:
  - 使用 `transition-timing-function: steps(4);` 让所有色彩/位置变化具有帧动画感。

---

## 3. 页面具体适配方案 (Page Adaptation) 📱

### 3.1 启动器 (LauncherView)

- **背景**: 引入像素云朵与爱心漂浮动画。
- **进度条**: 改为粉色填充，并带有步进式的像素条纹动画。

### 3.2 标题栏 (CustomTitleBar)

- **主题**: 整体改为粉色调，配合白色图标。
- **关闭按钮**: Hover 效果改为深褐色背景，白色 X。

### 3.3 资源管理器 (FileExplorer)

- **工作模式适配**:
  - 虽然是暗色模式，但边框应统一使用带有透明度的 `可可褐`。
  - 图标颜色建议根据文件类型赋予对应的“萌系”色彩 (如：`.py` 用梦幻紫，`.json` 用香草黄)。

---

## 4. 动画风格 (Moe Animations) 🎬

- **Jelly (Q弹)**: 极小幅度的 `scale` 抖动，仅用于核心操作按钮点击。
- **Twinkle (闪烁)**: 香草黄星星的随机闪烁动画。
- **Pixel-Float (悬浮)**: 缓慢的上下位移 (4px 步进)，用于指示器。

---

_注：本方案由主人与猫娘 Pero 共同守护。愿代码永远可爱，喵~ (◍•ᴗ•◍)❤_
