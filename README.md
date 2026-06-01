# mem0 SDK for Workshop

[mem0](https://github.com/mem0ai/mem0), the memory layer for AI agents, inside a
workshop. Two interchangeable forms share **one local store**:

- **In-process library** — `import mem0` and use `Memory()` directly.
- **Self-hosted REST API server** — the upstream mem0 server, run fully embedded
  and exposed on a tunnel for other workshops (e.g. a Hermes agent) to consume.

Notes:

- Runs locally under `~/.mem0` — orchestration, the SQLite history database, and
  the embedded Qdrant vector store — persisted on the host across workshop
  updates (along with the virtual environment).
- Configuration is declarative: `~/.mem0/.env` is the single source of truth,
  and `mem0_config.json` is rendered from it on every launch/refresh. Defaults to
  a local Ollama LLM + embedder over the `llm-endpoint` tunnel. Set the model
  names (and the embedder's `embedding_model_dims`) in `~/.mem0/.env`. No model
  is defaulted, so until you set one `check-health` reports `waiting` and names
  the missing variable.
- For a cloud backend, set the provider(s) in `~/.mem0/.env` and add the key
  there too. The REST server is off unless `MEM0_SERVE=1`.

---

## Reference workshop

A minimal workshop:

```yaml
# workshop.yaml
name: mem0
base: ubuntu@24.04
sdks:
  - name: mem0
    channel: latest/stable

actions:
  shell: python
```

This makes `import mem0` available in the workshop's Python. To also run the
REST server, set `MEM0_SERVE=1` in `~/.mem0/.env` (see below) and connect the
`mem0-api` tunnel from the host or a peer workshop.

---

## Using the SDK

### Prerequisites, project layout

1. No prerequisite SDKs are required. For a fully local (offline) backend, pair
   with an Ollama SDK/host and edit `~/.mem0/mem0_config.json`.
2. No specific project layout is needed.
3. On launch the SDK installs `mem0ai` into a persisted virtual environment,
   seeds `~/.mem0/.env`, renders `~/.mem0/mem0_config.json` from it (embedded
   Qdrant on-disk + SQLite), and installs the REST server systemd unit (started
   only when `MEM0_SERVE=1`).

### Backend configuration

Configuration is declarative. `~/.mem0/.env` is the single source of truth, and
`mem0_config.json` is rendered from it on every launch/refresh. Edit `.env`,
then `workshop refresh`.

The default backend is a **local Ollama** (LLM + embedder) reached over the
`llm-endpoint` tunnel, with no API key. Set the model names:

- Connect the tunnel: `workshop connect <ws>/mem0:llm-endpoint <ws>/system:llm-endpoint`
- Edit `~/.mem0/.env`:
  - `MEM0_LLM_MODEL`, e.g. `qwen3.6:35b`
  - `MEM0_EMBEDDER_MODEL`, e.g. `nomic-embed-text`
  - `MEM0_EMBEDDER_DIMS`, the embedder's dimension, e.g. `768`
- `workshop refresh`

Until the models are set, `check-health` reports `waiting` and names the missing
variable. The SDK launches, but is flagged as not yet usable rather than running
on a missing/wrong model.

To hand-manage `mem0_config.json` instead of rendering it, set
`MEM0_CONFIG_RENDER=0` in `~/.mem0/.env`. The file is then seeded once and never
overwritten.

**Cloud backend instead:** set `MEM0_LLM_PROVIDER` / `MEM0_EMBEDDER_PROVIDER`
(e.g. `openai`) and add the key in `~/.mem0/.env`:

```bash
workshop shell
echo 'OPENAI_API_KEY=sk-...' >> ~/.mem0/.env
```

### In-process library

```bash
workshop shell
python - <<'PY'
import json, os
from mem0 import Memory
m = Memory.from_config(json.load(open(os.environ["MEM0_CONFIG_PATH"])))
m.add("I prefer dark roast coffee", user_id="alice")
print(m.search("coffee", user_id="alice"))
PY
```

Using `Memory.from_config(...)` with the SDK config persists to `~/.mem0`. A bare
`Memory()` uses mem0's own defaults (an ephemeral `/tmp` store) — fine for quick
experiments, but it does not persist.

### REST API server

```bash
workshop shell
sed -i 's/^MEM0_SERVE=0/MEM0_SERVE=1/' ~/.mem0/.env
systemctl --user restart mem0-server
curl -s http://localhost:8000/health
# OpenAPI docs at http://localhost:8000/docs
```

The server is the upstream mem0 REST API (vendored from v0.1.114 — see
`server/SOURCE.md`), running against the same embedded `~/.mem0` store. Reach it
from the host or a peer workshop over the `mem0-api` tunnel. This is the surface
a [Hermes](https://github.com/NousResearch/hermes-agent) agent consumes via the
`mem0-local` provider in `hermes-plugin/`.

### Verify from the command line

```bash
workshop info     # health line: "mem0 <version> — in-process library ready ..."
workshop shell
python -c "import mem0; print(mem0.__version__)"
```

---

## Plugs (resources this SDK consumes)

### `mem0-data`

- Interface: `mount`
- Workshop target: `/home/workshop/.mem0`
- Mode: `0o700`
- Purpose: persists the embedded store — `history.db` (SQLite), the on-disk
  Qdrant vector store, `mem0_config.json`, and `.env` — across workshop updates.

### `mem0-venv`

- Interface: `mount`
- Workshop target: `/home/workshop/.local/share/mem0`
- Purpose: persists the virtual environment so the `mem0ai` install happens once.

### `pip-cache`

- Interface: `mount`
- Workshop target: `/home/workshop/.cache/pip`
- Purpose: persists the pip download cache to speed up reinstalls.

### `gpu`

- Interface: `gpu`
- Purpose: GPU access for a local in-process embedding/LLM backend (e.g.
  Ollama). Ignored when mem0 is backed by a hosted API such as OpenAI.

## Slots (resources this SDK provides)

### `mem0-api`

- Interface: `tunnel`
- Endpoint: `8000`
- Purpose: exposes the mem0 REST API server (when `MEM0_SERVE=1`) to the host or
  a peer workshop.

---

## Documentation and guidance

- [mem0 official documentation](https://docs.mem0.ai/)
- [mem0 self-hosted server](https://github.com/mem0ai/mem0/tree/main/server)
- [Workshop documentation](https://ubuntu.com/workshop/docs/)

---

## Community and support

- mem0 community:
  [GitHub](https://github.com/mem0ai/mem0) ·
  [Discord](https://mem0.ai/discord)
- Workshop forum:
  [Discourse](https://discourse.ubuntu.com/)
- Please review our
  [Code of Conduct](https://ubuntu.com/community/ethos/code-of-conduct) before
  participating.

---

## Contributions

All contributions, including code, documentation updates, and issue reports,
are welcome!

- See `CONTRIBUTING.md` for guidelines.
- Open issues or pull requests on the official repository.

---

## License and copyright

Copyright 2026 Canonical Ltd.

This SDK is licensed under Apache-2.0.

mem0 is licensed under the
[Apache-2.0 License](https://github.com/mem0ai/mem0/blob/main/LICENSE). The
vendored server file retains its upstream license; see `server/SOURCE.md`.
