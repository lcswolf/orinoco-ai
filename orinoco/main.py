"""Minimal Orinoco API entry point.

This is the first runnable foundation, not the finished assistant UI.
"""

from fastapi import FastAPI

from orinoco import __version__

app = FastAPI(
    title="Orinoco",
    description="A self-hosted personal AI assistant.",
    version=__version__,
    docs_url=None,
    redoc_url=None,
)


@app.get("/", include_in_schema=False)
async def index() -> dict[str, str]:
    return {
        "name": "Orinoco",
        "status": "starting",
        "message": "The Orinoco application foundation is running.",
    }


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "orinoco",
        "version": __version__,
    }
