import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Savegames table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS savegames (
                    user_id INTEGER PRIMARY KEY,
                    book_id TEXT NOT NULL,
                    current_node_id TEXT NOT NULL,
                    inventory TEXT DEFAULT '{}',
                    variables TEXT DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # History table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    from_node_id TEXT,
                    to_node_id TEXT NOT NULL,
                    choice_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            conn.commit()

    def get_or_create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                cursor.execute(
                    "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                    (user_id, username, first_name)
                )
                conn.commit()

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
            return {
                "user_id": row["user_id"],
                "book_id": row["book_id"],
                "current_node_id": row["current_node_id"],
                "inventory": json.loads(row["inventory"] or "{}"),
                "variables": json.loads(row["variables"] or "{}"),
                "updated_at": row["updated_at"]
            }

    def save_game(self, user_id: int, book_id: str, current_node_id: str, inventory: Optional[dict] = None, variables: Optional[dict] = None):
        inv_json = json.dumps(inventory or {})
        vars_json = json.dumps(variables or {})
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savegames (user_id, book_id, current_node_id, inventory, variables, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    book_id = excluded.book_id,
                    current_node_id = excluded.current_node_id,
                    inventory = excluded.inventory,
                    variables = excluded.variables,
                    updated_at = excluded.updated_at
            """, (user_id, book_id, current_node_id, inv_json, vars_json, now))
            conn.commit()

    def record_step(self, user_id: int, book_id: str, from_node_id: Optional[str], to_node_id: str, choice_text: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (user_id, book_id, from_node_id, to_node_id, choice_text)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, book_id, from_node_id, to_node_id, choice_text))
            conn.commit()

    def get_history(self, user_id: int, book_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM history WHERE user_id = ? AND book_id = ? ORDER BY id DESC LIMIT ?
            """, (user_id, book_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
