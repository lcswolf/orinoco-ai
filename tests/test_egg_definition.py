"""Basic structural checks for the Pterodactyl 1.x Egg definition."""

import json
from pathlib import Path


def test_orinoco_egg_is_valid_pterodactyl_v1_definition() -> None:
    path = Path(__file__).parents[1] / "egg" / "egg-orinoco.json"
    egg = json.loads(path.read_text(encoding="utf-8"))

    assert egg["meta"]["version"] == "PTDL_v1"
    assert egg["name"] == "Orinoco AI Assistant"
    assert egg["images"] == ["ghcr.io/lcswolf/orinoco-ai:stable"]
    assert "{{SERVER_PORT}}" in egg["startup"]
    assert egg["config"]["stop"] == "^C"
    assert egg["scripts"]["installation"]["container"]
    assert egg["scripts"]["installation"]["script"]
    assert {v["env_variable"] for v in egg["variables"]} >= {
        "AI_MODEL",
        "AUTO_DOWNLOAD_MODEL",
        "MODEL_CONTEXT",
        "AI_CONCURRENCY",
        "ENABLE_DISCORD",
        "DISCORD_TOKEN",
        "ENABLE_VOICE",
        "ENABLE_WEB_SEARCH",
        "SEARXNG_URL",
        "TIMEZONE",
    }


def test_discord_token_is_blank_and_not_user_visible() -> None:
    path = Path(__file__).parents[1] / "egg" / "egg-orinoco.json"
    egg = json.loads(path.read_text(encoding="utf-8"))
    token = next(v for v in egg["variables"] if v["env_variable"] == "DISCORD_TOKEN")

    assert token["default_value"] == ""
    assert token["user_viewable"] is False
    assert token["user_editable"] is False
