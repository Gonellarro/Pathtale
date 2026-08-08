"""Public book catalogue routes and their presentation rules."""

import random
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Catalog"])


@router.get("/tags")
def get_tags(authorization: Optional[str] = Header(None)):
    resolve_user_id(authorization)
    return {"tags": engine.db.get_top_tags(limit=5)}


@router.get("/books")
def list_books(
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    random_sample: bool = Query(False),
    latest: bool = Query(False),
    narrator: Optional[str] = Query(None),
):
    current_uid = resolve_user_id(authorization)
    user_tier = engine.db.get_user_active_tier(current_uid)
    books = engine.list_books()
    is_in_progress_filter = bool(tag and tag.lower() == "en curso")
    in_progress_ids = set()
    if random_sample and not is_in_progress_filter:
        in_progress_ids = {save["book_id"] for save in engine.db.get_in_progress_games(current_uid, limit=10)}
    if narrator and narrator.lower() != "todos":
        books = [
            book for book in books
            if (engine.books.get(book["book_id"], {}).get("narrator") or "DaveFX").lower() == narrator.lower()
        ]

    result = []
    for summary in books:
        book_id = summary["book_id"]
        if random_sample and not is_in_progress_filter and book_id in in_progress_ids:
            continue
        document = engine.books.get(book_id, {})
        database_book = engine.db.get_book_by_id(book_id) or {}
        if database_book.get("is_visible", 1) == 0:
            continue
        tier = engine.db.get_book_tier(book_id)
        genre = document.get("genre") or "Aventura"
        series = document.get("series")
        if tag and tag.lower() != "todos" and not is_in_progress_filter:
            tag_value = tag.lower()
            if tag_value not in genre.lower() and not (series and tag_value in series.lower()):
                continue

        savegame = engine.db.get_savegame(current_uid, book_id)
        history = engine.db.get_history(current_uid, book_id, limit=500) if savegame else []
        total_sections = document.get("total_sections", 1)
        visited_nodes = {row["to_node_id"] for row in history}
        progress = min(100, int((len(visited_nodes) / max(1, total_sections)) * 100))
        if is_in_progress_filter and progress == 0:
            continue
        narrator_id = document.get("narrator_id") or 1
        narrator_record = engine.db.get_narrator_by_id(narrator_id) if narrator_id else None
        result.append({
            "book_id": book_id,
            "title": document.get("title", book_id),
            "author": document.get("author", "Desconocido"),
            "publisher": document.get("publisher", "Desconocido"),
            "year": document.get("year", "2026"),
            "language": document.get("language", "es"),
            "description": document.get("description", ""),
            "isbn": document.get("isbn", ""),
            "genre": genre,
            "series": series,
            "volume": document.get("volume", 1),
            "estimated_duration": document.get("estimated_duration", "30 minutos"),
            "cover_image_url": f"/api/books/{book_id}/asset/{document['cover_image']}" if document.get("cover_image") else None,
            "total_sections": document.get("total_sections", 0),
            "start_node": document.get("start_node", "sec_002"),
            "features": document.get("features", {}),
            "has_savegame": bool(savegame),
            "progress_percent": progress,
            "status": "completed" if progress >= 100 else "in-progress" if progress else "non-started",
            "narrator_id": narrator_id,
            "narrator": narrator_record.get("display_name") if narrator_record else document.get("narrator", "DAVEFX (Piper Local)"),
            "tier_id": tier["tier_id"],
            "tier_code": tier["code"],
            "tier_name": tier["name"],
            "tier_level": tier["level"],
            "is_locked": tier["level"] > user_tier["level"],
            "rating": engine.db.get_book_rating_summary(book_id).get("average"),
            "created_at": database_book.get("created_at"),
            "has_supplements": bool(document.get("supplements")),
            "supplement_count": len(document.get("supplements", [])),
        })
    if latest:
        result.sort(key=lambda book: (book.get("created_at") or "", book["book_id"]), reverse=True)
    elif random_sample:
        random.shuffle(result)
    return {"books": result[:limit] if limit and limit > 0 else result}


@router.get("/books/{book_id}")
def get_book_details(book_id: str):
    if book_id not in engine.books:
        raise HTTPException(status_code=404, detail="Book not found")
    book = engine.books[book_id]
    return {
        "book_id": book_id,
        "title": book.get("title"),
        "author": book.get("author"),
        "publisher": book.get("publisher"),
        "year": book.get("year"),
        "description": book.get("description"),
        "cover_image_url": f"/api/books/{book_id}/asset/{book['cover_image']}" if book.get("cover_image") else None,
        "total_sections": book.get("total_sections"),
        "start_node": book.get("start_node"),
        "features": book.get("features", {}),
        "has_supplements": bool(book.get("supplements")),
        "supplement_count": len(book.get("supplements", [])),
    }
