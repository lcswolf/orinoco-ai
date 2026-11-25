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


def test_nginx_proxy_is_loopback_only_and_overwrites_forwarded_client_ip() -> None:
    """The app must receive a proxy-derived client address, not client spoofing."""
    template = (ROOT / "deploy" / "nginx" / "orinoco.conf.example").read_text(encoding="utf-8")
    assert "listen 127.0.0.1:8081;" in template
    assert "set_real_ip_from 127.0.0.1;" in template
    assert "real_ip_header X-Forwarded-For;" in template
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in template
    assert "proxy_set_header X-Real-IP $remote_addr;" in template
    assert "limit_req zone=orinoco_login" in template
    assert "limit_req zone=orinoco_chat" in template
    assert "client_max_body_size 12m;" in template
    assert "client_max_body_size 11m;" in template


def test_caddy_public_ingress_keeps_domain_ip_and_tls_boundaries() -> None:
    """Public ingress uses TLS and forwards only to the local Nginx edge."""
    template = (ROOT / "deploy" / "caddy" / "Caddyfile.example").read_text(encoding="utf-8")
    assert "default_sni {$ORINOCO_PUBLIC_IPV4}" in template
    assert "https://{$ORINOCO_PUBLIC_IPV4}:8443" in template
    assert "profile shortlived" in template
    assert "reverse_proxy 127.0.0.1:8081" in template
    assert "header_up X-Forwarded-For {remote_host}" in template
