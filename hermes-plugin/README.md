# `mem0-local` — Hermes memory provider for a self-hosted mem0

This is a **standalone Hermes memory-provider plugin** (the sanctioned
`~/.hermes/plugins/` extension path — see the hermes-agent `CONTRIBUTING.md`)
that points Hermes at a **self-hosted mem0 REST server** instead of the mem0
cloud Platform.

Hermes' *built-in* `mem0` provider uses `MemoryClient`, which only talks to
`https://api.mem0.ai` and needs a `MEM0_API_KEY`. This `mem0-local` provider
instead speaks the self-hosted server's own endpoints (`/memories`, `/search`)
over plain HTTP — no API key, no cloud — so it pairs with the **mem0 SDK's REST
server** running in another workshop.

---

## Wiring two workshops together

The mem0 SDK exposes its REST server on the `mem0-api` tunnel slot (port 8000).
The Hermes workshop consumes it through a tunnel plug so that
`http://localhost:8000` inside the Hermes workshop reaches the mem0 server.

1. **Enable the mem0 REST server** in the mem0 workshop — set `MEM0_SERVE=1` in
   `~/.mem0/.env` and add `OPENAI_API_KEY` (or configure Ollama in
   `~/.mem0/mem0_config.json`), then `systemctl --user restart mem0-server`.

2. **Install this plugin** into the Hermes workshop:

   ```bash
   # from the Hermes workshop shell
   mkdir -p ~/.hermes/plugins
   cp -r /path/to/mem0_local ~/.hermes/plugins/mem0_local
   ```

   (Or mount it: point the Hermes `hermes-home` mount at a host directory that
   contains `plugins/mem0_local/`.)

3. **Select the provider** in `~/.hermes/config.yaml`:

   ```yaml
   memory:
     memory_enabled: true
     provider: mem0-local
   ```

4. **Point it at the server.** Default is `http://localhost:8000`. If the mem0
   server is reached over a tunnel on a different host/port, set it in
   `~/.hermes/mem0_local.json`:

   ```json
   { "base_url": "http://localhost:8000", "user_id": "hermes-user" }
   ```

5. **Restart the gateway:** `systemctl --user restart hermes-gateway`.

---

## Example combined workshop

```yaml
# workshop.yaml — Hermes + mem0 in one workshop, wired over a tunnel
name: hermes-mem0
base: ubuntu@24.04

sdks:
  - name: mem0
    channel: latest/stable
  - name: hermes-agent
    channel: latest/stable

connections:
  # Hermes' tunnel plug -> mem0's REST server slot.
  - plug: hermes-agent:llm-backend      # (LLM, wired separately to Ollama/host)
    slot: system:llm-backend
  - plug: hermes-agent:mem0-api          # add a matching tunnel plug on hermes
    slot: mem0:mem0-api
```

> Note: the stock hermes-agent SDK does not yet declare a `mem0-api` tunnel
> plug. Until it does, run both SDKs in the same workshop and reach the server
> at `http://localhost:8000` directly, or add the plug to the hermes-agent SDK.

---

## Config reference

| Key | Env var | Default | Purpose |
|---|---|---|---|
| `base_url` | `MEM0_BASE_URL` | `http://localhost:8000` | mem0 server URL |
| `user_id` | `MEM0_USER_ID` | `hermes-user` | memory scoping (read/write) |
| `agent_id` | `MEM0_AGENT_ID` | `hermes` | attribution on writes |

## Limitations

- The self-hosted v0.1.114 server has no server-side reranking or `top_k`, so
  those built-in-provider options are not exposed here.
- `mem0_conclude` is stored through mem0's normal LLM fact-extraction (the
  lightweight server does not expose `infer=false`).
