import sqlite3
import json
import hashlib
import os
import secrets
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
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    first_name TEXT,
                    password_hash TEXT,
                    salt TEXT,
                    settings TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add columns if table existed without them
            for col, col_type in [("password_hash", "TEXT"), ("salt", "TEXT"), ("settings", "TEXT DEFAULT '{}'")]:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # Books metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    book_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT,
                    publisher TEXT,
                    year TEXT,
                    language TEXT DEFAULT 'es',
                    description TEXT,
                    isbn TEXT,
                    genre TEXT,
                    series TEXT,
                    volume INTEGER,
                    estimated_duration TEXT,
                    cover_image TEXT,
                    total_sections INTEGER,
                    start_node TEXT,
                    rating REAL DEFAULT 4.8,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migration check: if savegames table exists with old schema, migrate to composite PRIMARY KEY (user_id, book_id)
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='savegames'")
            row = cursor.fetchone()
            if row and "PRIMARY KEY (user_id, book_id)" not in row["sql"]:
                cursor.execute("""
                    CREATE TABLE savegames_new (
                        user_id INTEGER NOT NULL,
                        book_id TEXT NOT NULL,
                        current_node_id TEXT NOT NULL,
                        inventory TEXT DEFAULT '{}',
                        variables TEXT DEFAULT '{}',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, book_id),
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                """)
                cursor.execute("""
                    INSERT OR REPLACE INTO savegames_new (user_id, book_id, current_node_id, inventory, variables, updated_at)
                    SELECT user_id, book_id, current_node_id, inventory, variables, updated_at FROM savegames
                """)
                cursor.execute("DROP TABLE savegames")
                cursor.execute("ALTER TABLE savegames_new RENAME TO savegames")

            # Savegames table (user_id, book_id composite key)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS savegames (
                    user_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    current_node_id TEXT NOT NULL,
                    inventory TEXT DEFAULT '{}',
                    variables TEXT DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, book_id),
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

            # Create default guest user (user_id=1) if not present
            cursor.execute("SELECT * FROM users WHERE user_id = 1")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO users (user_id, username, first_name) VALUES (1, 'invitado', 'Invitado')"
                )

            conn.commit()

    # --- Authentication Methods ---

    def _hash_password(self, password: str, salt_hex: str) -> str:
        salt_bytes = bytes.fromhex(salt_hex)
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000).hex()

    def register_user(self, username: str, password: str, first_name: Optional[str] = None) -> Dict[str, Any]:
        username_clean = username.strip().lower()
        if not username_clean or len(password) < 4:
            raise ValueError("Nombre de usuario y contraseña (mín. 4 caracteres) requeridos.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username_clean,))
            if cursor.fetchone():
                raise ValueError("El nombre de usuario ya está registrado.")

            salt_hex = os.urandom(16).hex()
            pwd_hash = self._hash_password(password, salt_hex)
            display_name = first_name or username.strip()

            cursor.execute(
                "INSERT INTO users (username, first_name, password_hash, salt) VALUES (?, ?, ?, ?)",
                (username_clean, display_name, pwd_hash, salt_hex)
            )
            user_id = cursor.lastrowid
            token = secrets.token_hex(32)
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
            conn.commit()

            return {
                "user_id": user_id,
                "username": username_clean,
                "first_name": display_name,
                "token": token
            }

    def login_user(self, username: str, password: str) -> Dict[str, Any]:
        username_clean = username.strip().lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE LOWER(username) = ?", (username_clean,))
            user = cursor.fetchone()
            if not user or not user["password_hash"] or not user["salt"]:
                raise ValueError("Usuario o contraseña incorrectos.")

            computed_hash = self._hash_password(password, user["salt"])
            if computed_hash != user["password_hash"]:
                raise ValueError("Usuario o contraseña incorrectos.")

            token = secrets.token_hex(32)
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["user_id"]))
            conn.commit()

            return {
                "user_id": user["user_id"],
                "username": user["username"],
                "first_name": user["first_name"] or user["username"],
                "token": token
            }

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.settings, u.created_at
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.token = ?
            """, (token,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "first_name": row["first_name"] or row["username"],
                "settings": json.loads(row["settings"] or "{}"),
                "created_at": row["created_at"]
            }

    def logout_user(self, token: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
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

    # --- Savegame & Gameplay Methods ---

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

    def get_last_active_game(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM savegames WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "book_id": row["book_id"],
                "current_node_id": row["current_node_id"],
                "updated_at": row["updated_at"]
            }

    def get_in_progress_games(self, user_id: int, limit: int = 3) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM savegames WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def upsert_book(self, b: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO books (
                    book_id, title, author, publisher, year, language, description,
                    isbn, genre, series, volume, estimated_duration, cover_image,
                    total_sections, start_node
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    title = excluded.title,
                    author = excluded.author,
                    publisher = excluded.publisher,
                    year = excluded.year,
                    language = excluded.language,
                    description = excluded.description,
                    isbn = excluded.isbn,
                    genre = excluded.genre,
                    series = excluded.series,
                    volume = excluded.volume,
                    estimated_duration = excluded.estimated_duration,
                    cover_image = excluded.cover_image,
                    total_sections = excluded.total_sections,
                    start_node = excluded.start_node
            """, (
                b.get("book_id"), b.get("title"), b.get("author"), b.get("publisher"),
                b.get("year"), b.get("language", "es"), b.get("description"), b.get("isbn"),
                b.get("genre", "Ficción Interactiva"), b.get("series"), b.get("volume"),
                b.get("estimated_duration", "30 minutos"), b.get("cover_image"),
                b.get("total_sections", 1), b.get("start_node")
            ))
            conn.commit()

    def get_top_tags(self, limit: int = 5) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT genre, series FROM books")
            rows = cursor.fetchall()
            
            tags = []
            for r in rows:
                if r["genre"]:
                    for g in r["genre"].replace("·", ",").replace("/", ",").split(","):
                        g_clean = g.strip()
                        if g_clean and g_clean.lower() not in [t.lower() for t in tags]:
                            tags.append(g_clean)
                if r["series"]:
                    s_clean = r["series"].strip()
                    if s_clean and s_clean.lower() not in [t.lower() for t in tags]:
                        tags.append(s_clean)
            
            return tags[:limit]

    def save_game(self, user_id: int, book_id: str, current_node_id: str, inventory: Optional[dict] = None, variables: Optional[dict] = None):
        inv_json = json.dumps(inventory or {})
        vars_json = json.dumps(variables or {})
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO savegames (user_id, book_id, current_node_id, inventory, variables, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, book_id) DO UPDATE SET
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

    def get_history(self, user_id: int, book_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM history WHERE user_id = ? AND book_id = ? ORDER BY id DESC LIMIT ?
            """, (user_id, book_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def update_user_settings(self, user_id: int, settings: Dict[str, Any]):
        self.get_or_create_user(user_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET settings = ? WHERE user_id = ?", (json.dumps(settings), user_id))
            conn.commit()

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT settings FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row["settings"]:
                try:
                    return json.loads(row["settings"])
                except Exception:
                    pass
            return {}

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT book_id) as books_started FROM savegames WHERE user_id = ?", (user_id,))
            books_count = cursor.fetchone()["books_started"]
            
            cursor.execute("SELECT COUNT(*) as decisions_made FROM history WHERE user_id = ?", (user_id,))
            decisions_count = cursor.fetchone()["decisions_made"]
            
            return {
                "books_started": books_count,
                "decisions_made": decisions_count
            }
