"""Temporary upload staging and EPUB inspection for admin imports."""

import time
from pathlib import Path
from typing import Any, Dict, Tuple

from src.importer import EPUBImporter


class BookUploadService:
    def __init__(self, uploads_dir: Path):
        self.uploads_dir = Path(uploads_dir)

    def stage_normalized_epub(self, filename: str, content: bytes) -> Tuple[str, Path]:
        if not filename.lower().endswith(".epub"):
            raise ValueError("PathTale solo acepta EPUB normalizados.")
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        temp_file_id = f"{int(time.time())}_{safe_name}"
        temp_path = self.uploads_dir / temp_file_id
        temp_path.write_bytes(content)
        return temp_file_id, temp_path

    def inspect(self, temp_path: Path) -> Dict[str, Any]:
        inspection = EPUBImporter(temp_path).inspect()
        if not inspection.get("is_normalized"):
            raise ValueError("El EPUB no cumple el formato normalizado requerido por PathTale.")
        return inspection

    def stage_and_inspect(self, filename: str, content: bytes) -> Tuple[str, Path, Dict[str, Any]]:
        temp_file_id, temp_path = self.stage_normalized_epub(filename, content)
        try:
            return temp_file_id, temp_path, self.inspect(temp_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
