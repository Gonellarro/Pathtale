from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from config import BOOKS_DIR, DATA_DIR, INPUT_BOOKS_DIR
from src.dependencies import (
    AdminBookUpdateRequest,
    AdminConfirmBookImportRequest,
    engine,
    logger,
    require_admin,
)
from src.services.admin_book_service import AdminBookService
from src.services.audio_job_service import AudioJobService
from src.services.book_upload_service import BookUploadService

router = APIRouter(prefix="/api/admin", tags=["Admin Books"])
book_service = AdminBookService(engine.db, BOOKS_DIR, engine._load_installed_books)
book_uploads = BookUploadService(DATA_DIR / "temp" / "uploads")
audio_jobs = AudioJobService(book_service.audio)


@router.get("/books")
def list_books(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"books": engine.db.get_all_books_admin()}


@router.put("/books/{book_id}")
def update_book(book_id: str, req: AdminBookUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    updates = req.dict(exclude_unset=True)
    regenerate = updates.pop("regenerate_audios", False)
    tts_engine = updates.pop("tts_engine", "auto")
    voice_name = updates.pop("voice_name", None)
    try:
        book_service.update(
            book_id,
            updates,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audio_job = None
    if regenerate:
        audio_job = audio_jobs.start(
            book_id,
            tts_engine=tts_engine,
            voice_name=voice_name,
            language=updates.get("language"),
            narrator_id=updates.get("narrator_id"),
            overwrite=True,
        )
    return {"status": "success", "message": f"Libro '{book_id}' actualizado correctamente.", "audio_job": audio_job}


@router.post("/books/{book_id}/cover")
async def upload_book_cover(book_id: str, file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
        raise HTTPException(status_code=400, detail="El archivo de portada debe ser una imagen.")
    try:
        relative_path = book_service.replace_cover(book_id, file.filename, await file.read())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "success", "message": f"Portada del libro '{book_id}' actualizada correctamente.", "cover_image": relative_path}


@router.delete("/books/{book_id}")
def delete_book(book_id: str, hard: bool = Query(False), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        book_service.delete(book_id, hard=hard)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "message": f"Audiolibro '{book_id}' {'eliminado permanentemente' if hard else 'ocultado'} correctamente.", "hard_deleted": hard}


@router.post("/books/inspect")
async def inspect_book(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        temp_file_id, _, meta = book_uploads.stage_and_inspect(file.filename, await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info("Inspecting uploaded EPUB '%s' (temp_id='%s')", file.filename, temp_file_id)
    return {"status": "success", "temp_file_id": temp_file_id, "filename": file.filename, "inspection": meta}


@router.post("/books/confirm_import")
def confirm_book_import(req: AdminConfirmBookImportRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    temp_path = DATA_DIR / "temp" / "uploads" / req.temp_file_id
    target_path = INPUT_BOOKS_DIR / Path(req.temp_file_id.split("_", 1)[-1]).name
    try:
        book_folder = book_service.imports.import_book(temp_path, target_path, title=req.title, author=req.author, language=req.language, start_node=req.start_node, tier_id=req.tier_id, narrator_id=req.narrator_id, generate_audios=False, tts_engine=req.tts_engine, voice_name=req.voice_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audio_job = None
    if req.generate_audios:
        audio_job = audio_jobs.start(
            book_folder.name,
            tts_engine=req.tts_engine,
            voice_name=req.voice_name,
            language=req.language,
            narrator_id=req.narrator_id,
        )
    return {"status": "success", "message": f"Libro '{req.title}' importado correctamente.", "book_id": book_folder.name, "audio_job": audio_job}


@router.get("/books/audio-jobs/{job_id}")
def get_audio_job(job_id: str, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    job = audio_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="No se encontró el trabajo de generación de audio.")
    return {"job": job}


@router.post("/books/upload")
async def upload_book(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        _, temp_path, inspection = book_uploads.stage_and_inspect(file.filename, await file.read())
        target_path = INPUT_BOOKS_DIR / Path(file.filename).name
        book_folder = book_service.imports.import_book(
            temp_path,
            target_path,
            title=inspection["suggested_title"],
            author=inspection["suggested_author"],
            language=inspection["suggested_language"],
            start_node=inspection["suggested_start_node"],
            tier_id=1,
            narrator_id=None,
            generate_audios=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    book_data = engine.books.get(book_folder.name, {})
    return {
        "status": "success",
        "message": f"Libro '{file.filename}' importado correctamente.",
        "book_folder": str(book_folder.name),
        "book": {
            "book_id": book_folder.name,
            "title": book_data.get("title", file.filename),
            "author": book_data.get("author", "Desconocido"),
            "language": book_data.get("language", "es"),
            "start_node": book_data.get("start_node", "sec_001"),
            "total_sections": book_data.get("total_sections", 1),
            "narrator_id": book_data.get("narrator_id", 1),
            "tier_id": book_data.get("tier_id", 1),
        },
    }
