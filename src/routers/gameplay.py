"""HTTP routes that transition or retrieve the interactive game state."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from src.api_models import ChoiceRequest, JumpRequest, StartGameRequest
from src.dependencies import engine, resolve_user_id
from src.services.game_state_presenter import GameStatePresenter

router = APIRouter(prefix="/api", tags=["Game"])
presenter = GameStatePresenter(engine)


@router.post("/games")
def start_game(req: StartGameRequest, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    user_tier = engine.db.get_user_active_tier(uid)
    book_tier = engine.db.get_book_tier(req.book_id)
    if book_tier.get("is_visible") == 0:
        token = authorization.split(" ")[1] if authorization and authorization.startswith("Bearer ") else None
        user = engine.db.get_user_by_token(token) if token else None
        if not (user and user.get("role_name") == "admin"):
            raise HTTPException(status_code=403, detail="Este audiolibro no está disponible actualmente.")
    if book_tier["level"] > user_tier["level"]:
        raise HTTPException(
            status_code=403,
            detail=f"Este audiolibro requiere la membresía '{book_tier['name']}'. Tu nivel actual es '{user_tier['name']}'.",
        )
    state = engine.start_game(uid, req.book_id)
    if not state:
        raise HTTPException(status_code=400, detail="Could not start game session")
    return presenter.format(uid, req.book_id, state)


@router.get("/games/{user_id}/{book_id}")
def get_game_state(user_id: int, book_id: str, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    state = engine.get_current_state(uid, book_id)
    if not state:
        state = engine.start_game(uid, book_id)
    else:
        engine.db.touch_savegame(uid, book_id)
    return presenter.format(uid, book_id, state)


@router.post("/games/{user_id}/{book_id}/choice")
def make_choice(user_id: int, book_id: str, req: ChoiceRequest, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    state = engine.get_current_state(uid, book_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game session not found")
    choices = state["current_node"]["choices"]
    chosen = None
    if req.choice_id is not None and str(req.choice_id).strip():
        chosen = next((choice for choice in choices if str(choice.get("choice_id")) == str(req.choice_id)), None)
    if not chosen and req.target_node:
        chosen = next((choice for choice in choices if str(choice.get("target_node")) == str(req.target_node)), None)
    if not chosen and (req.text or req.text_query):
        from src.dependencies import voice_parser
        chosen = voice_parser.parse_intent(req.text or req.text_query, choices)
    if not chosen:
        raise HTTPException(status_code=400, detail="Invalid choice option selected")
    chosen_copy = {**chosen, "book_id": book_id}
    new_state = engine.make_choice(uid, chosen_copy)
    if not new_state:
        raise HTTPException(status_code=500, detail="Could not advance game state")
    return presenter.format(uid, book_id, new_state)


@router.post("/games/{user_id}/{book_id}/jump")
def jump_section(user_id: int, book_id: str, req: JumpRequest, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    state = engine.jump_to_node(uid, book_id, req.target)
    if not state:
        raise HTTPException(status_code=404, detail=f"No se encontró la sección '{req.target}' en este libro.")
    return presenter.format(uid, book_id, state)
