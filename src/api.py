import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import BOOKS_DIR, BASE_DIR
from src.engine import GameEngine
from src.stt import STTManager
from src.voice_parser import VoiceParser

logger = logging.getLogger("API")

app = FastAPI(
    title="PathTale Engine API",
    description="REST API para alimentar PWA, Móvil, Telegram y otras interfaces de ficción interactiva.",
    version="1.0.0"
)

# Enable CORS for PWA and Web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = GameEngine()
stt_manager = STTManager()
voice_parser = VoiceParser()

WEB_DIR = BASE_DIR / "web"
temp_dir = BASE_DIR / "data" / "temp"
temp_dir.mkdir(parents=True, exist_ok=True)

# Pydantic Request Models
class StartGameRequest(BaseModel):
    user_id: Optional[int] = 1
    book_id: str

class ChoiceRequest(BaseModel):
    choice_id: Optional[Any] = None
    target_node: Optional[str] = None
    text: Optional[str] = None
    text_query: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    first_name: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Admin Pydantic Request Models
class AdminUserCreateRequest(BaseModel):
    username: str
    password: str
    first_name: Optional[str] = None
    role: Optional[str] = "user"

class AdminUserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class AdminNarratorCreateRequest(BaseModel):
    name: str
    display_name: str
    specialty: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

class AdminNarratorUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    specialty: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

class AdminBookUpdateRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    narrator_id: Optional[int] = None
    tier_id: Optional[int] = None
    is_visible: Optional[bool] = None
    genre: Optional[str] = None
    series: Optional[str] = None
    volume: Optional[int] = None
    description: Optional[str] = None
    language: Optional[str] = None

class AdminUserSubscriptionRequest(BaseModel):
    tier_id: int
    duration_days: Optional[int] = None

# Helper to resolve user_id from Authorization Bearer header or fallback
def resolve_user_id(authorization: Optional[str] = Header(None), query_user_id: Optional[int] = None) -> int:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user = engine.db.get_user_by_token(token)
        if user:
            return user["user_id"]
    return query_user_id or 1

# Helper to enforce Admin Role for backend endpoints
def require_admin(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado. Token requerido.")
    token = authorization.split(" ")[1]
    user = engine.db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")
    if user.get("role_name") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requiere rol de Administrador.")
    return user

ENABLE_PUBLIC_REGISTRATION = False  # Single toggle flag: set to True to open public registration

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    """Registers a new user account."""
    if not ENABLE_PUBLIC_REGISTRATION:
        raise HTTPException(status_code=403, detail="Temporalmente deshabilitado. Solo altas con invitación.")
    try:
        user_info = engine.db.register_user(req.username, req.password, req.first_name)
        return {"status": "success", "user": user_info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Authenticates user and returns session token."""
    try:
        user_info = engine.db.login_user(req.username, req.password)
        return {"status": "success", "user": user_info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    """Logs out user by destroying active session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        engine.db.logout_user(token)
    return {"status": "success"}

@app.get("/api/auth/me")
def get_me(authorization: Optional[str] = Header(None)):
    """Returns profile, subscription tier, and statistics for currently authenticated user."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user = engine.db.get_user_by_token(token)
        if user:
            stats = engine.db.get_user_stats(user["user_id"])
            active_tier = engine.db.get_user_active_tier(user["user_id"])
            return {
                "authenticated": True,
                "user": user,
                "tier": active_tier,
                "stats": stats
            }
    return {
        "authenticated": False,
        "user": {"user_id": 1, "username": "invitado", "first_name": "Invitado", "settings": {}},
        "tier": {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0},
        "stats": {"books_started": 0, "decisions_made": 0}
    }

@app.get("/api/subscription_tiers")
def get_subscription_tiers():
    """Returns list of all available subscription tiers."""
    tiers = engine.db.get_all_subscription_tiers()
    return {"tiers": tiers}

# --- REST API Game Endpoints ---

@app.get("/api/tags")
def get_tags():
    """Returns top category/series tags for filtering."""
    tags = engine.db.get_top_tags(limit=5)
    return {"tags": tags}

@app.get("/api/narrators")
def get_narrators():
    """Returns configured narrators with story count stats."""
    narrators = engine.db.get_narrators_stats()
    return {"narrators": narrators}

@app.get("/api/books")
def list_books(
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    random_sample: Optional[bool] = Query(False),
    narrator: Optional[str] = Query(None)
):
    """Returns a list of imported books with rich metadata and user progress status."""
    current_uid = resolve_user_id(authorization, user_id)
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
        
        genre = full_data.get("genre") or "Ficción Interactiva"
        series = full_data.get("series") or ""
        
        savegame = engine.db.get_savegame(current_uid, b_id)
        progress_pct = 0
        status = "nuevo"

        if savegame:
            history = engine.db.get_history(current_uid, b_id, limit=500)
            visited_count = len(set(h["to_node_id"] for h in history))
            total_sections = full_data.get("total_sections", 1)
            progress_pct = min(100, int((visited_count / max(1, total_sections)) * 100))
            if progress_pct >= 90:
                status = "completado"
            else:
                status = "en_curso"

        # Tag filtering if specified
        if tag and tag.lower() != "todos":
            tag_lower = tag.lower()
            if tag_lower == "en curso":
                if not (savegame and status == "en_curso"):
                    continue
            else:
                matches_tag = (
                    tag_lower in genre.lower() or
                    tag_lower in series.lower()
                )
                if not matches_tag:
                    continue

        book_tier = engine.db.get_book_tier(b_id)
        if book_tier.get("is_visible") == 0:
            user = engine.db.get_user_by_token(authorization.split(" ")[1]) if authorization and authorization.startswith("Bearer ") else None
            if not (user and user.get("role_name") == "admin"):
                continue

        is_locked = book_tier["level"] > user_tier["level"]

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
            "narrator": full_data.get("narrator") or "DaveFX",
            "tier_id": book_tier["tier_id"],
            "tier_code": book_tier["code"],
            "tier_name": book_tier["name"],
            "tier_level": book_tier["level"],
            "is_locked": is_locked,
            "rating": 4.8
        })

    if random_sample and result:
        import random
        random.shuffle(result)

    if limit and limit > 0:
        result = result[:limit]

    return {"books": result}

@app.get("/api/books/{book_id}")
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
        "cover_image_url": f"/api/books/{book_id}/asset/{b_data.get('cover_image')}" if b_data.get("cover_image") else None,
        "total_sections": b_data.get("total_sections"),
        "start_node": b_data.get("start_node"),
        "features": b_data.get("features", {})
    }

@app.post("/api/books/{book_id}/regenerate_audios")
def regenerate_book_audios(book_id: str):
    """Deletes existing MP3 files for a book and regenerates TTS audio files including options."""
    book_folder = BOOKS_DIR / book_id
    if not book_folder.exists():
        raise HTTPException(status_code=404, detail="Book directory not found")

    audios_dir = book_folder / "audios"
    if audios_dir.exists():
        for f in audios_dir.glob("*.mp3"):
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Could not remove audio file {f}: {e}")

    from main import get_epub_book_id
    from config import INPUT_BOOKS_DIR
    from src.importer import EPUBImporter
    
    epub_match = next((p for p in INPUT_BOOKS_DIR.glob("*.epub") if get_epub_book_id(p) == book_id), None)
    if not epub_match:
        raise HTTPException(status_code=404, detail="Original EPUB file not found in Libros/ folder")

    importer = EPUBImporter(epub_match)
    importer.process(generate_audios=True)
    engine._load_installed_books()
    return {"status": "success", "message": f"Regenerated TTS audios for '{book_id}' with options."}

# --- Admin Dashboard Endpoints ---

@app.get("/api/admin/users")
def admin_list_users(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"users": engine.db.get_all_users_admin()}

@app.post("/api/admin/users")
def admin_create_user(req: AdminUserCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        user_info = engine.db.create_user_admin(req.username, req.password, req.first_name, req.role or "user")
        return {"status": "success", "user": user_info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, req: AdminUserUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.update_user_admin(user_id, req.first_name, req.role, req.password)
    return {"status": "success", "message": f"Usuario {user_id} actualizado."}

@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        engine.db.delete_user_admin(user_id)
        return {"status": "success", "message": f"Usuario {user_id} eliminado."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/narrators")
def admin_list_narrators(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"narrators": engine.db.get_narrators_stats()}

@app.post("/api/admin/narrators")
def admin_create_narrator(req: AdminNarratorCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    narrator_info = engine.db.create_narrator_admin(req.name, req.display_name, req.specialty, req.avatar_url, req.bio)
    return {"status": "success", "narrator": narrator_info}

@app.put("/api/admin/narrators/{narrator_id}")
def admin_update_narrator(narrator_id: int, req: AdminNarratorUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.update_narrator_admin(narrator_id, req.display_name, req.specialty, req.avatar_url, req.bio)
    return {"status": "success", "message": f"Narrador {narrator_id} actualizado."}

@app.delete("/api/admin/narrators/{narrator_id}")
def admin_delete_narrator(narrator_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        engine.db.delete_narrator_admin(narrator_id)
        return {"status": "success", "message": f"Narrador {narrator_id} eliminado."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/books")
def admin_list_books(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"books": engine.db.get_all_books_admin()}

@app.put("/api/admin/books/{book_id}")
def admin_update_book(book_id: str, req: AdminBookUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    updates = req.dict(exclude_unset=True)
    engine.db.update_book_admin(book_id, updates)
    engine._load_installed_books()
    return {"status": "success", "message": f"Libro {book_id} actualizado."}

@app.delete("/api/admin/books/{book_id}")
def admin_delete_book(book_id: str, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.delete_book_admin(book_id)
    engine._load_installed_books()
    return {"status": "success", "message": f"Libro {book_id} eliminado."}

@app.post("/api/admin/books/upload")
async def admin_upload_epub_book(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Uploads an .epub file, places it in Libros/, and runs EPUBImporter pipeline with TTS."""
    require_admin(authorization)
    if not file.filename.endswith(".epub"):
        raise HTTPException(status_code=400, detail="El archivo debe tener extensión .epub")

    from config import INPUT_BOOKS_DIR
    from src.importer import EPUBImporter

    INPUT_BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = INPUT_BOOKS_DIR / file.filename

    with open(target_path, "wb") as f:
        content = await file.read()
        f.write(content)

    logger.info(f"📖 Web EPUB Upload received: '{file.filename}'. Starting import pipeline...")
    importer = EPUBImporter(target_path)
    book_folder = importer.process(generate_audios=True)
    engine._load_installed_books()

    return {
        "status": "success",
        "message": f"Libro '{file.filename}' importado y sintetizado correctamente.",
        "book_folder": str(book_folder.name)
    }

@app.post("/api/admin/users/{user_id}/subscription")
def admin_assign_user_subscription(user_id: int, req: AdminUserSubscriptionRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.assign_user_subscription(user_id, req.tier_id, req.duration_days)
    return {"status": "success", "message": f"Suscripción del usuario #{user_id} actualizada correctamente."}

@app.get("/api/admin/logs")
def admin_list_logs(limit: int = Query(50), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    logs = engine.db.get_reading_logs_admin(limit=limit)
    return {"logs": logs}

@app.get("/api/books/{book_id}/asset/{subpath:path}")
def get_book_asset(book_id: str, subpath: str):
    """Serves static assets (images and audio files) for a given book."""
    asset_path = BOOKS_DIR / book_id / subpath
    if not asset_path.exists() or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return FileResponse(asset_path)

@app.post("/api/games")
def start_game(req: StartGameRequest, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization, req.user_id)
    user_tier = engine.db.get_user_active_tier(uid)
    book_tier = engine.db.get_book_tier(req.book_id)

    # Visibility Enforcement
    if book_tier.get("is_visible") == 0:
        user = engine.db.get_user_by_token(authorization.split(" ")[1]) if authorization and authorization.startswith("Bearer ") else None
        if not (user and user.get("role_name") == "admin"):
            raise HTTPException(
                status_code=403,
                detail="Este audiolibro no está disponible actualmente."
            )

    # Subscription Tier Access Enforcement
    if book_tier["level"] > user_tier["level"]:
        raise HTTPException(
            status_code=403,
            detail=f"Este audiolibro requiere la membresía '{book_tier['name']}'. Tu nivel actual es '{user_tier['name']}'."
        )

    state = engine.start_game(uid, req.book_id)
    if not state:
        raise HTTPException(status_code=400, detail="Could not start game session")
    return _format_game_state_response(uid, req.book_id, state)

@app.get("/favicon.ico")
def get_favicon():
    fav = WEB_DIR / "assets" / "pathtale_logo_clear.png"
    if fav.exists():
        return FileResponse(fav)
    return Response(status_code=204)

@app.get("/api/games/{user_id}/last_active")
def get_last_active_game(user_id: int, authorization: Optional[str] = Header(None)):
    """Returns the most recently played game session for the user."""
    uid = resolve_user_id(authorization, user_id)
    last_game = engine.db.get_last_active_game(uid)
    if not last_game:
        return {"has_active_game": False}

    book_id = last_game["book_id"]
    book_data = engine.books.get(book_id, {})
    return {
        "has_active_game": True,
        "book_id": book_id,
        "book_title": book_data.get("title", book_id),
        "current_node_id": last_game["current_node_id"],
        "updated_at": last_game["updated_at"]
    }

@app.get("/api/games/{user_id}/in_progress")
def get_in_progress_games(user_id: int, limit: int = 3, authorization: Optional[str] = Header(None)):
    """Returns top in-progress game sessions for the user."""
    uid = resolve_user_id(authorization, user_id)
    saves = engine.db.get_in_progress_games(uid, limit=limit)
    result = []
    for s in saves:
        b_id = s["book_id"]
        book_data = engine.books.get(b_id, {})
        history = engine.db.get_history(uid, b_id, limit=500)
        visited_count = len(set(h["to_node_id"] for h in history))
        total_sections = book_data.get("total_sections", 1)
        progress_pct = min(100, int((visited_count / max(1, total_sections)) * 100))
        
        result.append({
            "book_id": b_id,
            "title": book_data.get("title", b_id),
            "genre": book_data.get("genre", "Ficción Interactiva"),
            "cover_image_url": f"/api/books/{b_id}/asset/{book_data.get('cover_image')}" if book_data.get("cover_image") else None,
            "estimated_duration": book_data.get("estimated_duration", "30 min"),
            "total_sections": total_sections,
            "progress_percent": progress_pct,
            "updated_at": s["updated_at"]
        })
    return {"in_progress": result}

@app.get("/api/games/{user_id}/{book_id}")
def get_game_state(user_id: int, book_id: str, authorization: Optional[str] = Header(None)):
    """Retrieves current game state for active user session."""
    uid = resolve_user_id(authorization, user_id)
    state = engine.get_current_state(uid, book_id)
    if not state:
        state = engine.start_game(uid, book_id)
    return _format_game_state_response(uid, book_id, state)

@app.get("/api/games/{user_id}/{book_id}/history")
def get_game_history(user_id: int, book_id: str, authorization: Optional[str] = Header(None)):
    """Retrieves decision history for a user and book."""
    uid = resolve_user_id(authorization, user_id)
    history = engine.db.get_history(uid, book_id)
    return history

class ChoiceRequest(BaseModel):
    choice_id: Optional[Any] = None
    target_node: Optional[str] = None
    text: Optional[str] = None
    text_query: Optional[str] = None

@app.post("/api/games/{user_id}/{book_id}/choice")
def make_choice(user_id: int, book_id: str, req: ChoiceRequest, authorization: Optional[str] = Header(None)):
    """Submits a choice to advance game state."""
    uid = resolve_user_id(authorization, user_id)
    state = engine.get_current_state(uid, book_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game session not found")

    choices = state["current_node"]["choices"]
    chosen = None

    if req.choice_id is not None and str(req.choice_id).strip() != "":
        chosen = next((c for c in choices if str(c.get("choice_id")) == str(req.choice_id)), None)

    if not chosen and req.target_node:
        chosen = next((c for c in choices if str(c.get("target_node")) == str(req.target_node)), None)

    if not chosen:
        query_text = req.text or req.text_query
        if query_text:
            chosen = voice_parser.parse_intent(query_text, choices)

    if not chosen:
        raise HTTPException(status_code=400, detail="Invalid choice option selected")

    chosen_copy = dict(chosen)
    chosen_copy["book_id"] = book_id

    new_state = engine.make_choice(uid, chosen_copy)
    if not new_state:
        raise HTTPException(status_code=500, detail="Could not advance game state")

    return _format_game_state_response(uid, book_id, new_state)

class JumpRequest(BaseModel):
    target: str

@app.post("/api/games/{user_id}/{book_id}/jump")
def jump_section(user_id: int, book_id: str, req: JumpRequest, authorization: Optional[str] = Header(None)):
    """Jumps directly to a target section by number or node_id."""
    uid = resolve_user_id(authorization, user_id)
    state = engine.jump_to_node(uid, book_id, req.target)
    if not state:
        raise HTTPException(status_code=404, detail=f"No se encontró la sección '{req.target}' en este libro.")
    return _format_game_state_response(uid, book_id, state)

@app.post("/api/voice/transcribe")
async def transcribe_voice(file: UploadFile = File(...)):
    """Transcribes an uploaded audio file using Whisper STT."""
    try:
        content = await file.read()
        file_ext = Path(file.filename).suffix or ".wav"
        temp_file = temp_dir / f"voice_{os.getpid()}{file_ext}"
        with open(temp_file, "wb") as f:
            f.write(content)

        text = stt_manager.transcribe(temp_file)
        if temp_file.exists():
            temp_file.unlink()

        return {"status": "success", "text": text}
    except Exception as e:
        logger.error(f"STT Error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice transcription failed: {str(e)}")

@app.get("/api/users/{user_id}/settings")
def get_settings(user_id: int, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization, user_id)
    settings = engine.db.get_user_settings(uid)
    return {"user_id": uid, "settings": settings}

@app.put("/api/users/{user_id}/settings")
def update_settings(user_id: int, settings: dict = Body(...), authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization, user_id)
    new_settings = settings.get("settings", settings)
    engine.db.update_user_settings(uid, new_settings)
    return {"user_id": uid, "status": "updated", "settings": new_settings}

@app.get("/api/stats/user/{user_id}")
def get_user_statistics(user_id: int, authorization: Optional[str] = Header(None)):
    """Returns detailed user statistics and book progress breakdown."""
    uid = resolve_user_id(authorization, user_id)
    return engine.db.get_user_stats_detailed(uid)

@app.get("/api/stats/global")
def get_global_statistics(authorization: Optional[str] = Header(None)):
    """Returns platform-wide statistics for admins."""
    require_admin(authorization)
    return engine.db.get_global_stats()

def _format_game_state_response(user_id: int, book_id: str, state: dict) -> dict:
    node = state["current_node"]
    book_dir_url = f"/api/books/{book_id}/asset"

    images_urls = [f"{book_dir_url}/{img}" for img in node.get("images", [])]
    audio_url = f"{book_dir_url}/{node.get('audio')}" if node.get("audio") else None
    audio_options_url = f"{book_dir_url}/{node.get('audio_options')}" if node.get("audio_options") else None

    history = engine.db.get_history(user_id, book_id, limit=100)
    visited_count = len(set(h["to_node_id"] for h in history))
    total_sections = engine.books.get(book_id, {}).get("total_sections", 1)
    progress_pct = min(100, int((visited_count / max(1, total_sections)) * 100))

    return {
        "user_id": user_id,
        "book_id": book_id,
        "book_title": state.get("book_title"),
        "node_id": node.get("id"),
        "display_number": node.get("display_number"),
        "title": node.get("title"),
        "text": node.get("text"),
        "images": images_urls,
        "audio_url": audio_url,
        "audio_options_url": audio_options_url,
        "choices": node.get("choices", []),
        "inventory": state.get("inventory", {}),
        "variables": state.get("variables", {}),
        "progress_percent": progress_pct,
        "history_count": len(history)
    }

# --- Serve PWA Static Files ---
if WEB_DIR.exists():
    @app.get("/")
    def serve_index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
