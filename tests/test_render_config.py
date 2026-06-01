#!/usr/bin/env python3
"""Unit tests for the mem0 config renderer (config/mem0_render_config.py).

Verifies that mem0_config.json is a deterministic function of the environment:
model / provider / base_url / dims flow through, unset knobs are omitted (so
the validator then flags them), and the fixed storage layout is always present.

The renderer under test is the co-located copy tests/mem0_render_config.py:
sdkcraft test (spread) only syncs the tests/ directory, so config/ is not
reachable there. The validator-sync CI check enforces that this copy stays
byte-identical to config/mem0_render_config.py.

Run directly:  python3 tests/test_render_config.py
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
RENDER = HERE / "mem0_render_config.py"


def render(env_extra):
    """Render with a clean MEM0_* environment plus env_extra; return the JSON."""
    out = pathlib.Path(tempfile.mkdtemp(), "mem0_config.json")
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEM0_")}
    env.update(env_extra)
    subprocess.run([sys.executable, str(RENDER), str(out)], env=env, check=True)
    return json.loads(out.read_text())


def test_models_and_dims_flow_through():
    c = render({
        "MEM0_LLM_MODEL": "qwen3.6:35b",
        "MEM0_EMBEDDER_MODEL": "nomic-embed-text",
        "MEM0_EMBEDDER_DIMS": "768",
    })
    assert c["llm"]["provider"] == "ollama"
    assert c["llm"]["config"]["model"] == "qwen3.6:35b"
    assert c["embedder"]["config"]["model"] == "nomic-embed-text"
    assert c["embedder"]["config"]["embedding_model_dims"] == 768


def test_unset_model_is_omitted():
    # Empty env -> no model keys, so mem0_healthcheck.py flags them.
    c = render({})
    assert "model" not in c["llm"]["config"]
    assert "model" not in c["embedder"]["config"]
    assert "embedding_model_dims" not in c["embedder"]["config"]


def test_base_url_keyed_by_provider():
    ollama = render({"MEM0_LLM_MODEL": "x"})
    assert "ollama_base_url" in ollama["llm"]["config"]
    openai = render({
        "MEM0_LLM_PROVIDER": "openai",
        "MEM0_LLM_MODEL": "gpt-4o-mini",
        "MEM0_LLM_BASE_URL": "https://api.openai.com/v1",
    })
    assert "openai_base_url" in openai["llm"]["config"]


def test_storage_layout_is_fixed():
    c = render({})
    assert c["vector_store"]["provider"] == "qdrant"
    assert c["vector_store"]["config"]["on_disk"] is True
    assert c["history_db_path"].endswith("/.mem0/history.db")


def test_temperature_default_and_override():
    assert render({})["llm"]["config"]["temperature"] == 0.2
    assert render({"MEM0_LLM_TEMPERATURE": "0.7"})["llm"]["config"]["temperature"] == 0.7


if __name__ == "__main__":
    import traceback

    failures = 0
    for name, fn in sorted((n, f) for n, f in globals().items() if n.startswith("test_")):
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    sys.exit(1 if failures else 0)
