"""Safe delivery of installed-book and shared audio assets."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import BOOKS_DIR
from src.services.audio_catalog import AudioCatalog, AudioCatalogError

router = APIRouter(prefix="/api", tags=["Catalog"])
audio_catalog = AudioCatalog()


@router.get("/books/{book_id}/asset/{subpath:path}")
def get_book_asset(book_id: str, subpath: str):
    target_dir = (BOOKS_DIR / book_id).resolve()
    asset_path = (target_dir / subpath).resolve()
    if not str(asset_path).startswith(str(target_dir)):
        raise HTTPException(status_code=403, detail="Acceso denegado. Ruta no permitida.")
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return FileResponse(asset_path)


@router.get("/audio-assets/{asset_id}")
def get_audio_asset(asset_id: str):
    try:
        return FileResponse(audio_catalog.get_asset(asset_id)["path"])
    except AudioCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
