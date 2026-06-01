#!/usr/bin/env python3
"""Render ~/.mem0/mem0_config.json from environment variables.

Declarative config: setup-project runs this on every launch/refresh, so the
config is a deterministic function of ~/.mem0/.env (the single source of truth).
Set MEM0_CONFIG_RENDER=0 to keep a hand-edited mem0_config.json instead.

Variable knobs come from the environment; the storage layout (qdrant path,
history DB, on-disk vector store) is fixed by the SDK. Writes to argv[1] if
given, else ~/.mem0/mem0_config.json.

Only the Python standard library is used.
"""
import json
import os
import sys


def env(name, default=""):
    return os.environ.get(name, default).strip()


def as_num(value, cast):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def role_block(provider, model, base_url, temperature=None, dims=None):
    """Build an llm/embedder block, omitting keys that are unset."""
    config = {}
    if model:
        config["model"] = model
    if temperature is not None:
        config["temperature"] = temperature
    if dims is not None:
        config["embedding_model_dims"] = dims
    if base_url:
        # mem0 keys the endpoint by provider family.
        key = "ollama_base_url" if provider == "ollama" else "openai_base_url"
        config[key] = base_url
    return {"provider": provider, "config": config}


mem0_dir = os.path.join(os.path.expanduser("~"), ".mem0")

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "path": os.path.join(mem0_dir, "qdrant"),
            "on_disk": True,
        },
    },
    "llm": role_block(
        env("MEM0_LLM_PROVIDER", "ollama"),
        env("MEM0_LLM_MODEL"),
        env("MEM0_LLM_BASE_URL", "http://127.0.0.1:11434"),
        temperature=as_num(env("MEM0_LLM_TEMPERATURE", "0.2"), float),
    ),
    "embedder": role_block(
        env("MEM0_EMBEDDER_PROVIDER", "ollama"),
        env("MEM0_EMBEDDER_MODEL"),
        env("MEM0_EMBEDDER_BASE_URL", "http://127.0.0.1:11434"),
        dims=as_num(env("MEM0_EMBEDDER_DIMS"), int),
    ),
    "history_db_path": os.path.join(mem0_dir, "history.db"),
}

out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(mem0_dir, "mem0_config.json")
with open(out_path, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
