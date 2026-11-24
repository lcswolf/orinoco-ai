"""Regression checks for the documented host-side reverse-proxy boundary."""

import re
from inspect import signature
from pathlib import Path

from orinoco.llm.ollama import OllamaClient


ROOT = Path(__file__).resolve().parents[1]


def test_nginx_model_response_timeout_exceeds_local_ollama_timeout() -> None:
    """The edge proxy must not time out before the local model request does."""
    template = (ROOT / "deploy" / "nginx" / "orinoco.conf.example").read_text(encoding="utf-8")
    deployment_guide = (ROOT / "docs" / "NETWORK_DEPLOYMENT.md").read_text(encoding="utf-8")
    app_timeout = signature(OllamaClient.__init__).parameters["timeout"].default

    template_match = re.search(r"^\s*proxy_read_timeout\s+(\d+)s;", template, re.MULTILINE)
    guide_match = re.search(r"^\s*proxy_read_timeout\s+(\d+)s;", deployment_guide, re.MULTILINE)

    assert template_match is not None
    assert guide_match is not None
    assert int(template_match.group(1)) > app_timeout
    assert int(guide_match.group(1)) == int(template_match.group(1))
