"""Structural checks for the Pterodactyl Egg and container runtime layout."""

import json
import os
import subprocess
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
        "ORINOCO_TRUSTED_PROXY_IPS",
        "ORINOCO_CHAT_REQUESTS_PER_MINUTE",
        "ORINOCO_MAX_PENDING_GENERATIONS",
        "ORINOCO_MAX_MEMORIES_PER_USER",
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
    assert '--no-proxy-headers' in script
    # Uvicorn access logs include raw request URLs and query strings; keep them disabled.
    assert '--no-access-log' in script


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
    assert key["rules"] == "nullable|string|max:128"


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
        "ORINOCO_MAX_PENDING_GENERATIONS": "8",
        "ORINOCO_MAX_MEMORIES_PER_USER": "100",
    }
    for name, default in expected.items():
        assert variables[name]["default_value"] == default
        assert variables[name]["user_editable"] is False

    # The request-body middleware rejects limits below 1 KiB as misconfigured.
    assert variables["ORINOCO_MAX_REQUEST_BODY_BYTES"]["rules"] == "required|integer|min:1024"



def test_reverse_proxy_templates_keep_private_backends_and_edge_limits() -> None:
    """Guard the deployment examples against accidental public backend exposure."""
    caddy = (ROOT / "deploy" / "caddy" / "Caddyfile.example").read_text(encoding="utf-8")
    nginx = (ROOT / "deploy" / "nginx" / "orinoco.conf.example").read_text(encoding="utf-8")

    assert "default_sni {$ORINOCO_PUBLIC_IPV4}" in caddy
    assert "profile shortlived" in caddy
    assert "127.0.0.1:8081" in caddy
    assert "header_up X-Forwarded-For {remote_host}" in caddy

    assert "listen 127.0.0.1:8081;" in nginx
    assert "server 127.0.0.1:28080;" in nginx
    assert "set_real_ip_from 127.0.0.1;" in nginx
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in nginx
    assert "client_max_body_size 12m;" in nginx
    assert "client_max_body_size 11m;" in nginx
    assert "limit_req_zone $binary_remote_addr zone=orinoco_login" in nginx
    assert "limit_req_zone $binary_remote_addr zone=orinoco_chat" in nginx

def test_searxng_endpoint_is_admin_only_and_hidden() -> None:
    """The outbound search service endpoint must not be user-editable."""
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    endpoint = next(v for v in egg["variables"] if v["env_variable"] == "SEARXNG_URL")

    assert endpoint["user_viewable"] is False
    assert endpoint["user_editable"] is False

def test_trusted_proxy_allowlist_is_hidden_and_admin_only() -> None:
    """Client-IP trust can only be configured by the Panel administrator."""
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    variable = next(v for v in egg["variables"] if v["env_variable"] == "ORINOCO_TRUSTED_PROXY_IPS")

    assert variable["default_value"] == ""
    assert variable["user_viewable"] is False
    assert variable["user_editable"] is False


def test_model_choices_match_confirmed_stable_auto_download_configuration() -> None:
    """Keep the curated multi-model selector and automatic download default aligned."""
    egg = json.loads((ROOT / "egg" / "egg-orinoco.json").read_text(encoding="utf-8"))
    variables = {item["env_variable"]: item for item in egg["variables"]}

    assert egg["images"] == ["ghcr.io/lcswolf/orinoco-ai:stable"]
    assert variables["AI_MODEL"]["default_value"] == "qwen2.5:1.5b"
    assert variables["AI_MODEL"]["rules"] == "required|string|in:qwen2.5:0.5b,qwen2.5:1.5b,qwen2.5:3b"
    assert variables["AUTO_DOWNLOAD_MODEL"]["default_value"] == "true"


def test_model_download_has_bounded_transient_retries_and_clear_failure() -> None:
    """A registry hiccup gets retries, but an exhausted pull fails visibly."""
    script = (ROOT / "docker" / "model-init.sh").read_text(encoding="utf-8")

    assert "max_pull_attempts=3" in script
    assert 'until /usr/local/bin/ollama pull "$MODEL"; do' in script
    assert "sleep 30" in script
    assert "Model download failed after $max_pull_attempts attempts." in script
    assert "readyz will remain HTTP 503" in script



def _run_model_init(tmp_path: Path, *, failures_before_success: int) -> subprocess.CompletedProcess[str]:
    """Run the real model-init script with a deterministic fake Ollama binary."""
    script = (ROOT / "docker" / "model-init.sh").read_text(encoding="utf-8")
    fake_ollama = tmp_path / "ollama"
    state_file = tmp_path / "pull-count"
    fake_ollama.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "case \"$1\" in\n"
        "  list) exit 0 ;;\n"
        "  show) exit 1 ;;\n"
        "  pull)\n"
        f"    limit={failures_before_success}\n"
        f"    count_file='{state_file}'\n"
        "    count=0\n"
        "    [ ! -f \"$count_file\" ] || count=$(cat \"$count_file\")\n"
        "    count=$((count + 1))\n"
        "    printf '%s' \"$count\" > \"$count_file\"\n"
        "    printf 'pull:%s models:%s\\n' \"$count\" \"$OLLAMA_MODELS\" >> \"$OLLAMA_TEST_LOG\"\n"
        "    [ \"$count\" -gt \"$limit\" ]\n"
        "    ;;\n"
        "  *) exit 9 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_ollama.chmod(0o755)
    fake_sleep = tmp_path / "sleep"
    fake_sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_sleep.chmod(0o755)
    script = script.replace("/usr/local/bin/ollama", str(fake_ollama))
    executable_script = tmp_path / "model-init.sh"
    executable_script.write_text(script, encoding="utf-8")
    executable_script.chmod(0o755)
    log_file = tmp_path / "ollama.log"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}",
        "AUTO_DOWNLOAD_MODEL": "true",
        "AI_MODEL": "qwen2.5:1.5b",
        "OLLAMA_MODELS": str(tmp_path / "persistent-models"),
        "OLLAMA_TEST_LOG": str(log_file),
    }
    result = subprocess.run(
        ["/bin/sh", str(executable_script)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    result.ollama_log = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
    return result


def test_model_init_recovers_after_transient_pull_failures(tmp_path: Path) -> None:
    """A transient registry failure is retried and the later successful pull completes."""
    result = _run_model_init(tmp_path, failures_before_success=2)

    assert result.returncode == 0, result.stderr
    assert result.ollama_log.count("pull:") == 3
    assert f"models:{tmp_path / 'persistent-models'}" in result.ollama_log
    assert "downloaded successfully" in result.stdout


def test_model_init_stops_after_three_failed_pulls(tmp_path: Path) -> None:
    """An unavailable registry fails visibly after the configured retry budget."""
    result = _run_model_init(tmp_path, failures_before_success=99)

    assert result.returncode == 1
    assert result.ollama_log.count("pull:") == 3
    assert "failed after 3 attempts" in result.stderr
    assert "readyz will remain HTTP 503" in result.stderr
