"""Administrative narrator and TTS model routes."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from config import BOOKS_DIR
from src.dependencies import AdminNarratorCreateRequest, AdminNarratorUpdateRequest, engine, require_admin
from src.services.narrator_model_service import NarratorModelService

router = APIRouter(prefix="/api/admin", tags=["Admin Narrators"])
models = NarratorModelService(BOOKS_DIR.parent / "models" / "piper")


@router.get("/tts_engines")
def list_tts_engines(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"engines": engine.db.get_all_tts_engines()}


@router.get("/narrators")
def list_narrators(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"narrators": engine.db.get_narrators_stats()}


@router.post("/narrators")
def create_narrator(req: AdminNarratorCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    narrator = engine.db.create_narrator_admin(
        name=req.name, display_name=req.display_name, engine_id=req.engine_id or 1,
        voice_code=req.voice_code or "default", language=req.language or "es", gender=req.gender or "male",
        specialty=req.specialty, avatar_url=req.avatar_url, download_url=req.download_url,
        model_filename=req.model_filename, bio=req.bio,
    )
    return {"status": "success", "narrator": narrator}


@router.put("/narrators/{narrator_id}")
def update_narrator(narrator_id: int, req: AdminNarratorUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.update_narrator_admin(narrator_id, display_name=req.display_name, engine_id=req.engine_id,
                                    voice_code=req.voice_code, language=req.language, gender=req.gender,
                                    specialty=req.specialty, avatar_url=req.avatar_url,
                                    download_url=req.download_url, model_filename=req.model_filename, bio=req.bio)
    return {"status": "success", "message": f"Narrador #{narrator_id} actualizado."}


@router.post("/narrators/{narrator_id}/download")
def download_narrator_model(narrator_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    narrator = engine.db.get_narrator_by_id(narrator_id)
    if not narrator:
        raise HTTPException(status_code=404, detail="Narrador no encontrado.")
    try:
        filename = models.download(narrator)
        return {"status": "success", "message": f"Modelo '{filename}' descargado correctamente en disco."}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/narrators/{narrator_id}")
def delete_narrator(narrator_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        engine.db.delete_narrator_admin(narrator_id)
        return {"status": "success", "message": f"Narrador #{narrator_id} eliminado."}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
