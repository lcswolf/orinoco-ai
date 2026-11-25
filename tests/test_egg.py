"""Regression checks for the Pterodactyl Egg import definition.

These checks mirror the stable Panel 1.13.0 parser's PTDL_v1 acceptance
rules and catch malformed or unsafe project-specific Egg configuration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


EGG_PATH = Path(__file__).resolve().parents[1] / "egg" / "egg-orinoco.json"


@pytest.fixture(scope="module")
def egg() -> dict:
    """Load the checked-in Egg exactly as Pterodactyl receives it."""
    return json.loads(EGG_PATH.read_text(encoding="utf-8"))


def test_egg_uses_a_panel_1_x_supported_format(egg: dict) -> None:
    """Panel 1.13.0 accepts PTDL_v1 and converts it during import."""
    assert egg["meta"]["version"] in {"PTDL_v1", "PTDL_v2"}
    assert egg["name"] == "Orinoco AI Assistant"
    assert egg["startup"]
    assert isinstance(egg["config"], dict)
    assert isinstance(egg["scripts"]["installation"]["script"], str)


def test_egg_author_is_a_valid_email_address(egg: dict) -> None:
    """Pterodactyl validates the Egg author as an email address."""
    author = egg["author"]
    assert re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", author)


def test_egg_has_a_named_container_image_and_install_script(egg: dict) -> None:
    """The imported Egg must define at least one image and an installer."""
    assert egg["images"]
    assert all(isinstance(image, str) and image for image in egg["images"])
    installation = egg["scripts"]["installation"]
    assert installation["container"]
    assert installation["entrypoint"]


def test_egg_variables_are_unique_and_well_formed(egg: dict) -> None:
    """Reject duplicate environment names and incomplete Panel variables."""
    variables = egg["variables"]
    names = [item["env_variable"] for item in variables]
    assert len(names) == len(set(names))
    for item in variables:
        assert item["name"]
        assert item["description"]
        assert item["default_value"] is not None
        assert item["rules"]
        assert isinstance(item["user_viewable"], bool)
        assert isinstance(item["user_editable"], bool)


def test_egg_keeps_unimplemented_discord_and_voice_disabled(egg: dict) -> None:
    """Future integrations must not be advertised as active prematurely."""
    variables = {item["env_variable"]: item for item in egg["variables"]}
    assert variables["ENABLE_DISCORD"]["default_value"] == "false"
    assert variables["ENABLE_VOICE"]["default_value"] == "false"
    assert variables["ENABLE_DISCORD"]["user_editable"] is False
    assert variables["ENABLE_VOICE"]["user_editable"] is False


def test_egg_uses_the_curated_local_model_options(egg: dict) -> None:
    """Keep model choices aligned with the Ollama initialisation script."""
    variables = {item["env_variable"]: item for item in egg["variables"]}
    model = variables["AI_MODEL"]
    assert model["default_value"] == "qwen2.5:1.5b"
    assert "qwen2.5:0.5b" in model["rules"]
    assert "qwen2.5:1.5b" in model["rules"]
    assert "qwen2.5:3b" in model["rules"]
    assert variables["AUTO_DOWNLOAD_MODEL"]["default_value"] == "true"



def test_active_egg_environment_variables_are_used_by_runtime(egg: dict) -> None:
    """Catch misspelled or stale Egg variables before the Panel import test."""
    repository_root = EGG_PATH.resolve().parents[1]
    runtime_files = [
        *repository_root.joinpath("orinoco").rglob("*.py"),
        *repository_root.joinpath("docker").rglob("*.py"),
        *repository_root.joinpath("docker").rglob("*.sh"),
        *repository_root.joinpath("docker").rglob("*.conf"),
        repository_root / "docker" / "Dockerfile",
    ]
    runtime_source = "\n".join(
        file.read_text(encoding="utf-8")
        for file in runtime_files
        if file.is_file()
    )
    # These three variables are deliberately reserved for integrations that
    # are disabled in this release and must not be wired into active runtime.
    reserved = {"DISCORD_TOKEN", "ENABLE_DISCORD", "ENABLE_VOICE"}
    unused = [
        item["env_variable"]
        for item in egg["variables"]
        if item["env_variable"] not in reserved
        and item["env_variable"] not in runtime_source
    ]
    assert unused == [], f"Egg variables not referenced by runtime: {unused}"


def test_egg_persistent_data_paths_match_install_and_runtime(egg: dict) -> None:
    """The install script creates the same persistent data root used by Orinoco."""
    repository_root = EGG_PATH.resolve().parents[1]
    installation = egg["scripts"]["installation"]["script"]
    model_init = (repository_root / "docker" / "model-init.sh").read_text(encoding="utf-8")
    ollama_start = (repository_root / "docker" / "ollama-start.sh").read_text(encoding="utf-8")
    assert "/mnt/server/data/models" in installation
    assert "/mnt/server/data/documents" in installation
    assert "/home/container/data/models" in model_init
    assert "/home/container/data/models" in ollama_start
    variables = {item["env_variable"]: item for item in egg["variables"]}
    assert variables["ORINOCO_DATABASE_PATH"]["default_value"].startswith("/home/container/data/")
