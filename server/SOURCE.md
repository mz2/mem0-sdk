# Provenance of `mem0_server.py`

`mem0_server.py` is **vendored from upstream mem0**, file `server/main.py` at tag
[`v0.1.114`](https://github.com/mem0ai/mem0/blob/v0.1.114/server/main.py)
(Apache-2.0).

All FastAPI route handlers (`/memories`, `/search`, `/configure`, `/reset`,
`/memories/{id}` and `/memories/{id}/history`) are upstream **verbatim**.

The only Workshop-SDK delta is the **configuration block** (everything above the
`MEMORY_INSTANCE = Memory.from_config(...)` line) plus a small `/health` route
and a `__main__` runner:

- Upstream hardcodes `DEFAULT_CONFIG` to `pgvector` (Postgres) + `neo4j`, so the
  server cannot start without those external services.
- This SDK instead defaults to a **fully embedded** backend — on-disk Qdrant and
  SQLite under `$MEM0_DIR` (default `~/.mem0`) — the same store the in-process
  `mem0` library uses.
- Set `MEM0_CONFIG_PATH` to a JSON file to override the backend entirely (e.g.
  point the LLM/embedder at a local Ollama). The shipped default lives at
  `~/.mem0/mem0_config.json`.

To update: re-fetch `server/main.py` from a newer mem0 tag and re-apply the
configuration block above the `MEMORY_INSTANCE` assignment.
