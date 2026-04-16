# shore-memory

Standalone memory platform for AnanBot.

`shore-memory` is one project with multiple runtime components:

- `server/`: Rust hot-path service for recall, writeback, task orchestration, and WebSocket events
- `worker/`: Python worker for embedding, scoring, and reflection tasks
- `vendor/TriviumDB/`: vendored Rust `TriviumDB` source used by the server hot path

This layout keeps the memory system self-contained:

- no dependency on a sibling project outside `shore-memory`
- no split into multiple top-level repos just to run one memory service
- Rust stays on the synchronous recall path, while Python stays on async worker duties

## Quick Start

1. Copy `server/.env.example` to `server/.env`
2. Copy `worker/.env.example` to `worker/.env`
3. Start the worker from `worker/`

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 7812
```

4. Start the server from `server/`

```powershell
cargo run
```

5. Point the AstrBot bridge plugin to `http://127.0.0.1:7811`

## Notes

- `vendor/TriviumDB` is a vendored snapshot copied from the latest `E:\cursor_project\ananbot\TriviumDB`
- if you later update the standalone `TriviumDB` clone, sync the vendored copy intentionally instead of pointing the server back to an external sibling path
- this repository intentionally preserves `PeroCore` git lineage in history so upstream contributors remain visible, while the current working tree stays focused on `shore-memory`
