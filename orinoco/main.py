"""Orinoco web application entry point."""

from __future__ import annotations

import os
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from orinoco import __version__
from orinoco.admin.routes import router as admin_router
from orinoco.memories.routes import router as memories_router
from orinoco.research.routes import router as research_router
from orinoco.preferences.routes import router as preferences_router
from orinoco.documents.routes import router as documents_router
from orinoco.documents.admin_routes import router as shared_documents_router
from orinoco.chat.routes import router as chat_router
from orinoco.auth.routes import router as auth_router
from orinoco.auth.sessions import get_session_secret, secure_cookie_enabled
from orinoco.logging_config import configure_logging, current_request_id, reset_request_id, set_request_id
from orinoco.resources import get_resource_profile, resolve_ai_threads

configure_logging()
logger = logging.getLogger("orinoco.http")

# Detect container limits once as the web application starts. The same cached
# profile is used by inference requests and the administrator diagnostics view.
RESOURCE_PROFILE = get_resource_profile()
AI_THREAD_COUNT = resolve_ai_threads(RESOURCE_PROFILE)
logger.info(
    "Container resources detected: %s CPU(s), %s inference thread(s), memory limit %s bytes",
    RESOURCE_PROFILE.cpu_count,
    AI_THREAD_COUNT,
    RESOURCE_PROFILE.memory_limit_bytes,
    extra={"event_code": "resources.detected"},
)

OLLAMA_API_BASE = "http://127.0.0.1:11434"
DEFAULT_MODEL = os.environ.get("AI_MODEL", "qwen2.5:1.5b")
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Orinoco",
    description="A self-hosted personal AI assistant.",
    version=__version__,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_session_secret(),
    session_cookie="orinoco_session",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=secure_cookie_enabled(),
)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(memories_router)
app.include_router(research_router)
app.include_router(preferences_router)
app.include_router(documents_router)
app.include_router(shared_documents_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")



@app.middleware("http")
async def request_body_limit(request, call_next):
    """Reject oversized declared request bodies before FastAPI parses them.

    The reverse proxy must also enforce a body limit for chunked requests that
    do not carry Content-Length; the application check is defence in depth.
    """
    raw_length = request.headers.get("content-length")
    if raw_length is not None:
        try:
            content_length = int(raw_length)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        if content_length < 0:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        try:
            max_bytes = int(os.environ.get("ORINOCO_MAX_REQUEST_BODY_BYTES", str(12 * 1024 * 1024)))
        except ValueError:
            return JSONResponse(status_code=500, content={"detail": "Request body limit is misconfigured."})
        if max_bytes < 1024:
            return JSONResponse(status_code=500, content={"detail": "Request body limit is misconfigured."})
        if content_length > max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "The request body exceeds the configured size limit."},
            )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request, call_next):
    """Apply conservative browser security headers to app and static responses."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; form-action 'self'; "
        "frame-ancestors 'none'; object-src 'none'; img-src 'self' data:; "
        "font-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'",
    )
    return response


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
    async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
        response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise ValueError("Ollama returned an invalid model list")

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


@app.middleware("http")
async def request_correlation(request, call_next):
    """Attach a non-sensitive correlation ID to each request and its response."""
    supplied = request.headers.get("x-request-id")
    token = set_request_id(supplied)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = current_request_id()
        return response
    except Exception as exc:
        # Do not log exception text or request data: either may contain user content.
        logger.error(
            "Unhandled request failure (%s)",
            type(exc).__name__,
            extra={"event_code": "http.unhandled_exception"},
        )
        raise
    finally:
        reset_request_id(token)
