"""Filesystem persistence for installed books.

Keeping the book directory format here prevents HTTP routes and orchestration
services from knowing how ``book.json`` and its assets are stored on disk.
"""

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict


class BookFileStore:
    def __init__(self, books_dir: Path):
        self.books_dir = Path(books_dir)

    def book_dir(self, book_id: str) -> Path:
        return self.books_dir / book_id

    def read_document(self, book_id: str) -> Dict[str, Any]:
        path = self.book_dir(book_id) / "book.json"
        if not path.exists():
            raise FileNotFoundError(f"No se encontró book.json para el libro '{book_id}'.")
        with path.open("r", encoding="utf-8") as source:
            return json.load(source)

    def update_document(self, book_id: str, updates: Dict[str, Any]) -> None:
        path = self.book_dir(book_id) / "book.json"
        if not path.exists():
            return
        document = self.read_document(book_id)
        document.update({key: value for key, value in updates.items() if value is not None})
        with path.open("w", encoding="utf-8") as target:
            json.dump(document, target, ensure_ascii=False, indent=2)

    def store_cover(self, book_id: str, original_filename: str, content: bytes) -> str:
        book_dir = self.book_dir(book_id)
        if not book_dir.exists():
            raise FileNotFoundError(f"No se encontró la carpeta del libro '{book_id}'.")

        suffix = Path(original_filename).suffix.lower() or ".jpg"
        images_dir = book_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        filename = f"custom_cover_{int(time.time())}{suffix}"
        (images_dir / filename).write_bytes(content)
        relative_path = f"images/{filename}"
        self.update_document(book_id, {"cover_image": relative_path})
        return relative_path

    def remove_book(self, book_id: str) -> None:
        book_dir = self.book_dir(book_id)
        if book_dir.exists():
            shutil.rmtree(book_dir)
