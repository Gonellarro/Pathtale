from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header

from src.dependencies import (
    engine, login_rate_limiter, RegisterRequest, LoginRequest, resolve_user_id
)

router = APIRouter(prefix="/api", tags=["Auth"])

ENABLE_PUBLIC_REGISTRATION = False  # Single toggle flag: set to True to open public registration

@router.post("/auth/register")
def register(req: RegisterRequest):
    """Registers a new user account."""
    if not ENABLE_PUBLIC_REGISTRATION:
        raise HTTPException(status_code=403, detail="Temporalmente deshabilitado. Solo altas con invitación.")
    try:
        user_info = engine.db.register_user(req.username, req.password, req.first_name)
        return {"status": "success", "user": user_info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/login")
def login(req: LoginRequest, request: Request):
    """Authenticates user and returns session token with Rate Limiting protection."""
    client_ip = request.client.host if (request.client and request.client.host) else "unknown"
    login_rate_limiter.check_rate_limit(client_ip)
    try:
        user_info = engine.db.login_user(req.username, req.password)
        engine.db.log_audit_event(user_info["user_id"], action_type="login", detail="Inicio de sesión")
        return {"status": "success", "user": user_info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    """Logs out user by destroying active session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user = engine.db.get_user_by_token(token)
        if user:
            engine.db.log_audit_event(user["user_id"], action_type="logout", detail="Cierre de sesión")
        engine.db.logout_user(token)
    return {"status": "success"}

@router.get("/auth/me")
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
        "user": None,
        "tier": {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0},
        "stats": {"books_started": 0, "decisions_made": 0}
    }

@router.get("/subscription_tiers")
def get_subscription_tiers(authorization: Optional[str] = Header(None)):
    """Returns list of all available subscription tiers."""
    resolve_user_id(authorization)
    tiers = engine.db.get_all_subscription_tiers()
    return {"tiers": tiers}
