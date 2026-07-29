import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
    choice_id: Optional[int] = None
    target_node: Optional[str] = None
    text: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    first_name: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Helper to resolve user_id from Authorization Bearer header or fallback
def resolve_user_id(authorization: Optional[str] = Header(None), query_user_id: Optional[int] = None) -> int:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user = engine.db.get_user_by_token(token)
        if user:
            return user["user_id"]
    return query_user_id or 1

# --- Authentication Endpoints ---

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    """Registers a new user account."""
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
    """Returns profile and statistics for currently authenticated user."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user = engine.db.get_user_by_token(token)
        if user:
            stats = engine.db.get_user_stats(user["user_id"])
            return {
                "authenticated": True,
                "user": user,
                "stats": stats
            }
    return {
        "authenticated": False,
        "user": {"user_id": 1, "username": "invitado", "first_name": "Invitado", "settings": {}},
        "stats": {"books_started": 0, "decisions_made": 0}
    }

# --- REST API Game Endpoints ---

@app.get("/api/tags")
def get_tags():
    """Returns top category/series tags for filtering."""
    tags = engine.db.get_top_tags(limit=5)
    return {"tags": tags}

@app.get("/api/books")
def list_books(
    authorization: Optional[str] = Header(None),
    user_id: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    tag: Optional[str] = Query(None)
):
    """Returns a list of imported books with rich metadata and user progress status."""
    current_uid = resolve_user_id(authorization, user_id)
    books = engine.list_books()
    result = []
    
    for b_summary in books:
        b_id = b_summary["book_id"]
        full_data = engine.books.get(b_id, {})
        
        genre = full_data.get("genre", "Ficción Interactiva")
        series = full_data.get("series", "")
        
        # Tag filtering if specified
        if tag and tag.lower() != "todos":
            tag_lower = tag.lower()
            matches_tag = (
                tag_lower in genre.lower() or
                tag_lower in series.lower() or
                (tag_lower == "en curso" and engine.db.get_savegame(current_uid, b_id))
            )
            if not matches_tag:
                continue

        progress_pct = 0
        savegame = engine.db.get_savegame(current_uid, b_id)
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
            "rating": 4.8
        })

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

@app.get("/api/books/{book_id}/asset/{subpath:path}")
def get_book_asset(book_id: str, subpath: str):
    """Serves static assets (images and audio files) for a given book."""
    asset_path = BOOKS_DIR / book_id / subpath
    if not asset_path.exists() or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return FileResponse(asset_path)

@app.post("/api/games")
def start_game(req: StartGameRequest, authorization: Optional[str] = Header(None)):
    """Starts or resets a game session for a user and book."""
    uid = resolve_user_id(authorization, req.user_id)
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

@app.post("/api/games/{user_id}/{book_id}/choice")
def make_choice(user_id: int, book_id: str, req: ChoiceRequest, authorization: Optional[str] = Header(None)):
    """Submits a choice to advance game state."""
    uid = resolve_user_id(authorization, user_id)
    state = engine.get_current_state(uid, book_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game session not found")

    choices = state["current_node"]["choices"]
    chosen = None

    if req.choice_id:
        chosen = next((c for c in choices if c["choice_id"] == req.choice_id), None)
    elif req.target_node:
        chosen = next((c for c in choices if c["target_node"] == req.target_node), None)
    elif req.text:
        chosen = voice_parser.parse_intent(req.text, choices)

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
