"""Hermes memory provider: mem0-local.

A standalone Hermes memory-provider plugin (sanctioned ~/.hermes/plugins/ path —
see hermes-agent CONTRIBUTING.md) that points at a *self-hosted* mem0 REST
server instead of the mem0 cloud Platform. This is the bridge that lets a Hermes
workshop use the mem0 SDK's REST server (the `mem0-api` tunnel) as its memory
backend.

Unlike Hermes' built-in `mem0` provider — which uses `MemoryClient` and only
talks to https://api.mem0.ai — this provider speaks the self-hosted server's
own endpoints (`/memories`, `/search`) over plain HTTP, so it needs no API key
and no platform paths. It uses only the standard library.

Config via environment variables (or $HERMES_HOME/mem0_local.json):
  MEM0_BASE_URL   — base URL of the mem0 server (default: http://localhost:8000)
  MEM0_USER_ID    — user identifier (default: hermes-user)
  MEM0_AGENT_ID   — agent identifier (default: hermes)

Wiring: connect the Hermes workshop's tunnel plug to the mem0 workshop's
`mem0-api` slot so that http://localhost:8000 inside the Hermes workshop reaches
the mem0 server.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


def _load_config() -> dict:
    from hermes_constants import get_hermes_home

    config = {
        "base_url": os.environ.get("MEM0_BASE_URL", "http://localhost:8000"),
        "user_id": os.environ.get("MEM0_USER_ID", "hermes-user"),
        "agent_id": os.environ.get("MEM0_AGENT_ID", "hermes"),
    }
    config_path = get_hermes_home() / "mem0_local.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            config.update({k: v for k, v in file_cfg.items() if v not in (None, "")})
        except Exception:
            pass
    return config


class _RestClient:
    """Minimal HTTP client for the self-hosted mem0 server (stdlib only)."""

    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")

    def _request(self, method: str, path: str, *, body: dict | None = None) -> Any:
        url = f"{self._base}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

    def add(self, messages: List[dict], scope: Dict[str, str]) -> Any:
        return self._request("POST", "/memories", body={"messages": messages, **scope})

    def search(self, query: str, scope: Dict[str, str]) -> Any:
        return self._request("POST", "/search", body={"query": query, **scope})

    def get_all(self, scope: Dict[str, str]) -> Any:
        qs = urllib.parse.urlencode(scope)
        return self._request("GET", f"/memories?{qs}")


PROFILE_SCHEMA = {
    "name": "mem0_profile",
    "description": "Retrieve all stored memories about the user. Use at conversation start.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "mem0_search",
    "description": "Search memories by meaning. Returns relevant facts ranked by similarity.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "What to search for."}},
        "required": ["query"],
    },
}

CONCLUDE_SCHEMA = {
    "name": "mem0_conclude",
    "description": "Store a durable fact about the user (e.g. an explicit preference or decision).",
    "parameters": {
        "type": "object",
        "properties": {"conclusion": {"type": "string", "description": "The fact to store."}},
        "required": ["conclusion"],
    },
}


def _unwrap(response: Any) -> list:
    if isinstance(response, dict):
        return response.get("results", [])
    if isinstance(response, list):
        return response
    return []


class Mem0LocalMemoryProvider(MemoryProvider):
    """mem0 memory backed by a self-hosted mem0 REST server."""

    def __init__(self):
        self._config: dict = {}
        self._client: _RestClient | None = None
        self._user_id = "hermes-user"
        self._agent_id = "hermes"
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: threading.Thread | None = None
        self._sync_thread: threading.Thread | None = None

    @property
    def name(self) -> str:
        return "mem0-local"

    def is_available(self) -> bool:
        return True

    def get_config_schema(self):
        return [
            {"key": "base_url", "description": "Self-hosted mem0 server URL", "default": "http://localhost:8000", "env_var": "MEM0_BASE_URL"},
            {"key": "user_id", "description": "User identifier", "default": "hermes-user"},
            {"key": "agent_id", "description": "Agent identifier", "default": "hermes"},
        ]

    def save_config(self, values, hermes_home):
        from pathlib import Path
        path = Path(hermes_home) / "mem0_local.json"
        existing = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text())
            except Exception:
                pass
        existing.update(values)
        path.write_text(json.dumps(existing, indent=2))

    def initialize(self, session_id: str, **kwargs) -> None:
        self._config = _load_config()
        self._client = _RestClient(self._config["base_url"])
        self._user_id = kwargs.get("user_id") or self._config.get("user_id", "hermes-user")
        self._agent_id = self._config.get("agent_id", "hermes")

    def _read_scope(self) -> Dict[str, str]:
        return {"user_id": self._user_id}

    def _write_scope(self) -> Dict[str, str]:
        return {"user_id": self._user_id, "agent_id": self._agent_id}

    def system_prompt_block(self) -> str:
        return (
            "# Mem0 Memory (self-hosted)\n"
            f"Active. User: {self._user_id}.\n"
            "Use mem0_search to find memories, mem0_conclude to store facts, "
            "mem0_profile for a full overview."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        return f"## Mem0 Memory\n{result}" if result else ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        def _run():
            try:
                results = _unwrap(self._client.search(query, self._read_scope()))
                lines = [r.get("memory", "") for r in results if r.get("memory")]
                if lines:
                    with self._prefetch_lock:
                        self._prefetch_result = "\n".join(f"- {l}" for l in lines)
            except Exception as e:
                logger.debug("mem0-local prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(target=_run, daemon=True, name="mem0-local-prefetch")
        self._prefetch_thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        def _sync():
            try:
                messages = [
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": assistant_content},
                ]
                self._client.add(messages, self._write_scope())
            except Exception as e:
                logger.warning("mem0-local sync failed: %s", e)

        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)
        self._sync_thread = threading.Thread(target=_sync, daemon=True, name="mem0-local-sync")
        self._sync_thread.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, CONCLUDE_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if self._client is None:
            return tool_error("mem0-local not initialized")

        if tool_name == "mem0_profile":
            try:
                memories = _unwrap(self._client.get_all(self._read_scope()))
                lines = [m.get("memory", "") for m in memories if m.get("memory")]
                if not lines:
                    return json.dumps({"result": "No memories stored yet."})
                return json.dumps({"result": "\n".join(lines), "count": len(lines)})
            except Exception as e:
                return tool_error(f"Failed to fetch profile: {e}")

        if tool_name == "mem0_search":
            query = args.get("query", "")
            if not query:
                return tool_error("Missing required parameter: query")
            try:
                results = _unwrap(self._client.search(query, self._read_scope()))
                if not results:
                    return json.dumps({"result": "No relevant memories found."})
                items = [{"memory": r.get("memory", ""), "score": r.get("score", 0)} for r in results]
                return json.dumps({"results": items, "count": len(items)})
            except Exception as e:
                return tool_error(f"Search failed: {e}")

        if tool_name == "mem0_conclude":
            conclusion = args.get("conclusion", "")
            if not conclusion:
                return tool_error("Missing required parameter: conclusion")
            try:
                self._client.add([{"role": "user", "content": conclusion}], self._write_scope())
                return json.dumps({"result": "Fact stored."})
            except Exception as e:
                return tool_error(f"Failed to store: {e}")

        return tool_error(f"Unknown tool: {tool_name}")

    def shutdown(self) -> None:
        for t in (self._prefetch_thread, self._sync_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)
        self._client = None


def register(ctx) -> None:
    """Register mem0-local as a memory provider plugin."""
    ctx.register_memory_provider(Mem0LocalMemoryProvider())
