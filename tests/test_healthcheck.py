#!/usr/bin/env python3
"""Unit tests for the mem0 config validator (config/mem0_healthcheck.py).

Verifies the explicit-failure behaviour: the validator must flag a mem0 config
that is not actually usable (no model, a cloud provider with no API key, an
ollama embedder with no dimensions) and stay silent on a good one.

The validator under test is the co-located copy tests/mem0_healthcheck.py:
`sdkcraft test` (spread) only syncs the tests/ directory into the test system,
so config/ is not reachable there. test_copy_matches_shipped() enforces that
the copy is byte-identical to the shipped config/mem0_healthcheck.py wherever
the full repo is present (locally / on the build runner); it no-ops inside the
spread container, where config/ is absent.

Run directly:  python3 tests/test_healthcheck.py
Or via pytest: python3 -m pytest tests/
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HC = HERE / "mem0_healthcheck.py"                       # tested copy (synced)
SHIPPED = HERE.parent / "config" / "mem0_healthcheck.py"  # source of truth


def run(cfg, env_text=None):
    """Run the validator against a config (and optional .env), return stdout."""
    d = tempfile.mkdtemp()
    mem0 = pathlib.Path(d, ".mem0")
    mem0.mkdir()
    (mem0 / "mem0_config.json").write_text(json.dumps(cfg))
    if env_text is not None:
        (mem0 / ".env").write_text(env_text)
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)  # don't let a host key mask the check
    # Point the validator at the temp config dir explicitly (argv) rather than
    # via $HOME — a CI spread system has a real ~/.mem0 and expanduser/$HOME
    # overrides proved unreliable there.
    r = subprocess.run([sys.executable, str(HC), str(mem0)], env=env, capture_output=True, text=True)
    return r.stdout.strip()


OLLAMA_OK = {
    "llm": {"provider": "ollama", "config": {"model": "qwen3.6:35b"}},
    "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text", "embedding_model_dims": 768}},
}


def test_good_config_is_silent():
    assert run(OLLAMA_OK) == ""


def test_flags_missing_models_and_dims():
    cfg = {
        "llm": {"provider": "ollama", "config": {"model": ""}},
        "embedder": {"provider": "ollama", "config": {"model": ""}},
    }
    out = run(cfg)
    assert "llm.config.model is not set" in out
    assert "embedder.config.model is not set" in out
    assert "embedding_model_dims" in out


def test_flags_cloud_provider_without_key():
    cfg = {
        "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini"}},
        "embedder": {"provider": "ollama", "config": {"model": "x", "embedding_model_dims": 1}},
    }
    assert "OPENAI_API_KEY" in run(cfg, env_text="")


def test_cloud_provider_with_key_is_silent():
    cfg = {
        "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini"}},
        "embedder": {"provider": "ollama", "config": {"model": "x", "embedding_model_dims": 1}},
    }
    assert run(cfg, env_text="OPENAI_API_KEY=sk-test") == ""


def test_flags_invalid_config_file():
    d = tempfile.mkdtemp()
    mem0 = pathlib.Path(d, ".mem0")
    mem0.mkdir()
    r = subprocess.run([sys.executable, str(HC), str(mem0)], capture_output=True, text=True)
    assert "mem0_config.json" in r.stdout


def test_copy_matches_shipped():
    # Where the full repo is present (locally / build runner), the tested copy
    # must be byte-identical to the shipped validator. Inside the spread
    # container only tests/ is synced, so config/ is absent and we skip.
    if not SHIPPED.exists():
        return
    assert HC.read_text() == SHIPPED.read_text(), (
        "tests/mem0_healthcheck.py has drifted from config/mem0_healthcheck.py — "
        "re-copy it (cp config/mem0_healthcheck.py tests/mem0_healthcheck.py)"
    )


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
