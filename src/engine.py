import logging
from typing import Dict, Any, Optional, List
from config import BOOKS_DIR
from src.db import Database
from src.plugins.base import BasePlugin
from src.book_loader import InstalledBookLoader
from src.game_session import GameSessionService

logger = logging.getLogger("GameEngine")

class GameEngine:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.books: Dict[str, Dict[str, Any]] = {}
        self.plugins: List[BasePlugin] = []
        self.book_loader = InstalledBookLoader(BOOKS_DIR, self.db)
        self._load_installed_books()
        self.session_service = GameSessionService(self.db, self.books, self.plugins)

    def register_plugin(self, plugin: BasePlugin):
        self.plugins.append(plugin)

    def _load_installed_books(self):
        self.books = self.book_loader.load()
        if hasattr(self, "session_service"):
            self.session_service.books = self.books

    def list_books(self) -> List[Dict[str, Any]]:
        return [
            {
                "book_id": b_id,
                "title": data.get("title", b_id),
                "author": data.get("author", "Unknown"),
                "year": data.get("year"),
                "series": data.get("series"),
                "volume": data.get("volume"),
                "language": data.get("language", "es"),
                "description": data.get("description"),
                "cover_image": data.get("cover_image"),
                "total_sections": data.get("total_sections", 0)
            }
            for b_id, data in self.books.items()
        ]

    def start_game(self, user_id: int, book_id: str) -> Optional[Dict[str, Any]]:
        return self.session_service.start_game(user_id, book_id)

    def get_current_state(self, user_id: int, book_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self.session_service.get_current_state(user_id, book_id)

    def make_choice(self, user_id: int, choice_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.session_service.make_choice(user_id, choice_dict)

    def jump_to_node(self, user_id: int, book_id: str, target: str) -> Optional[Dict[str, Any]]:
        return self.session_service.jump_to_node(user_id, book_id, target)
