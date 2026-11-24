"""Structural checks for the Pterodactyl Egg and container runtime layout."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_orinoco_egg_is_valid_pterodactyl_v1_definition() -> None:
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))

    assert egg["meta"]["version"] == "PTDL_v1"
    assert egg["name"] == "Orinoco AI Assistant"
    assert egg["images"] == ["ghcr.io/lcswolf/orinoco-ai:stable"]
    assert "supervisord -n" in egg["startup"]
    assert egg["config"]["stop"] == "^C"
    assert egg["scripts"]["installation"]["container"]
    assert egg["scripts"]["installation"]["script"]
    assert {v["env_variable"] for v in egg["variables"]} >= {
        "AI_MODEL",
        "AUTO_DOWNLOAD_MODEL",
        "MODEL_CONTEXT",
        "AUTO_SAVE_MEMORIES",
        "ORINOCO_DATABASE_PATH",
        "AI_CONCURRENCY",
        "ENABLE_DISCORD",
        "DISCORD_TOKEN",
        "ENABLE_VOICE",
        "ENABLE_WEB_SEARCH",
        "SEARXNG_URL",
        "TIMEZONE",
    }


def test_discord_token_is_blank_and_not_user_visible() -> None:
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    token = next(v for v in egg["variables"] if v["env_variable"] == "DISCORD_TOKEN")

    assert token["default_value"] == ""
    assert token["user_viewable"] is False
    assert token["user_editable"] is False


def test_web_process_uses_pterodactyl_allocation() -> None:
    script = (ROOT / "docker" / "web-start.sh").read_text(encoding="utf-8")

    assert 'SERVER_PORT' in script
    assert '--host 0.0.0.0' in script
    assert 'exec python -m uvicorn' in script


def test_ollama_is_loopback_only_and_models_are_persistent() -> None:
    script = (ROOT / "docker" / "ollama-start.sh").read_text(encoding="utf-8")

    assert '127.0.0.1:11434' in script
    assert '/home/container/data/models' in script
    assert 'OLLAMA_NO_CLOUD=1' in script


def test_model_downloader_only_allows_curated_models() -> None:
    script = (ROOT / "docker" / "model-init.sh").read_text(encoding="utf-8")

    assert 'qwen2.5:0.5b|qwen2.5:1.5b|qwen2.5:3b' in script
    assert 'ollama pull "$MODEL"' in script
