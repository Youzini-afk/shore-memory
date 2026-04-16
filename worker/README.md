# shore-memory-worker

`shore-memory` 的 Python 冷路径。职责：

- **embedding** — 对文本和批量文本取向量。
- **extract-entities** — 从自然语言抽取实体（有 LLM 配置时）。
- **score-turn** — 把一轮对话打分成若干 memory draft + state patch。
- **reflect** — 跑去重 / supersede / invalidate / archive 的反思输出。

没有 LLM 配置时会回落到**启发式实现**，保证 Rust server 依旧能跑一条完整的写入 → 召回链路。

## 路由

- `GET /health`
- `POST /v1/embed`
- `POST /v1/embed/batch`
- `POST /v1/tasks/extract-entities`
- `POST /v1/tasks/score-turn`
- `POST /v1/tasks/reflect`

调用方（Rust server）会为每种操作加独立超时（见 `server/src/worker.rs`）。

## 运行

```powershell
copy .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 7812
```

## 配置

- `embedding model / api key`：没配就走本地 hash 兜底（仅用于开发）。
- `LLM 配置`：没配就走启发式 scorer / reflection，服务端仍能形成 memory。
- 具体变量见 `.env.example`。

## 语法检查

```powershell
python -m py_compile worker/app/main.py
```
