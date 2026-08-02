import random
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import FileResponse

from config import BOOKS_DIR
from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Catalog"])

@router.get("/tags")
def get_tags(authorization: Optional[str] = Header(None)):
    """Returns top category/series tags for filtering."""
    resolve_user_id(authorization)
    tags = engine.db.get_top_tags(limit=5)
    return {"tags": tags}

@router.get("/narrators")
def get_narrators(authorization: Optional[str] = Header(None)):
    """Returns configured narrators with story count stats."""
    resolve_user_id(authorization)
    narrators = engine.db.get_narrators_stats()
    return {"narrators": narrators}

@router.get("/books")
def list_books(
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    random_sample: Optional[bool] = Query(False),
    narrator: Optional[str] = Query(None)
):
    """Returns a list of imported books with rich metadata and user progress status."""
    current_uid = resolve_user_id(authorization)
    user_tier = engine.db.get_user_active_tier(current_uid)
    books = engine.list_books()

    is_en_curso_filter = tag and tag.lower() == "en curso"
    in_progress_ids = set()

    if random_sample and not is_en_curso_filter:
        in_progress_list = engine.db.get_in_progress_games(current_uid, limit=10)
        in_progress_ids = set(g["book_id"] for g in in_progress_list)

    if narrator and narrator.lower() != "todos":
        books = [b for b in books if (engine.books.get(b["book_id"], {}).get("narrator") or "DaveFX").lower() == narrator.lower()]

    result = []
    
    for b_summary in books:
        b_id = b_summary["book_id"]
        
        if random_sample and not is_en_curso_filter and b_id in in_progress_ids:
            continue

        full_data = engine.books.get(b_id, {})
        
        book_tier = engine.db.get_book_tier(b_id)
        if book_tier.get("is_visible") == 0:
            user = engine.db.get_user_by_token(authorization.split(" ")[1]) if authorization and authorization.startswith("Bearer ") else None
            if not (user and user.get("role_name") == "admin"):
                continue

        genre = full_data.get("genre") or "Aventura"
        series = full_data.get("series")
        if tag and tag.lower() != "todos":
            tag_l = tag.lower()
            if is_en_curso_filter:
                pass
            elif not (tag_l in genre.lower() or (series and tag_l in series.lower())):
                continue

        savegame = engine.db.get_savegame(current_uid, b_id)
        visited_count = 0
        if savegame:
            history = engine.db.get_history(current_uid, b_id, limit=500)
            visited_count = len(set(h["to_node_id"] for h in history))
        
        total_sections = full_data.get("total_sections", 1)
        progress_pct = min(100, int((visited_count / max(1, total_sections)) * 100))
        
        if is_en_curso_filter and progress_pct == 0:
            continue

        status = "non-started"
        if progress_pct >= 100:
            status = "completed"
        elif progress_pct > 0:
            status = "in-progress"

        is_locked = book_tier["level"] > user_tier["level"]

        narrator_id = full_data.get("narrator_id") or 1
        narrator_obj = engine.db.get_narrator_by_id(narrator_id) if narrator_id else None
        narrator_name = narrator_obj.get("display_name") if narrator_obj else (full_data.get("narrator") or "DAVEFX (Piper Local)")

        result.append({
            "book_id": b_id,
            "title": full_data.get("title", b_id),
            "author": full_data.get("author", "Desconocido"),
            "publisher": full_data.get("publisher", "Desconocido"),
            "year": full_data.get("year", "2026"),
            "language": full_data.get("language", "es"),
            "description": full_data.get("description", ""),
            "isbn": full_data.get("isbn", ""),
            "genre": genre,
            "series": series,
            "volume": full_data.get("volume", 1),
            "estimated_duration": full_data.get("estimated_duration", "30 minutos"),
            "cover_image_url": f"/api/books/{b_id}/asset/{full_data.get('cover_image')}" if full_data.get("cover_image") else None,
            "total_sections": full_data.get("total_sections", 0),
            "start_node": full_data.get("start_node", "sec_002"),
            "features": full_data.get("features", {}),
            "has_savegame": bool(savegame),
            "progress_percent": progress_pct,
            "status": status,
            "narrator_id": narrator_id,
            "narrator": narrator_name,
            "tier_id": book_tier["tier_id"],
            "tier_code": book_tier["code"],
            "tier_name": book_tier["name"],
            "tier_level": book_tier["level"],
            "is_locked": is_locked,
            "rating": 4.8
        })

    if random_sample and result:
        random.shuffle(result)

    if limit and limit > 0:
        result = result[:limit]

    return {"books": result}

@router.get("/books/{book_id}")
def get_book_details(book_id: str):
    """Returns details for a single book."""
    if book_id not in engine.books:
        raise HTTPException(status_code=404, detail="Book not found")
    b_data = engine.books[book_id]
    return {
        "book_id": book_id,
        "title": b_data.get("title"),
        "author": b_data.get("author"),
        "publisher": b_data.get("publisher"),
        "year": b_data.get("year"),
        "description": b_data.get("description"),
        "cover_image_url": f"/api/books/{book_id}/asset/{b_data.get('cover_image')}" if b_data.get('cover_image') else None,
        "total_sections": b_data.get("total_sections"),
        "start_node": b_data.get("start_node"),
        "features": b_data.get("features", {})
    }

@router.get("/books/{book_id}/asset/{subpath:path}")
def get_book_asset(book_id: str, subpath: str):
    """Serves static assets (images and audio files) for a given book safely."""
    target_dir = (BOOKS_DIR / book_id).resolve()
    asset_path = (target_dir / subpath).resolve()

    if not str(asset_path).startswith(str(target_dir)):
        raise HTTPException(status_code=403, detail="Acceso denegado. Ruta no permitida.")

    if not asset_path.exists() or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return FileResponse(asset_path)

@router.get("/narrators")
def list_narrators(limit: int = 3):
    """Returns active narrator voices from SQLite DB sorted by most books narrated (top limit)."""
    raw_narrators = engine.db.get_narrators_stats()
    raw_narrators.sort(key=lambda x: x.get("book_count", 0), reverse=True)
    if limit and limit > 0:
        raw_narrators = raw_narrators[:limit]

    narrators = []
    for n in raw_narrators:
        b_count = n.get("book_count") if n.get("book_count") is not None else 0
        narrators.append({
            "id": str(n.get("narrator_id") or n.get("name")),
            "narrator_id": n.get("narrator_id"),
            "name": n.get("display_name") or n.get("name"),
            "specialty": n.get("specialty") or "Narrador Profesional",
            "avatar_url": n.get("avatar_url") or "/assets/narrator_davefx.jpg",
            "story_count": b_count,
            "book_count": b_count,
            "engine_code": n.get("engine_code"),
            "engine_name": n.get("engine_name"),
            "language": n.get("language", "es")
        })
    return {"narrators": narrators}
