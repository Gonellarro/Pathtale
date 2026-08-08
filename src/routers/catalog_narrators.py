"""Narrator discovery for the landing page and library."""

from typing import Optional

from fastapi import APIRouter, Header

from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Catalog"])


@router.get("/narrators")
def list_narrators(limit: int = 3, authorization: Optional[str] = Header(None)):
    resolve_user_id(authorization)
    narrators = engine.db.get_narrators_stats()
    narrators.sort(key=lambda item: item.get("book_count", 0), reverse=True)
    selected_narrators = narrators[:limit] if limit > 0 else narrators
    return {"narrators": [{
        "id": str(item.get("narrator_id") or item.get("name")),
        "narrator_id": item.get("narrator_id"),
        "name": item.get("display_name") or item.get("name"),
        "specialty": item.get("specialty") or "Narrador Profesional",
        "avatar_url": item.get("avatar_url") or "/assets/narrator_davefx.jpg",
        "story_count": item.get("book_count") or 0,
        "book_count": item.get("book_count") or 0,
        "engine_code": item.get("engine_code"),
        "engine_name": item.get("engine_name"),
        "language": item.get("language", "es"),
    } for item in selected_narrators]}
