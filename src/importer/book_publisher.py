import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger("Importer.BookPublisher")


class BookPublisher:
    """Builds and publishes the canonical book representation."""

    def __init__(self, database=None):
        self.database = database

    def build_document(
        self,
        *,
        book_id: str,
        title: str,
        author: str,
        language: str,
        description: Optional[str],
        publisher: Optional[str],
        year: Optional[Any],
        isbn: Optional[str],
        genre: Optional[str],
        series: Optional[str],
        volume: Optional[Any],
        cover_image: Optional[str],
        start_node: str,
        tier_id: int,
        narrator_id: int,
        supplements: list,
        nodes: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_words = sum(len(node.get("text", "").split()) for node in nodes.values())
        total_sections = len(nodes)
        estimated_minutes = max(5, round(total_words / 180)) if total_words > 0 else total_sections * 2
        return {
            "ir_version": "1.1",
            "book_id": book_id,
            "title": title,
            "author": author,
            "publisher": publisher,
            "year": year,
            "language": language,
            "description": description or f"Aventura interactiva basada en {title}.",
            "isbn": isbn,
            "genre": genre or "Ficción Interactiva",
            "series": series,
            "volume": volume,
            "estimated_duration": f"{estimated_minutes} minutos",
            "cover_image": cover_image,
            "total_sections": total_sections,
            "start_node": start_node,
            "tier_id": tier_id,
            "narrator_id": narrator_id,
            "features": {"inventory": False, "dice": False, "combat": False, "variables": False},
            "supplements": supplements,
            "nodes": nodes,
        }

    def publish(self, output_dir: Path, document: Dict[str, Any], endings=None) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        book_json_path = output_dir / "book.json"
        with open(book_json_path, "w", encoding="utf-8") as file:
            json.dump(document, file, ensure_ascii=False, indent=2)

        logger.info("Imported %d nodes with extended metadata to %s", len(document.get("nodes", {})), book_json_path)
        if self.database:
            try:
                self.database.upsert_book(document)
                if endings:
                    self.database.register_book_endings(document["book_id"], endings)
                    logger.info("Registered %d ending nodes for '%s'.", len(endings), document["book_id"])
            except Exception as exc:
                logger.warning("Could not seed book in database: %s", exc)
        return book_json_path
