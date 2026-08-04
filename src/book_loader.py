import json
import logging
import re
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("BookLoader")


class InstalledBookLoader:
    """Loads canonical book.json files and synchronizes their catalog records."""

    def __init__(self, books_dir: Path, database):
        self.books_dir = Path(books_dir)
        self.database = database

    def load(self) -> Dict[str, Dict[str, Any]]:
        books: Dict[str, Dict[str, Any]] = {}
        if not self.books_dir.exists():
            logger.warning("BOOKS_DIR does not exist: %s", self.books_dir)
            return books
        for folder in sorted(self.books_dir.iterdir()):
            book_json = folder / "book.json"
            if not folder.is_dir() or not book_json.exists():
                continue
            try:
                with open(book_json, "r", encoding="utf-8") as source:
                    data = json.load(source)
                book_id = data["book_id"]
                books[book_id] = data
                self._sync_catalog(book_id, data)
                logger.info("Loaded book '%s' (%s) -> start_node='%s' (%d nodes)", data.get("title"), book_id, data.get("start_node"), len(data.get("nodes", {})))
            except Exception as exc:
                logger.error("Error loading book JSON %s: %s", book_json, exc)
        return books

    def _sync_catalog(self, book_id: str, data: Dict[str, Any]) -> None:
        try:
            self.database.upsert_book(data)
            endings = self._detect_endings(data)
            if endings:
                self.database.register_book_endings(book_id, endings)
        except Exception as exc:
            logger.warning("Could not upsert book/endings '%s' to DB: %s", book_id, exc)

    @staticmethod
    def _detect_endings(data: Dict[str, Any]):
        endings = []
        start_node = data.get("start_node", "sec_001")
        for node_id, node in data.get("nodes", {}).items():
            text = (node.get("text") or "").upper()
            title = (node.get("title") or "").upper()
            choices = node.get("choices") or []
            has_final_text = bool(re.search(r"\b(FIN|EL FIN|FIN DE LA AVENTURA)\b", text) or re.search(r"\b(FIN|EL FIN)\b", title))
            has_no_choices = not choices
            has_restart = len(choices) == 1 and choices[0].get("target_node") in (start_node, "sec_001", "sec001") and any(word in (choices[0].get("text") or "").lower() for word in ("retorna", "principio", "volver", "inicio", "reiniciar", "comenzar"))
            if has_final_text or has_no_choices or has_restart:
                label = "Final Victorioso" if any(word in text for word in ("VICTORIA", "CONSIGUES")) else "Final Trágico" if any(word in text for word in ("MUERTE", "CAES")) else "Final de la aventura"
                endings.append({"node_id": node_id, "label": label})
        return endings
