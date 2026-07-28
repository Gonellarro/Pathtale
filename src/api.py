import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Body
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
    title="Motor Narrativo de Librojuegos API",
    description="REST API para alimentar PWA, Móvil, Telegram y otras interfaces de ficción interactiva.",
    version="0.9.0"
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
    user_id: int = 1
    book_id: str

class ChoiceRequest(BaseModel):
    choice_id: Optional[int] = None
    target_node: Optional[str] = None
    text: Optional[str] = None

# --- REST API Endpoints ---

@app.get("/api/books")
def list_books(user_id: Optional[int] = Query(None)):
    """Returns a list of all imported books with rich metadata and game progress."""
    books = engine.list_books()
    result = []
    for b_summary in books:
        b_id = b_summary["book_id"]
        full_data = engine.books.get(b_id, {})
        
        progress_pct = 0
        savegame = None
        if user_id:
            savegame = engine.db.get_savegame(user_id, b_id)
            if savegame:
                history = engine.db.get_history(user_id, b_id, limit=500)
                visited_count = len(set(h["to_node_id"] for h in history))
                total_sections = full_data.get("total_sections", 1)
                progress_pct = min(100, int((visited_count / max(1, total_sections)) * 100))

        result.append({
            "book_id": b_id,
            "title": full_data.get("title", b_id),
            "author": full_data.get("author", "Desconocido"),
            "publisher": full_data.get("publisher", "Desconocido"),
            "year": full_data.get("year", "2026"),
            "language": full_data.get("language", "es"),
            "description": full_data.get("description", ""),
            "isbn": full_data.get("isbn", ""),
            "genre": full_data.get("genre", "Ficción Interactiva"),
            "series": full_data.get("series", ""),
            "volume": full_data.get("volume", 1),
            "estimated_duration": full_data.get("estimated_duration", "30 minutos"),
            "cover_image_url": f"/api/books/{b_id}/asset/{full_data.get('cover_image')}" if full_data.get("cover_image") else None,
            "total_sections": full_data.get("total_sections", 0),
            "start_node": full_data.get("start_node", "sec_002"),
            "features": full_data.get("features", {}),
            "has_savegame": bool(savegame),
            "progress_percent": progress_pct
        })
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

    # Find matching EPUB file in Libros/
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
def start_game(req: StartGameRequest):
    """Starts or resets a game session for a user and book."""
    state = engine.start_game(req.user_id, req.book_id)
    if not state:
        raise HTTPException(status_code=400, detail="Could not start game session")
    return _format_game_state_response(req.user_id, req.book_id, state)

@app.get("/api/games/{user_id}/{book_id}")
def get_game_state(user_id: int, book_id: str):
    """Retrieves current game state for active user session."""
    state = engine.get_current_state(user_id, book_id)
    if not state:
        state = engine.start_game(user_id, book_id)
    return _format_game_state_response(user_id, book_id, state)

@app.post("/api/games/{user_id}/{book_id}/choice")
def make_choice(user_id: int, book_id: str, req: ChoiceRequest):
    """Submits a choice to advance game state."""
    state = engine.get_current_state(user_id, book_id)
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

    chosen["book_id"] = book_id
    new_state = engine.make_choice(user_id, chosen)
    return _format_game_state_response(user_id, book_id, new_state)

@app.post("/api/games/{user_id}/{book_id}/voice")
async def process_voice_input(user_id: int, book_id: str, audio: UploadFile = File(...)):
    """Uploads voice recording (.webm, .ogg, .wav), transcribes via Whisper, matches choice and advances state."""
    state = engine.get_current_state(user_id, book_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game session not found")

    choices = state["current_node"]["choices"]
    
    file_ext = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_file = temp_dir / f"voice_{user_id}_{book_id}{file_ext}"
    with open(temp_file, "wb") as dst:
        content = await audio.read()
        dst.write(content)

    transcription = stt_manager.transcribe(temp_file)
    if temp_file.exists():
        temp_file.unlink()

    if not transcription:
        return JSONResponse(status_code=422, content={
            "matched": False,
            "transcription": "",
            "message": "No se pudo interpretar el audio."
        })

    chosen = voice_parser.parse_intent(transcription, choices)
    if not chosen:
        return JSONResponse(status_code=200, content={
            "matched": False,
            "transcription": transcription,
            "message": f"Escuché: '{transcription}', pero no coincide con ninguna opción."
        })

    chosen["book_id"] = book_id
    new_state = engine.make_choice(user_id, chosen)
    res = _format_game_state_response(user_id, book_id, new_state)
    res["matched"] = True
    res["transcription"] = transcription
    return res

@app.get("/api/games/{user_id}/{book_id}/history")
def get_game_history(user_id: int, book_id: str):
    """Returns decision history timeline for the player session."""
    history = engine.db.get_history(user_id, book_id, limit=100)
    return {"history": history}

@app.get("/api/users/{user_id}/settings")
def get_user_settings(user_id: int):
    """Returns stored user preferences."""
    settings = engine.db.get_user_settings(user_id)
    return {"user_id": user_id, "settings": settings}

@app.put("/api/users/{user_id}/settings")
def update_user_settings(user_id: int, req: Dict[str, Any] = Body(...)):
    """Updates stored user preferences."""
    settings = req.get("settings", req)
    engine.db.update_user_settings(user_id, settings)
    return {"status": "success", "settings": settings}

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

    app.mount("/", StaticFiles(directory=str(WEB_DIR)), name="web")
