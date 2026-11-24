"""Orinoco web application entry point."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from orinoco import __version__

OLLAMA_API_BASE = os.environ.get("ORINOCO_OLLAMA_API", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("AI_MODEL", "qwen2.5:1.5b")
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Orinoco",
    description="A self-hosted personal AI assistant.",
    version=__version__,
    docs_url=None,
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the custom Orinoco web interface."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness check: confirms that the web process is responding."""
    return {
        "status": "ok",
        "service": "orinoco",
        "version": __version__,
    }


async def get_ollama_readiness() -> dict[str, str]:
    """Check whether Ollama is reachable and the configured model is present."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
        response.raise_for_status()
        payload = response.json()

    available_models = {
        item.get("name") or item.get("model")
        for item in payload.get("models", [])
        if isinstance(item, dict)
    }
    if DEFAULT_MODEL not in available_models:
        return {
            "status": "model_missing",
            "service": "orinoco",
            "model": DEFAULT_MODEL,
        }

    return {
        "status": "ready",
        "service": "orinoco",
        "model": DEFAULT_MODEL,
    }


@app.get("/readyz", include_in_schema=False)
async def readyz():
    """Readiness check: confirms the local model service and selected model exist."""
    try:
        result = await get_ollama_readiness()
    except (httpx.HTTPError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"status": "ollama_unavailable", "service": "orinoco"},
        )

    if result["status"] != "ready":
        return JSONResponse(status_code=503, content=result)

    return result
