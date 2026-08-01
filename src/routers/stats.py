from typing import Optional
from fastapi import APIRouter, Header, Body
from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Stats"])

@router.get("/users/{user_id}/settings")
def get_settings(user_id: int, authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    settings = engine.db.get_user_settings(uid)
    return {"user_id": uid, "settings": settings}

@router.put("/users/{user_id}/settings")
def update_settings(user_id: int, settings: dict = Body(...), authorization: Optional[str] = Header(None)):
    uid = resolve_user_id(authorization)
    new_settings = settings.get("settings", settings)
    engine.db.update_user_settings(uid, new_settings)
    return {"user_id": uid, "status": "updated", "settings": new_settings}

@router.get("/stats/user/{user_id}")
def get_user_statistics(user_id: str, authorization: Optional[str] = Header(None)):
    """Returns detailed user statistics and book progress breakdown."""
    uid = resolve_user_id(authorization)
    return engine.db.get_user_stats_detailed(uid)

@router.get("/stats/global")
def get_global_statistics(authorization: Optional[str] = Header(None)):
    """Returns platform-wide statistics for the community."""
    return engine.db.get_global_stats()
