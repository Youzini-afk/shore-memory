# Shore Memory Server

Rust hot-path server for the standalone `shore-memory` project.

## What is included

- Rust HTTP + WebSocket service
- SQLite metadata and task store with WAL
- Native `TriviumDB` Rust integration from `../vendor/TriviumDB`
- Background task queue for scoring, indexing, reflection, and rebuild
- Python worker integration for embedding, scorer, and reflection tasks

## Layout

- `src/main.rs` starts the service
- `src/app.rs` contains HTTP handlers and task processing
- `src/db.rs` manages SQLite metadata and queue tables
- `src/trivium.rs` wraps the native TriviumDB Rust API
- `src/worker.rs` talks to the Python worker over HTTP

## Run

1. Copy `.env.example` to `.env` and adjust values if needed.
2. Start the Python worker from `../worker` first.
3. Run:

```powershell
cargo run
```

The server is intentionally kept inside the single `shore-memory` project and no longer depends on an external sibling repository path.
