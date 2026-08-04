from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Header

from config import BOOKS_DIR
from src.dependencies import (
    engine, logger, require_admin,
    AdminUserCreateRequest, AdminUserUpdateRequest,
    AdminNarratorCreateRequest, AdminNarratorUpdateRequest,
    AdminUserSubscriptionRequest
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/roles")
def admin_list_roles(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"roles": engine.db.get_all_roles()}

@router.get("/users")
def admin_list_users(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"users": engine.db.get_all_users_admin()}

@router.post("/users")
def admin_create_user(req: AdminUserCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        user_info = engine.db.create_user_admin(req.username, req.password, req.first_name, req.role or "user")
        return {"status": "success", "user": user_info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/users/{user_id}")
def admin_update_user(user_id: int, req: AdminUserUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.update_user_admin(user_id, first_name=req.first_name, role=req.role, password=req.password, tier_id=req.tier_id)
    return {"status": "success", "message": f"Usuario {user_id} actualizado."}

@router.delete("/users/{user_id}")
def admin_delete_user(user_id: int, hard: bool = Query(False), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        engine.db.delete_user_admin(user_id, hard_delete=hard)
        msg = f"Usuario #{user_id} eliminado permanentemente." if hard else f"Usuario #{user_id} desactivado (Soft Delete)."
        return {"status": "success", "message": msg}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/users/{user_id}/subscription")
def admin_assign_user_subscription(user_id: int, req: AdminUserSubscriptionRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.assign_user_subscription(user_id, req.tier_id, req.duration_days)
    return {"status": "success", "message": f"Suscripción del usuario #{user_id} actualizada correctamente."}

@router.get("/tts_engines")
def admin_list_tts_engines(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"engines": engine.db.get_all_tts_engines()}

@router.get("/narrators")
def admin_list_narrators(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"narrators": engine.db.get_narrators_stats()}

@router.post("/narrators")
def admin_create_narrator(req: AdminNarratorCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    narrator_info = engine.db.create_narrator_admin(
        name=req.name,
        display_name=req.display_name,
        engine_id=req.engine_id or 1,
        voice_code=req.voice_code or "default",
        language=req.language or "es",
        gender=req.gender or "male",
        specialty=req.specialty,
        avatar_url=req.avatar_url,
        download_url=req.download_url,
        model_filename=req.model_filename,
        bio=req.bio
    )
    return {"status": "success", "narrator": narrator_info}

@router.put("/narrators/{narrator_id}")
def admin_update_narrator(narrator_id: int, req: AdminNarratorUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.update_narrator_admin(
        narrator_id,
        display_name=req.display_name,
        engine_id=req.engine_id,
        voice_code=req.voice_code,
        language=req.language,
        gender=req.gender,
        specialty=req.specialty,
        avatar_url=req.avatar_url,
        download_url=req.download_url,
        model_filename=req.model_filename,
        bio=req.bio
    )
    return {"status": "success", "message": f"Narrador #{narrator_id} actualizado."}

@router.post("/narrators/{narrator_id}/download")
def admin_download_narrator_model(narrator_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    narrator = engine.db.get_narrator_by_id(narrator_id)
    if not narrator:
        raise HTTPException(status_code=404, detail="Narrador no encontrado.")

    if not narrator.get("download_url"):
        raise HTTPException(status_code=400, detail="Este narrador no requiere descarga o no tiene URL configurada.")

    model_filename = narrator.get("model_filename") or f"{narrator.get('voice_code')}.onnx"
    models_dir = BOOKS_DIR.parent / "models" / "piper"
    target_path = models_dir / model_filename
    from src.tts import TTSManager
    ok = TTSManager()._ensure_model_exists(str(target_path), custom_download_url=narrator.get("download_url"))
    if not ok:
        raise HTTPException(status_code=500, detail=f"No se pudo descargar el modelo desde {narrator.get('download_url')}.")

    return {"status": "success", "message": f"Modelo '{model_filename}' descargado correctamente en disco."}

@router.delete("/narrators/{narrator_id}")
def admin_delete_narrator(narrator_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        engine.db.delete_narrator_admin(narrator_id)
        return {"status": "success", "message": f"Narrador #{narrator_id} eliminado."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/logs")
def admin_list_logs(limit: int = Query(50), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    logs = engine.db.get_reading_logs_admin(limit=limit)
    return {"logs": logs}
