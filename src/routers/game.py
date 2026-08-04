import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Header
from pydantic import BaseModel

from src.dependencies import (
    engine, stt_manager, voice_parser, temp_dir, logger,
    StartGameRequest, ChoiceRequest, resolve_user_id
)

router = APIRouter(prefix="/api", tags=["Game"])

class JumpRequest(BaseModel):
    target: str

def _format_game_state_response(user_id: int, book_id: str, state: dict) -> dict:
    node = state["current_node"]
    book = engine.books.get(book_id, {})
    book_dir_url = f"/api/books/{book_id}/asset"

    images_urls = [f"{book_dir_url}/{img}" for img in node.get("images", [])]
    audio_url = f"{book_dir_url}/{node.get('audio')}" if node.get("audio") else None
    audio_options_url = f"{book_dir_url}/{node.get('audio_options')}" if node.get("audio_options") else None

    cover_image_url = f"{book_dir_url}/{book.get('cover_image')}" if book.get('cover_image') else None
    history = engine.db.get_history(user_id, book_id, limit=100)
    visited_count = len(set(h["to_node_id"] for h in history))
    total_sections = book.get("total_sections", 1)
    progress_pct = min(100, int((visited_count / max(1, total_sections)) * 100))
    narrator_id = book.get("narrator_id")
    narrator = engine.db.get_narrator_by_id(narrator_id) if narrator_id else None

    return {
        "user_id": user_id,
        "book_id": book_id,
        "book_title": state.get("book_title"),
        "book_author": book.get("author"),
        "narrator_name": narrator.get("display_name") if narrator else None,
        "narrator_engine": narrator.get("engine_name") if narrator else None,
        "total_sections": total_sections,
        "node_id": node.get("id"),
        "display_number": node.get("display_number"),
        "title": node.get("title"),
        "text": node.get("text"),
        "text_html": node.get("text_html"),
        "images": images_urls,
        "audio_url": audio_url,
        "cover_image_url": cover_image_url,
        "audio_options_url": audio_options_url,
        "choices": node.get("choices", []),
        "inventory": state.get("inventory", {}),
        "variables": state.get("variables", {}),
        "progress_percent": progress_pct,
        "history_count": len(history)
    }

@router.post("/games")
def start_game(req: StartGameRequest, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
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

@router.get("/games/{user_id}/last_active")
def get_last_active_game(user_id: int, authorization: Optional[str] = Header(None)):
    """Returns the most recently played game session for the user."""
    uid = resolve_user_id(authorization)
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

@router.get("/games/{user_id}/in_progress")
def get_in_progress_games(user_id: int, limit: int = 3, authorization: Optional[str] = Header(None)):
    """Returns top in-progress game sessions for the user."""
    uid = resolve_user_id(authorization)
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

@router.get("/games/{user_id}/{book_id}")
def get_game_state(user_id: int, book_id: str, authorization: Optional[str] = Header(None)):
    """Retrieves current game state for active user session."""
    uid = resolve_user_id(authorization)
    state = engine.get_current_state(uid, book_id)
    if not state:
        state = engine.start_game(uid, book_id)
    return _format_game_state_response(uid, book_id, state)

@router.get("/games/{user_id}/{book_id}/history")
def get_game_history(user_id: int, book_id: str, authorization: Optional[str] = Header(None)):
    """Retrieves decision history for a user and book."""
    uid = resolve_user_id(authorization)
    history = engine.db.get_history(uid, book_id)
    return history

@router.post("/games/{user_id}/{book_id}/choice")
def make_choice(user_id: int, book_id: str, req: ChoiceRequest, authorization: Optional[str] = Header(None)):
    """Submits a choice to advance game state."""
    uid = resolve_user_id(authorization)
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

@router.post("/games/{user_id}/{book_id}/jump")
def jump_section(user_id: int, book_id: str, req: JumpRequest, authorization: Optional[str] = Header(None)):
    """Jumps directly to a target section by number or node_id."""
    uid = resolve_user_id(authorization)
    state = engine.jump_to_node(uid, book_id, req.target)
    if not state:
        raise HTTPException(status_code=404, detail=f"No se encontró la sección '{req.target}' en este libro.")
    return _format_game_state_response(uid, book_id, state)

@router.post("/voice/transcribe")
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
