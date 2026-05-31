#!/usr/bin/env python3
"""Validate that the mem0 runtime config is actually usable.

Prints a one-line problem description to stdout (empty output = OK) and always
exits 0. Used by hooks/check-health to fail SDK health *explicitly* when mem0
is misconfigured (no model, missing cloud key, missing embedder dims) instead
of reporting healthy and then failing at first memory operation.

Only the Python standard library is used.
"""
import json
import os
import sys

home = os.path.expanduser("~")
cfg_path = os.path.join(home, ".mem0", "mem0_config.json")
env_path = os.path.join(home, ".mem0", ".env")

try:
    cfg = json.load(open(cfg_path))
except Exception as e:  # noqa: BLE001 — any failure here is a config problem
    print(f"mem0_config.json missing or invalid ({e})")
    sys.exit(0)

# Parse ~/.mem0/.env (KEY=VALUE lines) without sourcing it.
env = {}
try:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
except FileNotFoundError:
    pass


def is_set(name):
    return bool(env.get(name) or os.environ.get(name))


# Cloud providers that require an API key to function.
CLOUD_KEY = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
}

problems = []
for role in ("llm", "embedder"):
    blk = cfg.get(role) or {}
    prov = blk.get("provider")
    conf = blk.get("config") or {}
    model = conf.get("model")
    if not prov:
        problems.append(f"{role}.provider is not set")
        continue
    if not model:
        problems.append(f"{role}.config.model is not set")
    if prov in CLOUD_KEY and not is_set(CLOUD_KEY[prov]):
        problems.append(f"{role} provider '{prov}' needs {CLOUD_KEY[prov]} in ~/.mem0/.env")

emb = cfg.get("embedder") or {}
if emb.get("provider") == "ollama" and not (emb.get("config") or {}).get("embedding_model_dims"):
    problems.append("embedder.config.embedding_model_dims is not set (required for the ollama embedder)")

if problems:
    print("; ".join(problems))
