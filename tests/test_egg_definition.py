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
        "ORINOCO_BACKUP_KEY",
        "ORINOCO_BACKUP_S3_ENDPOINT",
        "ORINOCO_BACKUP_S3_BUCKET",
        "ORINOCO_BACKUP_S3_ACCESS_KEY_ID",
        "ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY",
        "ORINOCO_BACKUP_TIME",
        "ORINOCO_BACKUP_RETENTION_DAYS",
        "ORINOCO_USER_DOCUMENT_QUOTA_BYTES",
        "ORINOCO_USER_DOCUMENT_QUOTA_FILES",
        "ORINOCO_SHARED_DOCUMENT_QUOTA_BYTES",
        "ORINOCO_SHARED_DOCUMENT_QUOTA_FILES",
        "ORINOCO_MAX_REQUEST_BODY_BYTES",
        "ORINOCO_CHAT_REQUESTS_PER_MINUTE",
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


def test_dockerignore_keeps_application_feature_packages() -> None:
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "documents" not in ignored
    assert "memories" not in ignored
    assert "conversations" not in ignored
    assert "/data" in ignored



def test_backup_key_is_private_and_blank_by_default() -> None:
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    key = next(v for v in egg["variables"] if v["env_variable"] == "ORINOCO_BACKUP_KEY")

    assert key["default_value"] == ""
    assert key["user_viewable"] is False
    assert key["user_editable"] is False


def test_inactive_discord_and_voice_features_cannot_be_enabled_from_server_settings() -> None:
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    variables = {item["env_variable"]: item for item in egg["variables"]}

    assert variables["ENABLE_DISCORD"]["default_value"] == "false"
    assert variables["ENABLE_DISCORD"]["user_editable"] is False
    assert variables["ENABLE_VOICE"]["default_value"] == "false"
    assert variables["ENABLE_VOICE"]["user_editable"] is False


def test_container_installs_timezone_database_for_london_timezone() -> None:
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert "tzdata" in dockerfile
    assert "TZ=Europe/London" in dockerfile


def test_s3_backup_credentials_are_hidden_and_not_user_editable() -> None:
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    variables = {item["env_variable"]: item for item in egg["variables"]}

    for name in ("ORINOCO_BACKUP_S3_ACCESS_KEY_ID", "ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY"):
        assert variables[name]["default_value"] == ""
        assert variables[name]["user_viewable"] is False
        assert variables[name]["user_editable"] is False


def test_daily_backup_schedule_defaults_and_visibility() -> None:
    """The Egg must expose safe defaults for local schedule and retention."""
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    variables = {item["env_variable"]: item for item in egg["variables"]}

    assert variables["ORINOCO_BACKUP_TIME"]["default_value"] == "03:00"
    assert variables["ORINOCO_BACKUP_TIME"]["user_editable"] is True
    assert variables["ORINOCO_BACKUP_RETENTION_DAYS"]["default_value"] == "14"
    assert variables["ORINOCO_BACKUP_RETENTION_DAYS"]["rules"] == "required|integer|min:1|max:365"



def test_resource_limit_egg_defaults_are_conservative_and_admin_only() -> None:
    """Resource limits are exposed to the administrator but not ordinary server users."""
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    variables = {item["env_variable"]: item for item in egg["variables"]}

    expected = {
        "ORINOCO_USER_DOCUMENT_QUOTA_BYTES": "52428800",
        "ORINOCO_USER_DOCUMENT_QUOTA_FILES": "20",
        "ORINOCO_SHARED_DOCUMENT_QUOTA_BYTES": "209715200",
        "ORINOCO_SHARED_DOCUMENT_QUOTA_FILES": "50",
        "ORINOCO_MAX_REQUEST_BODY_BYTES": "12582912",
        "ORINOCO_CHAT_REQUESTS_PER_MINUTE": "10",
    }
    for name, default in expected.items():
        assert variables[name]["default_value"] == default
        assert variables[name]["user_editable"] is False
