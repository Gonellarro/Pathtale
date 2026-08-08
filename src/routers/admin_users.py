"""Administrative user, role and subscription routes."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from src.dependencies import AdminUserCreateRequest, AdminUserSubscriptionRequest, AdminUserUpdateRequest, engine, require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin Users"])


@router.get("/roles")
def list_roles(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"roles": engine.db.get_all_roles()}


@router.get("/users")
def list_users(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"users": engine.db.get_all_users_admin()}


@router.post("/users")
def create_user(req: AdminUserCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        user = engine.db.create_user_admin(req.username, req.password, req.first_name, req.role or "user", req.tier_id or 1)
        return {"status": "success", "user": user}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/users/{user_id}")
def update_user(user_id: int, req: AdminUserUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.update_user_admin(user_id, first_name=req.first_name, role=req.role, password=req.password, tier_id=req.tier_id)
    return {"status": "success", "message": f"Usuario {user_id} actualizado."}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, hard: bool = Query(False), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        engine.db.delete_user_admin(user_id, hard_delete=hard)
        message = f"Usuario #{user_id} eliminado permanentemente." if hard else f"Usuario #{user_id} desactivado (Soft Delete)."
        return {"status": "success", "message": message}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/users/{user_id}/subscription")
def assign_subscription(user_id: int, req: AdminUserSubscriptionRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.assign_user_subscription(user_id, req.tier_id, req.duration_days)
    return {"status": "success", "message": f"Suscripción del usuario #{user_id} actualizada correctamente."}
