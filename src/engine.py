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
            logger.warning(f"BOOKS_DIR does not exist: {BOOKS_DIR}")
            return
        self.books.clear()
        for book_folder in sorted(BOOKS_DIR.iterdir()):
            if book_folder.is_dir():
                book_json = book_folder / "book.json"
                if book_json.exists():
                    try:
                        with open(book_json, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            b_id = data["book_id"]
                            self.books[b_id] = data
                            try:
                                self.db.upsert_book(data)
                                # Detect and register book endings in SQLite
                                endings = []
                                import re
                                start_node_id = data.get("start_node", "sec_001")
                                for n_id, n_data in data.get("nodes", {}).items():
                                    t_up = (n_data.get("text") or "").upper()
                                    tit_up = (n_data.get("title") or "").upper()
                                    n_choices = n_data.get("choices") or []
                                    has_fin = bool(re.search(r'\b(FIN|EL FIN|FIN DE LA AVENTURA)\b', t_up) or re.search(r'\b(FIN|EL FIN)\b', tit_up))
                                    has_zero = len(n_choices) == 0
                                    has_restart = False
                                    if len(n_choices) == 1:
                                        target = n_choices[0].get("target_node")
                                        c_txt = (n_choices[0].get("text") or "").lower()
                                        if target in (start_node_id, "sec_001", "sec001") and any(kw in c_txt for kw in ("retorna", "principio", "volver", "inicio", "reiniciar", "comenzar")):
                                            has_restart = True
                                    if has_fin or has_zero or has_restart:
                                        label = "Final de la aventura"
                                        if "VICTORIA" in t_up or "CONSIGUES" in t_up: label = "Final Victorioso"
                                        elif "MUERTE" in t_up or "CAES" in t_up: label = "Final Trágico"
                                        endings.append({"node_id": n_id, "label": label})
                                if endings:
                                    self.db.register_book_endings(b_id, endings)
                            except Exception as dbe:
                                logger.warning(f"Could not upsert book/endings '{b_id}' to DB: {dbe}")
                            logger.info(f"📖 Loaded book '{data.get('title')}' ({b_id}) -> start_node = '{data.get('start_node')}' ({len(data.get('nodes', {}))} nodes)")
                    except Exception as e:
                        logger.error(f"Error loading book JSON {book_json}: {e}")

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
        if book_id not in self.books:
            logger.error(f"Book ID '{book_id}' not found.")
            return None

        book_data = self.books[book_id]
        start_node_id = book_data.get("start_node")
        if not start_node_id or start_node_id not in book_data.get("nodes", {}):
            available_nodes = book_data.get("nodes", {})
            start_node_id = next(iter(available_nodes), None)
            if not start_node_id:
                logger.error(f"Book '{book_id}' has no playable nodes.")
                return None
            logger.warning(
                "Book '%s' declares missing start_node; using first available node '%s'.",
                book_id, start_node_id,
            )
        logger.info(f"🎮 Starting new game for user {user_id} on book '{book_id}' at start_node = '{start_node_id}'")

        self.db.get_or_create_user(user_id)
        self.db.save_game(user_id, book_id, start_node_id, inventory={}, variables={})
        self.db.record_step(user_id, book_id, None, start_node_id, "Inicio de la aventura")
        book_title = book_data.get("title", book_id)
        self.db.log_audit_event(user_id, action_type="book_open", book_id=book_id, node_id=start_node_id, detail=f"Abrió libro: {book_title}")

        return self.get_current_state(user_id, book_id)

    def get_current_state(self, user_id: int, book_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not book_id:
            if not self.books:
                return None
            book_id = list(self.books.keys())[0]

        savegame = self.db.get_savegame(user_id, book_id)
        if not savegame:
            logger.info(f"No savegame found for user {user_id} on book '{book_id}'. Starting fresh game.")
            return self.start_game(user_id, book_id)

        book_data = self.books.get(book_id)
        if not book_data:
            logger.error(f"Book '{book_id}' not found in engine memory.")
            return None

        current_node_id = savegame["current_node_id"]
        start_node_id = book_data.get("start_node", "sec_002")

        logger.info(f"🕹️ User {user_id} state on '{book_id}': saved_node='{current_node_id}', book_start_node='{start_node_id}'")

        node_data = book_data["nodes"].get(current_node_id)
        if not node_data:
            logger.info(f"Savegame node '{current_node_id}' not found in book '{book_id}'. Resetting to '{start_node_id}'.")
            return self.start_game(user_id, book_id)

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

        for plugin in self.plugins:
            savegame = plugin.on_choice_made(user_id, choice_dict, savegame)

        self.db.save_game(
            user_id,
            book_id,
            target_node_id,
            inventory=savegame.get("inventory"),
            variables=savegame.get("variables")
        )
        self.db.record_step(user_id, book_id, from_node_id, target_node_id, choice_dict.get("text"))
        
        target_node_data = self.books.get(book_id, {}).get("nodes", {}).get(target_node_id, {})
        choices = target_node_data.get("choices", [])
        is_terminal = (len(choices) == 0)
        self.db.record_ending_reached(user_id, book_id, target_node_id, is_terminal=is_terminal)

        logger.info(f"🔀 User {user_id} moved from '{from_node_id}' to '{target_node_id}' in book '{book_id}'")
        return self.get_current_state(user_id, book_id)

    def jump_to_node(self, user_id: int, book_id: str, target: str) -> Optional[Dict[str, Any]]:
        """Jumps directly to a target section by section number or node ID."""
        if book_id not in self.books:
            return None
        book_data = self.books[book_id]
        nodes = book_data.get("nodes", {})

        target_node_id = None
        target_str = str(target).strip()

        # 1. Exact node_id match
        if target_str in nodes:
            target_node_id = target_str
        else:
            # 2. Match by display_number or numeric string
            import re
            nums = re.findall(r'\d+', target_str)
            clean_num = int(nums[0]) if nums else None

            if clean_num is not None:
                # Search by display_number
                for n_id, n_data in nodes.items():
                    if n_data.get("display_number") == clean_num:
                        target_node_id = n_id
                        break

                # Search by padded/short node_id patterns
                if not target_node_id:
                    padded_id = f"sec_{clean_num:03d}"
                    short_id = f"sec_{clean_num}"
                    if padded_id in nodes:
                        target_node_id = padded_id
                    elif short_id in nodes:
                        target_node_id = short_id

        if not target_node_id:
            logger.warning(f"Jump failed: Section target '{target}' not found in book '{book_id}'")
            return None

        savegame = self.db.get_savegame(user_id, book_id)
        from_node_id = savegame["current_node_id"] if savegame else None

        self.db.save_game(user_id, book_id, target_node_id)
        display_num = nodes[target_node_id].get("display_number", target_node_id)
        self.db.record_step(user_id, book_id, from_node_id, target_node_id, f"Navegación a sección {display_num}")

        logger.info(f"⚡ User {user_id} jumped to '{target_node_id}' in book '{book_id}'")
        return self.get_current_state(user_id, book_id)
