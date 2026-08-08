import logging
from typing import Any, Dict, List, Optional

from src.db import Database
from src.game_navigation import GameNavigationResolver
from src.plugins.base import BasePlugin

logger = logging.getLogger("GameSession")


class GameSessionService:
    """Owns persistent game-session state and node transitions.

    Book discovery/loading lives in ``InstalledBookLoader``; this service only
    coordinates the user's savegame, history and plugin hooks for an already
    loaded catalog.
    """

    def __init__(self, db: Database, books: Dict[str, Dict[str, Any]], plugins: List[BasePlugin]):
        self.db = db
        self.books = books
        self.plugins = plugins

    def start_game(self, user_id: int, book_id: str) -> Optional[Dict[str, Any]]:
        if book_id not in self.books:
            logger.error("Book ID '%s' not found.", book_id)
            return None

        book_data = self.books[book_id]
        start_node_id = book_data.get("start_node")
        if not start_node_id or start_node_id not in book_data.get("nodes", {}):
            available_nodes = book_data.get("nodes", {})
            start_node_id = next(iter(available_nodes), None)
            if not start_node_id:
                logger.error("Book '%s' has no playable nodes.", book_id)
                return None
            logger.warning(
                "Book '%s' declares missing start_node; using first available node '%s'.",
                book_id,
                start_node_id,
            )

        logger.info(
            "Starting new game for user %s on book '%s' at start_node = '%s'",
            user_id,
            book_id,
            start_node_id,
        )
        self.db.get_or_create_user(user_id)
        self.db.save_game(user_id, book_id, start_node_id, inventory={}, variables={})
        self.db.record_step(user_id, book_id, None, start_node_id, "Inicio de la aventura")
        book_title = book_data.get("title", book_id)
        self.db.log_audit_event(
            user_id,
            action_type="book_open",
            book_id=book_id,
            node_id=start_node_id,
            detail=f"Abrió libro: {book_title}",
        )
        return self.get_current_state(user_id, book_id)

    def get_current_state(self, user_id: int, book_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not book_id:
            if not self.books:
                return None
            book_id = list(self.books.keys())[0]

        savegame = self.db.get_savegame(user_id, book_id)
        if not savegame:
            logger.info("No savegame found for user %s on book '%s'. Starting fresh game.", user_id, book_id)
            return self.start_game(user_id, book_id)

        book_data = self.books.get(book_id)
        if not book_data:
            logger.error("Book '%s' not found in engine memory.", book_id)
            return None

        current_node_id = savegame["current_node_id"]
        start_node_id = book_data.get("start_node", "sec_002")
        logger.info(
            "User %s state on '%s': saved_node='%s', book_start_node='%s'",
            user_id,
            book_id,
            current_node_id,
            start_node_id,
        )

        node_data = book_data["nodes"].get(current_node_id)
        if not node_data:
            logger.info(
                "Savegame node '%s' not found in book '%s'. Resetting to '%s'.",
                current_node_id,
                book_id,
                start_node_id,
            )
            return self.start_game(user_id, book_id)

        state = {
            "book_id": book_id,
            "book_title": book_data.get("title"),
            "current_node": node_data,
            "inventory": savegame["inventory"],
            "variables": savegame["variables"],
            "playback_node_id": savegame.get("playback_node_id"),
            "playback_position_seconds": savegame.get("playback_position_seconds", 0),
        }
        for plugin in self.plugins:
            state = plugin.on_node_enter(user_id, node_data, state)
            state["current_node"]["choices"] = plugin.evaluate_choices(
                user_id, state["current_node"]["choices"], state
            )
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
        for plugin in self.plugins:
            savegame = plugin.on_choice_made(user_id, choice_dict, savegame)

        self.db.save_game(
            user_id,
            book_id,
            target_node_id,
            inventory=savegame.get("inventory"),
            variables=savegame.get("variables"),
        )
        self.db.record_step(user_id, book_id, from_node_id, target_node_id, choice_dict.get("text"))

        target_node_data = self.books.get(book_id, {}).get("nodes", {}).get(target_node_id, {})
        is_terminal = len(target_node_data.get("choices", [])) == 0
        self.db.record_ending_reached(user_id, book_id, target_node_id, is_terminal=is_terminal)
        logger.info("User %s moved from '%s' to '%s' in book '%s'", user_id, from_node_id, target_node_id, book_id)
        return self.get_current_state(user_id, book_id)

    def jump_to_node(self, user_id: int, book_id: str, target: str) -> Optional[Dict[str, Any]]:
        if book_id not in self.books:
            return None
        nodes = self.books[book_id].get("nodes", {})
        target_node_id = GameNavigationResolver.resolve(nodes, target)
        if not target_node_id:
            logger.warning("Jump failed: Section target '%s' not found in book '%s'", target, book_id)
            return None

        savegame = self.db.get_savegame(user_id, book_id)
        from_node_id = savegame["current_node_id"] if savegame else None
        self.db.save_game(user_id, book_id, target_node_id)
        display_num = nodes[target_node_id].get("display_number", target_node_id)
        self.db.record_step(user_id, book_id, from_node_id, target_node_id, f"Navegación a sección {display_num}")
        logger.info("User %s jumped to '%s' in book '%s'", user_id, target_node_id, book_id)
        return self.get_current_state(user_id, book_id)
