import time
import json
import shutil
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Header

from config import BOOKS_DIR, DATA_DIR, INPUT_BOOKS_DIR
from src.dependencies import (
    engine, logger, require_admin,
    AdminUserCreateRequest, AdminUserUpdateRequest, AdminConfirmBookImportRequest,
    AdminNarratorCreateRequest, AdminNarratorUpdateRequest, AdminBookUpdateRequest,
    AdminRegenerateAudiosRequest, AdminUserSubscriptionRequest
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

def _internal_regenerate_audios(book_id: str, tts_engine: str = "auto", voice_name: Optional[str] = None, language: Optional[str] = None):
    book_folder = BOOKS_DIR / book_id
    json_path = book_folder / "book.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"No se encontró book.json para el libro '{book_id}'.")

    with open(json_path, "r", encoding="utf-8") as f:
        b_data = json.load(f)

    final_lang = (language or b_data.get("language") or "es").lower()[:2]
    nodes = b_data.get("nodes", {})
    from src.tts import TTSManager
    tts_mgr = TTSManager()

    audios_dir = book_folder / "audios"
    audios_dir.mkdir(exist_ok=True)
    for mp3_file in audios_dir.glob("*.mp3"):
        try: mp3_file.unlink()
        except Exception: pass

    logger.info(f"🎙️ Regenerating audios for '{book_id}' ({len(nodes)} nodes, engine='{tts_engine}', voice='{voice_name}', lang='{final_lang}')...")
    for n_id, n_data in nodes.items():
        audio_path = book_folder / n_data["audio"]
        tts_parts = []
        if n_data.get('title'):
            tts_parts.append(n_data['title'])
        if n_data.get('text'):
            tts_parts.append(n_data['text'])
        if tts_parts:
            tts_text = "\n\n".join(tts_parts)
            tts_mgr.generate_audio(tts_text, audio_path, language=final_lang, tts_engine=tts_engine, voice_name=voice_name)

        if n_data.get("audio_options"):
            audio_opt_path = book_folder / n_data["audio_options"]
            choices = n_data.get('choices', [])
            if choices:
                opt_parts = ["¿Qué deseas hacer?" if final_lang == "es" else "What do you want to do?"]
                for c in choices:
                    prefix = "Opción" if final_lang == "es" else "Option"
                    opt_parts.append(f"{prefix} {c['choice_id']}: {c['text']}.")
                opt_text = "\n\n".join(opt_parts)
                tts_mgr.generate_audio(opt_text, audio_opt_path, language=final_lang, tts_engine=tts_engine, voice_name=voice_name)

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

@router.get("/narrators")
def admin_list_narrators(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"narrators": engine.db.get_narrators_stats()}

@router.post("/narrators")
def admin_create_narrator(req: AdminNarratorCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    narrator_info = engine.db.create_narrator_admin(req.name, req.display_name, req.specialty, req.avatar_url, req.bio)
    return {"status": "success", "narrator": narrator_info}

@router.put("/narrators/{narrator_id}")
def admin_update_narrator(narrator_id: int, req: AdminNarratorUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.update_narrator_admin(narrator_id, req.display_name, req.specialty, req.avatar_url, req.bio)
    return {"status": "success", "message": f"Narrador {narrator_id} actualizado."}

@router.delete("/narrators/{narrator_id}")
def admin_delete_narrator(narrator_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    try:
        engine.db.delete_narrator_admin(narrator_id)
        return {"status": "success", "message": f"Narrador {narrator_id} eliminado."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/books")
def admin_list_books(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"books": engine.db.get_all_books_admin()}

@router.put("/books/{book_id}")
def admin_update_book(book_id: str, req: AdminBookUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    updates = req.dict(exclude_unset=True)
    should_regenerate = updates.pop("regenerate_audios", False)
    tts_engine = updates.pop("tts_engine", "auto")
    voice_name = updates.pop("voice_name", None)

    db_fields = {"title", "author", "narrator_id", "tier_id", "is_visible", "genre", "series", "volume", "description", "language", "start_node"}
    db_updates = {k: v for k, v in updates.items() if k in db_fields and v is not None}
    if db_updates:
        engine.db.update_book_admin(book_id, db_updates)

    book_folder = BOOKS_DIR / book_id
    json_path = book_folder / "book.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            b_json = json.load(f)
        for k, v in updates.items():
            if v is not None:
                b_json[k] = v
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(b_json, f, ensure_ascii=False, indent=2)

    engine._load_installed_books()

    if should_regenerate:
        _internal_regenerate_audios(book_id, tts_engine=tts_engine, voice_name=voice_name, language=updates.get("language"))

    return {"status": "success", "message": f"Libro '{book_id}' actualizado correctamente."}

@router.delete("/books/{book_id}")
def admin_delete_book(book_id: str, hard: bool = Query(False), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    engine.db.delete_book_admin(book_id, hard_delete=hard)
    engine._load_installed_books()
    msg = f"Audiolibro '{book_id}' eliminado permanentemente." if hard else f"Audiolibro '{book_id}' ocultado (Soft Delete)."
    return {"status": "success", "message": msg}

@router.post("/books/inspect")
async def admin_inspect_book(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".epub") or filename_lower.endswith(".pdf")):
        raise HTTPException(status_code=400, detail="El archivo debe ser de tipo .epub o .pdf")

    temp_uploads_dir = DATA_DIR / "temp" / "uploads"
    temp_uploads_dir.mkdir(parents=True, exist_ok=True)
    temp_file_id = f"{int(time.time())}_{file.filename}"
    temp_path = temp_uploads_dir / temp_file_id

    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    logger.info(f"🔍 Inspecting uploaded file '{file.filename}' (temp_id='{temp_file_id}')...")
    if filename_lower.endswith(".pdf"):
        from src.pdf_importer import PDFImporter
        importer = PDFImporter(temp_path)
        meta = importer.inspect()
    else:
        from src.importer import EPUBImporter
        importer = EPUBImporter(temp_path)
        meta = importer.inspect()

    return {
        "status": "success",
        "temp_file_id": temp_file_id,
        "filename": file.filename,
        "inspection": meta
    }

@router.post("/books/confirm_import")
def admin_confirm_book_import(req: AdminConfirmBookImportRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    temp_path = DATA_DIR / "temp" / "uploads" / req.temp_file_id
    if not temp_path.exists():
        raise HTTPException(status_code=404, detail="El archivo temporal ha expirado. Por favor, sube el archivo de nuevo.")

    target_filename = req.temp_file_id.split("_", 1)[-1]
    target_path = INPUT_BOOKS_DIR / target_filename
    shutil.copy(temp_path, target_path)

    filename_lower = target_path.name.lower()
    if filename_lower.endswith(".pdf"):
        from src.pdf_importer import PDFImporter
        importer = PDFImporter(target_path)
    else:
        from src.importer import EPUBImporter
        importer = EPUBImporter(target_path)

    book_folder = importer.process(
        generate_audios=req.generate_audios,
        title=req.title,
        author=req.author,
        language=req.language,
        start_node=req.start_node,
        tts_engine=req.tts_engine,
        voice_name=req.voice_name,
        tier_id=req.tier_id
    )

    engine._load_installed_books()

    try: temp_path.unlink()
    except Exception: pass

    return {
        "status": "success",
        "message": f"Libro '{req.title}' importado correctamente.",
        "book_id": book_folder.name
    }

@router.post("/books/upload")
async def admin_upload_book(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".epub") or filename_lower.endswith(".pdf")):
        raise HTTPException(status_code=400, detail="El archivo debe ser de tipo .epub o .pdf")

    from src.importer import EPUBImporter
    from src.pdf_importer import PDFImporter

    INPUT_BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = INPUT_BOOKS_DIR / file.filename

    with open(target_path, "wb") as f:
        content = await file.read()
        f.write(content)

    logger.info(f"📖 Web Upload received: '{file.filename}'. Starting import pipeline...")
    if filename_lower.endswith(".pdf"):
        importer = PDFImporter(target_path)
    else:
        importer = EPUBImporter(target_path)

    book_folder = importer.process(generate_audios=True)
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
            "tier_id": book_data.get("tier_id", 1)
        }
    }

@router.get("/logs")
def admin_list_logs(limit: int = Query(50), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    logs = engine.db.get_reading_logs_admin(limit=limit)
    return {"logs": logs}
