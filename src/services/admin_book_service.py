"""Application service for administrative book operations."""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.services.book_audio_service import BookAudioService
from src.services.book_file_store import BookFileStore
from src.services.book_import_service import BookImportService


class AdminBookService:
    """Coordinates book metadata, assets and lifecycle outside HTTP routes."""

    _DB_FIELDS = {
        "title", "author", "narrator_id", "tier_id", "is_visible", "genre",
        "series", "volume", "description", "language", "start_node",
    }

    def __init__(
        self,
        database,
        books_dir: Path,
        reload_books: Callable[[], None],
    ):
        self.database = database
        self.reload_books = reload_books
        self.files = BookFileStore(books_dir)
        self.audio = BookAudioService(books_dir, database)
        self.imports = BookImportService(database, reload_books)

    def update(
        self,
        book_id: str,
        updates: Dict[str, Any],
        *,
        regenerate_audios: bool = False,
        tts_engine: str = "auto",
        voice_name: Optional[str] = None,
    ) -> None:
        db_updates = {
            key: value for key, value in updates.items()
            if key in self._DB_FIELDS and value is not None
        }
        if db_updates:
            self.database.update_book_admin(book_id, db_updates)
        self.files.update_document(book_id, updates)
        self.reload_books()

        if regenerate_audios:
            self.audio.regenerate(
                book_id,
                tts_engine=tts_engine,
                voice_name=voice_name,
                language=updates.get("language"),
                narrator_id=updates.get("narrator_id"),
            )

    def replace_cover(self, book_id: str, filename: str, content: bytes) -> str:
        relative_path = self.files.store_cover(book_id, filename, content)
        self.database.update_book_admin(book_id, {"cover_image": relative_path})
        self.reload_books()
        return relative_path

    def delete(self, book_id: str, *, hard: bool = False) -> None:
        book = self.database.get_book_by_id(book_id)
        if not book:
            raise FileNotFoundError("Libro no encontrado")
        if hard and book.get("is_visible") != 0:
            raise ValueError("Solo se puede borrar definitivamente un libro que ya está oculto")

        self.database.delete_book_admin(book_id, hard_delete=hard)
        if hard:
            self.files.remove_book(book_id)
        self.reload_books()
