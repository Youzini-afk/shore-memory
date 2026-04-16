# Shore Memory Worker

Python async worker for the standalone `shore-memory` project.

This component is responsible for:

- embeddings
- turn scoring
- reflection summaries

## Run

1. Copy `.env.example` to `.env`
2. Fill embedding and optional LLM settings
3. Start:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 7812
```

If no LLM settings are configured, the worker falls back to heuristic scoring and reflection.
