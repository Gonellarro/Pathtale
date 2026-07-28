import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from config import BOOKS_DIR
from src.db import Database
from src.plugins.base import BasePlugin

logger = logging.getLogger("GameEngine")

class GameEngine:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.books: Dict[str, Dict[str, Any]] = {}
        self.plugins: List[BasePlugin] = []
        self._load_installed_books()

    def register_plugin(self, plugin: BasePlugin):
        self.plugins.append(plugin)

    def _load_installed_books(self):
        """Discovers and loads all imported book.json files in data/books/."""
        if not BOOKS_DIR.exists():
            return
        for book_folder in BOOKS_DIR.iterdir():
            if book_folder.is_dir():
                book_json = book_folder / "book.json"
                if book_json.exists():
                    try:
                        with open(book_json, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            b_id = data["book_id"]
                            self.books[b_id] = data
                            logger.info(f"Loaded book: '{data.get('title')}' ({b_id})")
                    except Exception as e:
                        logger.error(f"Error loading book JSON {book_json}: {e}")

    def list_books(self) -> List[Dict[str, str]]:
        return [
            {
                "book_id": b_id,
                "title": data.get("title", b_id),
                "author": data.get("author", "Unknown"),
                "cover_image": data.get("cover_image")
            }
            for b_id, data in self.books.items()
        ]

    def start_game(self, user_id: int, book_id: str) -> Optional[Dict[str, Any]]:
        if book_id not in self.books:
            logger.error(f"Book ID '{book_id}' not found.")
            return None

        book_data = self.books[book_id]
        start_node_id = book_data["start_node"]

        self.db.get_or_create_user(user_id)
        self.db.save_game(user_id, book_id, start_node_id, inventory={}, variables={})
        self.db.record_step(user_id, book_id, None, start_node_id, "Inicio de la aventura")

        return self.get_current_state(user_id, book_id)

    def get_current_state(self, user_id: int, book_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # If book_id not given, get active savegame
        if not book_id:
            # Pick first installed book if user has no savegame
            if not self.books:
                return None
            book_id = list(self.books.keys())[0]

        savegame = self.db.get_savegame(user_id, book_id)
        if not savegame:
            # Auto-start if no savegame exists
            return self.start_game(user_id, book_id)

        current_node_id = savegame["current_node_id"]
        book_data = self.books.get(book_id)
        if not book_data:
            return None

        node_data = book_data["nodes"].get(current_node_id)
        if not node_data:
            logger.error(f"Node '{current_node_id}' not found in book '{book_id}'")
            return None

        # Execute plugin hooks
        state = {
            "book_id": book_id,
            "book_title": book_data.get("title"),
            "current_node": node_data,
            "inventory": savegame["inventory"],
            "variables": savegame["variables"]
        }

        for plugin in self.plugins:
            state = plugin.on_node_enter(user_id, node_data, state)
            state["current_node"]["choices"] = plugin.evaluate_choices(user_id, state["current_node"]["choices"], state)

        return state

    def make_choice(self, user_id: int, choice_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        book_id = choice_dict.get("book_id")
        target_node_id = choice_dict.get("target_node")
        if not target_node_id:
            return None

        savegame = self.db.get_savegame(user_id, book_id)
        if not savegame:
            return None

        from_node_id = savegame["current_node_id"]

        # Run plugin hooks on choice
        for plugin in self.plugins:
            savegame = plugin.on_choice_made(user_id, choice_dict, savegame)

        # Update savegame and record history step
        self.db.save_game(
            user_id,
            book_id,
            target_node_id,
            inventory=savegame.get("inventory"),
            variables=savegame.get("variables")
        )
        self.db.record_step(user_id, book_id, from_node_id, target_node_id, choice_dict.get("text"))

        return self.get_current_state(user_id, book_id)
