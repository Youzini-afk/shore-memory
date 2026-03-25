# PeroCore MOD 目录

此目录存放所有 MOD（用户扩展）和系统基础设施。

## 目录约定

```
mods/
├── _external_plugins/          # 系统基础设施（_ 前缀，不作为用户 MOD 加载）
│   ├── service.py              # 外部插件注册表
│   └── router.py               # /api/plugins/* API 路由
│
└── my_mod/                     # 用户 MOD（自动加载）
    ├── mod.toml                # 可选：声明式元数据
    ├── main.py                 # 必须：入口文件（包含 init() 函数）
    ├── hooks.py                # 可选：EventBus Hook 处理函数
    ├── processors.py           # 可选：管道处理器
    └── external/               # 可选：外部插件独立服务（不被主进程加载）
        └── server.py
```

## 三层扩展体系

1. **EventBus Hook** — 监听事件，修改上下文
2. **管道注册** — 在预处理/后处理管道中插入节点
3. **外部插件** — 独立 HTTP 服务，通过 Webhook 通信

详见 `wiki/ecosystem/mod.md`。

## 示例

参见 `memory_tagger/` — 完整的三层扩展示例。
