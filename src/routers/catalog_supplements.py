"""Supplementary material outside the playable node graph."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from config import BOOKS_DIR
from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Catalog"])


def _asset_url(book_id: str, path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("/api/"):
        return path
    relative = path.lstrip("/")
    if not (BOOKS_DIR / book_id / relative).is_file():
        return None
    return f"/api/books/{book_id}/asset/{relative}"


@router.get("/books/{book_id}/supplements")
def get_book_supplements(book_id: str, authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization)
    if book_id not in engine.books:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if engine.db.get_book_tier(book_id)["level"] > engine.db.get_user_active_tier(user_id)["level"]:
        raise HTTPException(status_code=403, detail="Tu membresía no permite acceder a este libro")
    supplements = [{
        "id": item.get("id"),
        "order": item.get("order", 0),
        "category": item.get("category", "reference"),
        "title": item.get("title", "Material adicional"),
        "text": item.get("text", ""),
        "source_pages": item.get("source_pages", []),
        "images": [url for image in item.get("images", []) if (url := _asset_url(book_id, image))],
        "audio_url": _asset_url(book_id, item.get("audio")),
    } for item in engine.books[book_id].get("supplements", [])]
    return {
        "book_id": book_id,
        "title": engine.books[book_id].get("title"),
        "supplements": supplements,
        "groups": {category: [item for item in supplements if item["category"] == category]
                   for category in ("front_matter", "reference", "back_matter")},
    }
