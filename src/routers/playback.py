"""Playback bookmark API, independent from game navigation."""

from typing import Optional

from fastapi import APIRouter, Header

from src.api_models import PlaybackPositionRequest
from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Playback"])


@router.put("/games/{user_id}/{book_id}/playback-position")
def save_playback_position(
    user_id: int,
    book_id: str,
    req: PlaybackPositionRequest,
    authorization: Optional[str] = Header(None),
):
    saved = engine.db.save_playback_position(
        resolve_user_id(authorization), book_id, req.node_id, req.position_seconds, req.captured_at_ms,
    )
    return {"saved": saved}
