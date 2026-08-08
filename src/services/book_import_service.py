import logging
import shutil
from pathlib import Path
from typing import Callable, Optional

from src.db import Database

logger = logging.getLogger("BookImportService")


class BookImportService:
    """Coordinates the application workflow around normalized EPUBs."""

    def __init__(self, database: Database, reload_books: Callable[[], None]):
        self.database = database
        self.reload_books = reload_books

    def import_book(
        self,
        temp_path: Path,
        target_path: Path,
        *,
        title: str,
        author: str,
        language: str,
        start_node: str,
        tier_id: int,
        narrator_id: Optional[int],
        generate_audios: bool,
        tts_engine: str = "auto",
        voice_name: Optional[str] = "default",
    ) -> Path:
        """Copy an inspected upload and publish its imported book."""
        temp_path = Path(temp_path)
        target_path = Path(target_path)
        if not temp_path.exists():
            raise FileNotFoundError("El archivo temporal ha expirado. Por favor, sube el archivo de nuevo.")

        if not target_path.name.lower().endswith(".epub"):
            raise ValueError("PathTale solo acepta EPUB normalizados.")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_path, target_path)

        from src.importer import EPUBImporter
        importer = EPUBImporter(target_path)

        narrator_info = self.database.get_narrator_by_id(narrator_id) if narrator_id else None
        if narrator_id and not narrator_info:
            raise ValueError(f"El narrador #{narrator_id} no existe o está inactivo.")

        # The narrator record is authoritative for synthesis configuration.
        effective_engine = narrator_info.get("engine_code") if narrator_info else tts_engine
        effective_voice = narrator_info.get("voice_code") if narrator_info else voice_name

        try:
            book_json_path = importer.process(
                generate_audios=generate_audios,
                title=title,
                author=author,
                language=language,
                start_node=start_node,
                tts_engine=effective_engine,
                voice_name=effective_voice,
                tier_id=tier_id,
                narrator_id=narrator_id,
            )
            book_folder = book_json_path.parent
            if narrator_id:
                self.database.update_book_admin(book_folder.name, {"narrator_id": narrator_id})
            self.reload_books()
            return book_folder
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning("Could not remove temporary upload '%s'", temp_path)
