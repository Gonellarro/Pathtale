import json
from typing import Optional, Dict, Any, List
from src.db.base import BaseRepository

class GameplayRepository(BaseRepository):
    def get_savegame(self, user_id: int, book_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM savegames WHERE user_id = ? AND book_id = ?",
                (user_id, book_id)
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            return {
                "save_id": d.get("save_id") or d.get("id") or 0,
                "user_id": d["user_id"],
                "book_id": d["book_id"],
                "current_node_id": d["current_node_id"],
                "inventory": json.loads(d.get("inventory") or "[]"),
                "variables": json.loads(d.get("variables") or "{}"),
                "updated_at": d.get("updated_at")
            }

    def get_last_active_game(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, b.title, b.author, b.cover_image, b.genre, b.estimated_duration
                FROM savegames s
                JOIN books b ON b.book_id = s.book_id
                WHERE s.user_id = ?
                ORDER BY s.updated_at DESC
                LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["inventory"] = json.loads(res.get("inventory") or "[]")
            res["variables"] = json.loads(res.get("variables") or "{}")
            return res

    def get_in_progress_games(self, user_id: int, limit: int = 3) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, b.title, b.author, b.cover_image, b.genre, b.estimated_duration, b.total_sections
                FROM savegames s
                JOIN books b ON b.book_id = s.book_id
                WHERE s.user_id = ?
                ORDER BY s.updated_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["inventory"] = json.loads(d.get("inventory") or "[]")
                d["variables"] = json.loads(d.get("variables") or "{}")
                result.append(d)
            return result

    def save_game(self, user_id: int, book_id: str, current_node_id: str, inventory: Optional[dict] = None, variables: Optional[dict] = None):
        inv_json = json.dumps(inventory if inventory is not None else [])
        var_json = json.dumps(variables if variables is not None else {})

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savegames (user_id, book_id, current_node_id, inventory, variables, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, book_id) DO UPDATE SET
                    current_node_id=excluded.current_node_id,
                    inventory=excluded.inventory,
                    variables=excluded.variables,
                    updated_at=CURRENT_TIMESTAMP
            """, (user_id, book_id, current_node_id, inv_json, var_json))

            cursor.execute("""
                INSERT INTO reading_logs (user_id, book_id, node_id, choice_made, action_type)
                VALUES (?, ?, ?, 'Avance de lectura', 'progress_save')
            """, (user_id, book_id, current_node_id))
            conn.commit()

    def record_step(self, user_id: int, book_id: str, from_node_id: Optional[str], to_node_id: str, choice_text: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (user_id, book_id, from_node_id, to_node_id, choice_text)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, book_id, from_node_id, to_node_id, choice_text))

            cursor.execute("""
                INSERT INTO reading_logs (user_id, book_id, node_id, choice_made, action_type)
                VALUES (?, ?, ?, ?, 'choice')
            """, (user_id, book_id, to_node_id, choice_text))
            conn.commit()

    def get_history(self, user_id: int, book_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM history WHERE user_id = ? AND book_id = ? ORDER BY id DESC LIMIT ?
            """, (user_id, book_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def record_ending_reached(self, user_id: int, book_id: str, node_id: str, is_terminal: bool = False) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ending_id, label FROM book_endings WHERE book_id = ? AND node_id = ?", (book_id, node_id))
            ending = cursor.fetchone()
            if not ending and is_terminal:
                cursor.execute("INSERT OR IGNORE INTO book_endings (book_id, node_id, label) VALUES (?, ?, ?)", 
                               (book_id, node_id, "Final de la aventura"))
                conn.commit()
                cursor.execute("SELECT ending_id, label FROM book_endings WHERE book_id = ? AND node_id = ?", (book_id, node_id))
                ending = cursor.fetchone()

            if ending:
                ending_id = ending["ending_id"]
                cursor.execute("""
                    INSERT INTO user_book_endings (user_id, ending_id, times_reached)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, ending_id) DO UPDATE SET
                        times_reached = times_reached + 1
                """, (user_id, ending_id))

                end_label = ending["label"] if ending["label"] else "Final de la aventura"
                cursor.execute("""
                    INSERT INTO reading_logs (user_id, book_id, node_id, choice_made, action_type)
                    VALUES (?, ?, ?, ?, 'ending_reached')
                """, (user_id, book_id, node_id, end_label))
                conn.commit()
                return {"ending_id": ending_id, "label": ending["label"], "node_id": node_id}
            return None
