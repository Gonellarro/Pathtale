"""Read-only reading progress and history routes."""

from typing import Optional

from fastapi import APIRouter, Header

from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Game"])


@router.get("/games/{user_id}/last_active")
def get_last_active_game(user_id: int, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    last_game = engine.db.get_last_active_game(uid)
    if not last_game:
        return {"has_active_game": False}
    book_id = last_game["book_id"]
    book = engine.db.get_book_by_id(book_id) or {}
    if book.get("is_visible", 1) == 0:
        return {"has_active_game": False}
    return {
        "has_active_game": True,
        "book_id": book_id,
        "book_title": engine.books.get(book_id, {}).get("title", book_id),
        "current_node_id": last_game["current_node_id"],
        "updated_at": last_game["updated_at"],
    }


@router.get("/games/{user_id}/in_progress")
def get_in_progress_games(user_id: int, limit: int = 3, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    result = []
    for save in engine.db.get_in_progress_games(uid, limit=limit):
        book_id = save["book_id"]
        book_record = engine.db.get_book_by_id(book_id) or {}
        if book_record.get("is_visible", 1) == 0:
            continue
        book = engine.books.get(book_id, {})
        history = engine.db.get_history(uid, book_id, limit=500)
        visited_count = len({entry["to_node_id"] for entry in history})
        total_sections = book.get("total_sections", 1)
        result.append({
            "book_id": book_id,
            "title": book.get("title", book_id),
            "genre": book.get("genre", "Ficción Interactiva"),
            "cover_image_url": f"/api/books/{book_id}/asset/{book['cover_image']}" if book.get("cover_image") else None,
            "estimated_duration": book.get("estimated_duration", "30 min"),
            "total_sections": total_sections,
            "progress_percent": min(100, int((visited_count / max(1, total_sections)) * 100)),
            "updated_at": save["updated_at"],
        })
    return {"in_progress": result}


@router.get("/games/{user_id}/{book_id}/history")
def get_game_history(user_id: int, book_id: str, authorization: Optional[str] = Header(None)):
    return engine.db.get_history(resolve_user_id(authorization), book_id)
