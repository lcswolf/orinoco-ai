"""Explicit, authenticated web-search API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from orinoco.db import User, get_database_path, get_user_by_id, initialise_database
from orinoco.research.searxng import SearchUnavailable, SearXNGClient

router = APIRouter(prefix="/api/research", tags=["research"])


def _current_user(request: Request) -> User:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    database_path = get_database_path()
    initialise_database(database_path)
    user = get_user_by_id(user_id, database_path=database_path)
    if user is None or not user.active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


@router.get("/search")
async def search_web(
    request: Request,
    q: str = Query(min_length=3, max_length=300),
) -> dict[str, object]:
    _current_user(request)
    client: SearXNGClient | None = None
    try:
        client = SearXNGClient()
        results = await client.search(q)
    except (SearchUnavailable, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if client is not None:
            await client.aclose()
    return {"query": " ".join(q.split()), "results": results}
