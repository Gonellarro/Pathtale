import json
import time
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
from src.importer import EPUBImporter
from src.services.book_audio_service import BookAudioService
from src.services.book_import_service import BookImportService

router = APIRouter(prefix="/api/admin", tags=["Admin Books"])
book_audio_service = BookAudioService(BOOKS_DIR, engine.db)
book_import_service = BookImportService(engine.db, engine._load_installed_books)


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
    db_fields = {"title", "author", "narrator_id", "tier_id", "is_visible", "genre", "series", "volume", "description", "language", "start_node"}
    db_updates = {key: value for key, value in updates.items() if key in db_fields and value is not None}
    if db_updates:
        engine.db.update_book_admin(book_id, db_updates)

    book_folder = BOOKS_DIR / book_id
    json_path = book_folder / "book.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as file:
            book_data = json.load(file)
        book_data.update({key: value for key, value in updates.items() if value is not None})
        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(book_data, file, ensure_ascii=False, indent=2)
    engine._load_installed_books()

    if regenerate:
        try:
            book_audio_service.regenerate(book_id, tts_engine=tts_engine, voice_name=voice_name, language=updates.get("language"), narrator_id=updates.get("narrator_id"))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "message": f"Libro '{book_id}' actualizado correctamente."}


@router.post("/books/{book_id}/cover")
async def upload_book_cover(book_id: str, file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
        raise HTTPException(status_code=400, detail="El archivo de portada debe ser una imagen.")
    book_folder = BOOKS_DIR / book_id
    if not book_folder.exists():
        raise HTTPException(status_code=404, detail=f"No se encontró la carpeta del libro '{book_id}'.")
    images_dir = book_folder / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"custom_cover_{int(time.time())}{Path(file.filename).suffix.lower() or '.jpg'}"
    (images_dir / filename).write_bytes(await file.read())
    relative_path = f"images/{filename}"
    json_path = book_folder / "book.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as source:
            book_data = json.load(source)
        book_data["cover_image"] = relative_path
        with open(json_path, "w", encoding="utf-8") as target:
            json.dump(book_data, target, ensure_ascii=False, indent=2)
    engine.db.update_book_admin(book_id, {"cover_image": relative_path})
    engine._load_installed_books()
    return {"status": "success", "message": f"Portada del libro '{book_id}' actualizada correctamente.", "cover_image": relative_path}


@router.delete("/books/{book_id}")
def delete_book(book_id: str, hard: bool = Query(False), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.delete_book_admin(book_id, hard_delete=hard)
    engine._load_installed_books()
    return {"status": "success", "message": f"Audiolibro '{book_id}' {'eliminado permanentemente' if hard else 'ocultado'} correctamente."}


@router.post("/books/inspect")
async def inspect_book(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="PathTale solo acepta EPUB normalizados.")
    upload_dir = DATA_DIR / "temp" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_file_id = f"{int(time.time())}_{file.filename}"
    temp_path = upload_dir / temp_file_id
    temp_path.write_bytes(await file.read())
    logger.info("Inspecting uploaded EPUB '%s' (temp_id='%s')", file.filename, temp_file_id)
    meta = EPUBImporter(temp_path).inspect()
    if not meta.get("is_normalized"):
        raise HTTPException(status_code=400, detail="El EPUB no cumple el formato normalizado requerido por PathTale.")
    return {"status": "success", "temp_file_id": temp_file_id, "filename": file.filename, "inspection": meta}


@router.post("/books/confirm_import")
def confirm_book_import(req: AdminConfirmBookImportRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    temp_path = DATA_DIR / "temp" / "uploads" / req.temp_file_id
    target_path = INPUT_BOOKS_DIR / Path(req.temp_file_id.split("_", 1)[-1]).name
    try:
        book_folder = book_import_service.import_book(temp_path, target_path, title=req.title, author=req.author, language=req.language, start_node=req.start_node, tier_id=req.tier_id, narrator_id=req.narrator_id, generate_audios=req.generate_audios, tts_engine=req.tts_engine, voice_name=req.voice_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "message": f"Libro '{req.title}' importado correctamente.", "book_id": book_folder.name}


@router.post("/books/upload")
async def upload_book(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="PathTale solo acepta EPUB normalizados.")
    INPUT_BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = INPUT_BOOKS_DIR / Path(file.filename).name
    target_path.write_bytes(await file.read())
    book_folder = EPUBImporter(target_path).process(generate_audios=False)
    engine._load_installed_books()
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
