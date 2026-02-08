# PeroCore Linux Server (Docker) 技术方案

本文档描述了将 PeroCore 从 Electron 桌面应用改造为基于 Docker 的 Linux 服务端应用的架构设计与实施路线。

## 1. 架构概览

目标是将 PeroCore 拆分为三个松耦合的容器服务，通过 Docker Compose 进行编排。

### 1.1 服务拓扑

```mermaid
graph TD
    User[用户 (浏览器)] -->|HTTP :8080| Web[pero-web (Nginx)]
    Web -->|静态资源| WebFS[Frontend Static Files]
    Web -->|反向代理 /api| Backend[pero-backend (Python)]
    Backend -->|WebSocket/HTTP| NapCat[pero-napcat (Node.js)]
    Backend -->|读写| VolumeConfig[Config Volume]
    Backend -->|读写| VolumeData[Memory/Data Volume]
    NapCat -->|QQ 协议| TXServer[腾讯服务器]
```

### 1.2 核心组件

| 服务名 | 基础镜像 | 职责 | 端口映射 |
| :--- | :--- | :--- | :--- |
| **pero-backend** | `python:3.10-slim` | 核心业务逻辑、LLM 调度、记忆管理 | 9120 (仅内部) |
| **pero-web** | `nginx:alpine` | 托管 Dashboard 前端、反向代理 API | 8080:80 |
| **pero-napcat** | `node:20-alpine` | 运行 NapCat QQ 协议端 | 3000 (仅内部) |
| **pero-gateway** | `alpine` | 消息总线、Token 生成 | 14747 (仅内部) |

---

## 2. 详细实施方案

### 2.1 Backend 改造 (Python)

由于 Linux 服务器无图形界面，后端必须能够识别运行环境并优雅降级。

#### A. 环境变量控制
引入 `PERO_ENV` 环境变量：
- `desktop` (默认): 启用所有 GUI 功能（PyAutoGUI, PyGetWindow, OpenCV imshow）。
- `server`: 禁用 GUI 功能，使用 Mock 接口替代。

#### B. 依赖解耦 (requirements.txt)
将仅限 Windows 的库标记为可选，或在代码中动态导入：
```python
# 示例：动态导入 GUI 库
try:
    import pygetwindow as gw
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

def get_active_window():
    if not HAS_GUI:
        return {"title": "Server Mode", "app": "Console"}
    # ... 原有逻辑
```

#### C. 路径适配
确保所有文件路径操作使用 `os.path.join` 或 `pathlib`，避免硬编码 Windows 风格的反斜杠 `\`。

#### D. 路径与编码兼容性 (Path & Encoding)
- **分隔符**: 严禁使用字符串拼接路径 (如 `data + "\\" + file`)，必须使用 `os.path.join(data, file)` 或 `pathlib.Path`。
- **大小写敏感**: Linux 文件系统 (ext4) 是大小写敏感的。必须确保代码中引用的文件名（如 `import Config` vs `import config`，或 `open("Data.json")`）与实际文件名完全一致。
- **编码**: 所有文本文件读写操作 **必须显式指定 encoding**。
  ```python
  # 错误
  with open("file.txt", "r") as f: ...
  # 正确
  with open("file.txt", "r", encoding="utf-8") as f: ...
  ```
- **绝对路径**: 避免假设路径以 `C:` 开头。容器内路径通常以 `/app` 开头。

### 2.2 Frontend 改造 (Vue)

前端需要从 Electron 渲染进程转变为标准的 Web 单页应用 (SPA)。

#### A. API 请求适配
Dashboard 目前可能混合使用了 `ipcRenderer` 和 `fetch`。
- **IPC 移除/Mock**: 在浏览器环境中，`window.electron` 不存在。需要完善 `ipcAdapter.ts`，当检测到非 Electron 环境时，将部分 IPC 请求（如“获取配置”）转换为 HTTP 请求。
- **Base URL**: `fetch` 请求的 Base URL 应改为相对路径 `/api`，由 Nginx 转发，避免跨域问题。

#### B. 路由模式
- 保持 `HashRouter` (Vue Router 默认) 或配置 Nginx 支持 `HistoryRouter`。

#### C. 构建脚本
增加专门的 Docker 构建命令：
```json
"scripts": {
  "build:docker": "vue-tsc && vite build --mode docker"
}
```

### 2.3 NapCat 集成

NapCat 作为一个独立服务运行，不再由 Python 后端作为子进程启动。

- **通信**: Backend 通过 Docker 内部 DNS (`http://pero-napcat:3000`) 访问 NapCat。
- **配置**: NapCat 的配置文件 (`napcat.json`) 需要映射到宿主机，以便持久化登录态。

---

## 3. Docker 配置清单

### 3.1 Dockerfile.backend

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖 (OpenCV 需要一些 GL 库，即使在 Headless 模式下)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖定义
COPY backend/requirements.txt .
# 安装 Python 依赖 (排除 win32 库)
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY backend/ .
COPY config/ ./config_template/

# 环境变量
ENV PERO_ENV=server
ENV PORT=9120

# 启动命令
CMD ["python", "main.py"]
```

### 3.2 Dockerfile.web

```dockerfile
# 构建阶段
FROM node:18 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# 运行阶段
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 3.5 Dockerfile.rust (Build Stage)

您的项目使用了 Python 调用 Rust 扩展 (`backend/nit_core/interpreter/rust_binding` 和 `backend/rust_core`)。
这些扩展必须在 Linux 环境下重新编译。我们建议使用多阶段构建，在 Docker 镜像构建过程中完成编译。

修改 `Dockerfile.backend`：

```dockerfile
# --- Stage 1: Builder (Rust + Python) ---
FROM python:3.10-slim AS builder

# 安装构建工具
RUN apt-get update && apt-get install -y \
    curl build-essential libssl-dev pkg-config

# 安装 Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /build

# 复制 Rust 源码
COPY backend/nit_core/interpreter/rust_binding ./nit_core/interpreter/rust_binding
COPY backend/rust_core ./rust_core

# 编译 Rust 扩展 (这里假设使用 maturin 或 setuptools-rust)
# 如果是 maturin:
RUN pip install maturin
RUN cd nit_core/interpreter/rust_binding && maturin build --release --out ../../../dist
RUN cd rust_core && maturin build --release --out ../dist

# --- Stage 2: Runtime ---
FROM python:3.10-slim

WORKDIR /app
# ... (安装基础依赖) ...

# 复制并安装编译好的 Wheel 包
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install /tmp/*.whl

# ... (后续步骤同上) ...
```

### 3.6 Dockerfile.gateway


由于 Gateway 是用 Go 编写的，我们可以轻松编译 Linux 版本。

```dockerfile
# 构建阶段
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY gateway/ .
COPY proto/ ../proto/
# 调整 go.mod 中的本地替换路径 (如果有) 或直接构建
RUN go build -o gateway main.go

# 运行阶段
FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/gateway .
# 确保 Gateway 能写入 Token
CMD ["./gateway"]
```

### 3.4 docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - PERO_ENV=server
    networks:
      - pero-net

  napcat:
    image: mlikiowa/napcat-docker:latest
    volumes:
      - ./napcat/config:/app/config
    networks:
      - pero-net

  gateway:
    build:
      context: .
      dockerfile: docker/Dockerfile.gateway
    volumes:
      - ./data:/app/data
    networks:
      - pero-net

  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.web
    ports:
      - "8080:80"
    depends_on:
      - backend
    networks:
      - pero-net

networks:
  pero-net:
    driver: bridge
```

---

## 4. 开发路线图

1.  **Phase 1: 后端解耦 (当前阶段)**
    - 识别并隔离 `pywin32`, `pyautogui` 等 Windows 专用库。
    - 实现 `MockDesktopService` 以支持 Server 模式。
    - 验证后端在无 GUI 环境下能否启动。

2.  **Phase 2: 前端适配**
    - 增强 `ipcAdapter`，支持纯 Web 环境。
    - 调整 API 请求路径，适配 Nginx 反代。

3.  **Phase 3: Docker 环境构建**
    - 编写 Dockerfiles 和 docker-compose.yml。
    - 本地模拟 Docker 部署测试。

4.  **Phase 4: NapCat 联调**
    - 验证 Backend 与 Docker 版 NapCat 的通信。
    - 解决扫码登录的 UI 交互问题（在 Dashboard 显示二维码）。

## 5. 特别注意事项 (Crucial Considerations)

### 5.1 Gateway 编译与通信
您的项目中包含一个 Go 语言编写的 Gateway (`gateway/main.go`)。
- **编译**: 必须在 Docker 中重新编译为 Linux 二进制文件（见上文 `Dockerfile.gateway`）。
- **Token 共享**: Gateway 启动时会生成 `gateway_token.json`。Backend 和 Frontend 都需要这个 Token。
  - **解决方案**: 在 `docker-compose.yml` 中，将 `./data` 目录同时挂载给 `gateway` 和 `backend` 服务，实现文件共享。

### 5.2 时区 (Timezone)
Docker 容器默认使用 UTC 时间。这会导致定时任务（Scheduler）和日志时间偏差 8 小时。
- **解决方案**: 在所有服务的 `docker-compose` 配置中添加：
  ```yaml
  environment:
    - TZ=Asia/Shanghai
  ```

### 5.3 硬件加速 (GPU)
您的项目使用了 `faster_whisper` (ASR) 和可能的本地 LLM。
- **CPU 模式**: 默认情况下，Docker 仅使用 CPU。语音识别可能会有延迟。
- **GPU 模式**: 如果宿主机有 NVIDIA 显卡，建议安装 `nvidia-container-toolkit` 并配置 Docker 使用 GPU。
  ```yaml
  # backend service
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  ```

### 5.4 音频流 (Audio Streaming)
- **输入**: Linux Server 没有麦克风。必须确保 Web 前端通过 WebSocket (`/ws/voice`) 将浏览器捕获的麦克风数据流式传输给后端。
- **输出**: 后端不能直接播放音频 (`playsound` 等库在 Docker 中无效)。必须将 TTS 生成的音频数据通过 Gateway 广播回前端播放。**检查代码中是否有直接调用系统播放器的行为，必须全部移除或 Mock。**

