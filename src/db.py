import sqlite3
import json
import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from config import DB_PATH, SESSION_EXPIRE_DAYS, ADMIN_USERNAME, ADMIN_PASSWORD

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Enable Foreign Keys in SQLite
            cursor.execute("PRAGMA foreign_keys = ON;")

            # 1. Roles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT
                )
            """)

            # Seed default roles
            cursor.execute("INSERT OR IGNORE INTO roles (role_id, name, description) VALUES (1, 'admin', 'Administrador con acceso total')")
            cursor.execute("INSERT OR IGNORE INTO roles (role_id, name, description) VALUES (2, 'user', 'Usuario lector estándar')")

            # 2. Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    first_name TEXT,
                    password_hash TEXT,
                    salt TEXT,
                    role_id INTEGER NOT NULL DEFAULT 2,
                    is_active INTEGER DEFAULT 1,
                    settings TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE RESTRICT
                )
            """)

            # 3. Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # Migration for token PRIMARY KEY if sessions table existed with old schema
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sessions'")
            session_sql_row = cursor.fetchone()
            if session_sql_row and "PRIMARY KEY (token)" in session_sql_row["sql"]:
                cursor.execute("""
                    CREATE TABLE sessions_new (
                        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token TEXT UNIQUE NOT NULL,
                        user_id INTEGER NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("INSERT OR IGNORE INTO sessions_new (token, user_id, created_at) SELECT token, user_id, created_at FROM sessions")
                cursor.execute("DROP TABLE sessions")
                cursor.execute("ALTER TABLE sessions_new RENAME TO sessions")

            # 4. Narrators table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS narrators (
                    narrator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    specialty TEXT,
                    avatar_url TEXT,
                    bio TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed initial default narrators if empty
            cursor.execute("SELECT COUNT(*) as c FROM narrators")
            if cursor.fetchone()["c"] == 0:
                cursor.execute("""
                    INSERT INTO narrators (narrator_id, name, display_name, specialty, avatar_url) VALUES 
                    (1, 'DaveFX', 'DAVEFX', 'Español · Fantasía y Misterio', '/assets/narrator_davefx.jpg'),
                    (2, 'Lessac', 'LESSAC', 'Inglés · Drama y Aventuras', '/assets/narrator_lessac.jpg')
                """)

            # 5. Genres table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS genres (
                    genre_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    slug TEXT UNIQUE NOT NULL
                )
            """)

            # 6. Books metadata table
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
                    total_sections INTEGER DEFAULT 1,
                    start_node TEXT DEFAULT 'sec_001',
                    narrator_id INTEGER DEFAULT 1,
                    rating REAL DEFAULT 4.8,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (narrator_id) REFERENCES narrators(narrator_id) ON DELETE SET NULL
                )
            """)

            # Migration for narrator_id if books table existed without it
            try:
                cursor.execute("ALTER TABLE books ADD COLUMN narrator_id INTEGER DEFAULT 1")
            except Exception:
                pass

            cursor.execute("UPDATE books SET narrator_id = 1 WHERE narrator_id IS NULL OR narrator_id = 0")

            # 7. Subscription Tiers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscription_tiers (
                    tier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 0,
                    description TEXT
                )
            """)

            # Seed subscription tiers
            cursor.execute("INSERT OR IGNORE INTO subscription_tiers (tier_id, code, name, level, description) VALUES (1, 'demo', 'Demo Gratuita', 0, 'Acceso únicamente a audiolibros gratuitos de prueba')")
            cursor.execute("INSERT OR IGNORE INTO subscription_tiers (tier_id, code, name, level, description) VALUES (2, 'tier1', 'Tier 1 - Bronce', 1, 'Acceso a libros Demo y Tier 1')")
            cursor.execute("INSERT OR IGNORE INTO subscription_tiers (tier_id, code, name, level, description) VALUES (3, 'tier2', 'Tier 2 - Plata', 2, 'Acceso a libros Demo, Tier 1 y Tier 2')")
            cursor.execute("INSERT OR IGNORE INTO subscription_tiers (tier_id, code, name, level, description) VALUES (4, 'tier3', 'Tier 3 - Oro', 3, 'Acceso ilimitado a todo el catálogo (Demo, Tier 1, 2 y 3)')")

            # Migration for tier_id in books if table existed without it
            try:
                cursor.execute("ALTER TABLE books ADD COLUMN tier_id INTEGER DEFAULT 1")
            except Exception:
                pass

            cursor.execute("UPDATE books SET tier_id = 1 WHERE tier_id IS NULL OR tier_id = 0")

            # Migration for is_visible in books
            try:
                cursor.execute("ALTER TABLE books ADD COLUMN is_visible INTEGER DEFAULT 1")
            except Exception:
                pass

            cursor.execute("UPDATE books SET is_visible = 1 WHERE is_visible IS NULL")

            # 8. User Subscriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tier_id INTEGER NOT NULL DEFAULT 1,
                    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (tier_id) REFERENCES subscription_tiers(tier_id) ON DELETE RESTRICT
                )
            """)

            # 9. Book Genres intermediate table (N:M relation in 3FN)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS book_genres (
                    book_id TEXT NOT NULL,
                    genre_id INTEGER NOT NULL,
                    PRIMARY KEY (book_id, genre_id),
                    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE,
                    FOREIGN KEY (genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE
                )
            """)

            # 8. Savegames table (user_id, book_id composite key)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS savegames (
                    user_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    current_node_id TEXT NOT NULL,
                    progress_percent INTEGER DEFAULT 0,
                    inventory TEXT DEFAULT '{}',
                    variables TEXT DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, book_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
                )
            """)

            # 9. Reading Logs table (Audit & Analytics)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reading_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    book_id TEXT,
                    node_id TEXT,
                    choice_made TEXT,
                    action_type TEXT DEFAULT 'node_visit',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
                )
            """)

            # Migration for reading_logs schema if table existed with NOT NULL book_id
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reading_logs'")
            rl_sql_row = cursor.fetchone()
            if rl_sql_row and "book_id TEXT NOT NULL" in rl_sql_row["sql"]:
                cursor.execute("""
                    CREATE TABLE reading_logs_new (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        book_id TEXT,
                        node_id TEXT,
                        choice_made TEXT,
                        action_type TEXT DEFAULT 'node_visit',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("INSERT OR IGNORE INTO reading_logs_new (log_id, user_id, book_id, node_id, choice_made, action_type, created_at) SELECT log_id, user_id, NULLIF(book_id, ''), NULLIF(node_id, ''), choice_made, action_type, created_at FROM reading_logs")
                cursor.execute("DROP TABLE reading_logs")
                cursor.execute("ALTER TABLE reading_logs_new RENAME TO reading_logs")

            # Legacy history table kept for compatibility
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    from_node_id TEXT,
                    to_node_id TEXT NOT NULL,
                    choice_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # 10. Book Endings table (3FN Endings Model)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS book_endings (
                    ending_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    label TEXT,
                    is_good_ending INTEGER DEFAULT NULL,
                    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE,
                    UNIQUE (book_id, node_id)
                )
            """)

            # 11. User Book Endings Reached table (N:M User-Ending Discovery)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_book_endings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    ending_id INTEGER NOT NULL,
                    first_reached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    times_reached INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (ending_id) REFERENCES book_endings(ending_id) ON DELETE CASCADE,
                    UNIQUE (user_id, ending_id)
                )
            """)

            # High-performance indexes for frequent FK queries and analytics
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reading_logs_user_book ON reading_logs(user_id, book_id, action_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reading_logs_action ON reading_logs(action_type, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_book_endings_user ON user_book_endings(user_id)")

            # Analytics & Statistics SQL Views (Refresh view definitions on startup)
            cursor.execute("DROP VIEW IF EXISTS vw_user_book_progress")
            cursor.execute("""
                CREATE VIEW vw_user_book_progress AS
                SELECT
                    rl.user_id,
                    rl.book_id,
                    COUNT(DISTINCT rl.node_id) AS sections_read,
                    b.total_sections,
                    EXISTS (
                        SELECT 1 FROM user_book_endings ube
                        JOIN book_endings be ON be.ending_id = ube.ending_id
                        WHERE be.book_id = rl.book_id AND ube.user_id = rl.user_id
                    ) AS completed
                FROM reading_logs rl
                JOIN books b ON b.book_id = rl.book_id
                WHERE rl.action_type = 'node_visit'
                GROUP BY rl.user_id, rl.book_id;
            """)

            cursor.execute("DROP VIEW IF EXISTS vw_book_popularity")
            cursor.execute("""
                CREATE VIEW vw_book_popularity AS
                SELECT
                    rl.book_id,
                    b.title,
                    COUNT(DISTINCT rl.user_id) AS readers,
                    COUNT(*) AS total_visits
                FROM reading_logs rl
                JOIN books b ON b.book_id = rl.book_id
                WHERE rl.action_type = 'node_visit'
                GROUP BY rl.book_id
                ORDER BY readers DESC, total_visits DESC;
            """)

            # Seed initial Admin user if no admin account exists in the database
            cursor.execute("""
                SELECT COUNT(*) as c FROM users u
                JOIN roles r ON u.role_id = r.role_id
                WHERE r.name = 'admin'
            """)
            admin_row = cursor.fetchone()
            if not admin_row or admin_row["c"] == 0:
                salt_hex = os.urandom(16).hex()
                pwd_hash = self._hash_password(ADMIN_PASSWORD, salt_hex)
                admin_name = ADMIN_USERNAME.strip().lower()
                display_name = ADMIN_USERNAME.strip().capitalize()
                cursor.execute(
                    "INSERT INTO users (username, first_name, password_hash, salt, role_id) VALUES (?, ?, ?, ?, 1)",
                    (admin_name, display_name, pwd_hash, salt_hex)
                )

            conn.commit()

    # --- Authentication & User Methods ---

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
                "INSERT INTO users (username, first_name, password_hash, salt, role_id) VALUES (?, ?, ?, ?, 2)",
                (username_clean, display_name, pwd_hash, salt_hex)
            )
            user_id = cursor.lastrowid
            token = secrets.token_hex(32)
            expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            session_cols = [c["name"] for c in cursor.execute("PRAGMA table_info(sessions)").fetchall()]
            if "expires_at" in session_cols:
                cursor.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
            else:
                cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
            conn.commit()

            return {
                "user_id": user_id,
                "username": username_clean,
                "first_name": display_name,
                "role": "user",
                "role_name": "user",
                "token": token
            }

    def login_user(self, username: str, password: str) -> Dict[str, Any]:
        username_clean = username.strip().lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, r.name as role_name 
                FROM users u 
                LEFT JOIN roles r ON u.role_id = r.role_id 
                WHERE LOWER(u.username) = ?
            """, (username_clean,))
            user = cursor.fetchone()
            if not user or not user["password_hash"] or not user["salt"]:
                raise ValueError("Usuario o contraseña incorrectos.")

            if dict(user).get("is_active") == 0:
                raise ValueError("Esta cuenta de usuario ha sido desactivada.")

            computed_hash = self._hash_password(password, user["salt"])
            if computed_hash != user["password_hash"]:
                raise ValueError("Usuario o contraseña incorrectos.")

            token = secrets.token_hex(32)
            expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            session_cols = [c["name"] for c in cursor.execute("PRAGMA table_info(sessions)").fetchall()]
            if "expires_at" in session_cols:
                cursor.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user["user_id"], expires_at))
            else:
                cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["user_id"]))
            conn.commit()

            role_val = user["role_name"] or "user"
            return {
                "user_id": user["user_id"],
                "username": user["username"],
                "first_name": user["first_name"] or user["username"],
                "role": role_val,
                "role_name": role_val,
                "token": token
            }

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, s.created_at as session_created_at, r.name as role_name
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                LEFT JOIN roles r ON u.role_id = r.role_id
                WHERE s.token = ?
            """, (token,))
            row = cursor.fetchone()
            if not row:
                return None

            row_dict = dict(row)
            if row_dict.get("is_active") == 0:
                return None

            # Check expiration date if present
            expires_at = row_dict.get("expires_at")
            if expires_at:
                try:
                    exp_dt = datetime.strptime(str(expires_at), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > exp_dt:
                        # Session expired: clean up token and reject
                        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
                        conn.commit()
                        return None
                except Exception:
                    pass

            role_val = row_dict.get("role_name") or "user"
            return {
                "user_id": row_dict["user_id"],
                "username": row_dict["username"],
                "first_name": row_dict.get("first_name") or row_dict["username"],
                "role": role_val,
                "role_name": role_val,
                "settings": json.loads(row_dict.get("settings") or "{}"),
                "created_at": row_dict.get("created_at")
            }

    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE token = ?", (token,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def logout_user(self, token: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.settings, u.created_at, r.name as role_name
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.role_id
                WHERE u.user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "first_name": row["first_name"] or row["username"],
                "role": row["role_name"] or "user",
                "role_name": row["role_name"] or "user",
                "created_at": row["created_at"]
            }

    def get_or_create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                cursor.execute(
                    "INSERT INTO users (user_id, username, first_name, role_id) VALUES (?, ?, ?, 2)",
                    (user_id, username, first_name)
                )
                conn.commit()

    # --- Subscriptions & Tier Management ---

    def get_all_subscription_tiers(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscription_tiers ORDER BY level ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_user_active_tier(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.tier_id, t.code, t.name, t.level, t.description, s.end_date
                FROM user_subscriptions s
                JOIN subscription_tiers t ON s.tier_id = t.tier_id
                WHERE s.user_id = ?
                  AND (s.end_date IS NULL OR s.end_date >= CURRENT_TIMESTAMP)
                ORDER BY t.level DESC, s.created_at DESC
                LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)

            cursor.execute("SELECT tier_id, code, name, level, description FROM subscription_tiers WHERE code = 'demo'")
            demo_row = cursor.fetchone()
            res = dict(demo_row) if demo_row else {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0}
            res["end_date"] = None
            return res

    def assign_user_subscription(self, user_id: int, tier_id: int, duration_days: Optional[int] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            end_date = None
            if duration_days and int(duration_days) > 0:
                cursor.execute("SELECT datetime('now', '+' || ? || ' days')", (int(duration_days),))
                end_date = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO user_subscriptions (user_id, tier_id, end_date)
                VALUES (?, ?, ?)
            """, (user_id, tier_id, end_date))
            conn.commit()

    def get_book_tier(self, book_id: str) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.tier_id, t.code, t.name, t.level, COALESCE(b.is_visible, 1) as is_visible
                FROM books b
                LEFT JOIN subscription_tiers t ON b.tier_id = t.tier_id
                WHERE b.book_id = ?
            """, (book_id,))
            row = cursor.fetchone()
            if row and row["tier_id"]:
                return dict(row)
            return {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0, "is_visible": 1}

    # --- Admin Users Management ---

    def get_all_users_admin(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.created_at, r.name as role,
                       COALESCE(st.name, 'Demo Gratuita') as tier_name,
                       COALESCE(st.code, 'demo') as tier_code,
                       COALESCE(st.level, 0) as tier_level,
                       us.end_date as tier_end_date,
                       COALESCE(st.tier_id, 1) as tier_id
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.role_id
                LEFT JOIN (
                    SELECT user_id, tier_id, end_date,
                           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
                    FROM user_subscriptions
                    WHERE end_date IS NULL OR end_date >= CURRENT_TIMESTAMP
                ) us ON u.user_id = us.user_id AND us.rn = 1
                LEFT JOIN subscription_tiers st ON us.tier_id = st.tier_id
                ORDER BY u.user_id ASC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_all_roles(self) -> List[Dict[str, Any]]:
        """Returns all system roles from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role_id, name, description FROM roles ORDER BY role_id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def create_user_admin(self, username: str, password: str, first_name: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
        username_clean = username.strip().lower()
        if not username_clean or len(password) < 4:
            raise ValueError("Nombre de usuario y contraseña (mín. 4 caracteres) requeridos.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username_clean,))
            if cursor.fetchone():
                raise ValueError("El nombre de usuario ya existe.")

            cursor.execute("SELECT role_id FROM roles WHERE name = ?", (role,))
            role_row = cursor.fetchone()
            role_id = role_row["role_id"] if role_row else 2

            salt_hex = os.urandom(16).hex()
            pwd_hash = self._hash_password(password, salt_hex)
            display_name = first_name or username.strip()

            cursor.execute(
                "INSERT INTO users (username, first_name, password_hash, salt, role_id) VALUES (?, ?, ?, ?, ?)",
                (username_clean, display_name, pwd_hash, salt_hex, role_id)
            )
            user_id = cursor.lastrowid
            conn.commit()

            return {
                "user_id": user_id,
                "username": username_clean,
                "first_name": display_name,
                "role": role
            }

    def update_user_admin(self, user_id: int, first_name: Optional[str] = None, role: Optional[str] = None, password: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if first_name is not None:
                cursor.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (first_name, user_id))
            if role is not None:
                cursor.execute("SELECT role_id FROM roles WHERE name = ?", (role,))
                role_row = cursor.fetchone()
                if role_row:
                    cursor.execute("UPDATE users SET role_id = ? WHERE user_id = ?", (role_row["role_id"], user_id))
            if password and len(password) >= 4:
                salt_hex = os.urandom(16).hex()
                pwd_hash = self._hash_password(password, salt_hex)
                cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE user_id = ?", (pwd_hash, salt_hex, user_id))
            conn.commit()

    def delete_user_admin(self, user_id: int, hard_delete: bool = False):
        if user_id == 1:
            raise ValueError("No se puede eliminar el usuario administrador principal (ID 1).")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if hard_delete:
                # Hard Delete: permanent removal from database
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            else:
                # Soft Delete: deactivate user account, preserving analytics history
                cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
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
                SELECT s.* 
                FROM savegames s
                JOIN books b ON s.book_id = b.book_id
                WHERE s.user_id = ? AND COALESCE(b.is_visible, 1) = 1
                ORDER BY s.updated_at DESC LIMIT 1
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
                SELECT s.* 
                FROM savegames s
                JOIN books b ON s.book_id = b.book_id
                WHERE s.user_id = ? AND COALESCE(b.is_visible, 1) = 1
                ORDER BY s.updated_at DESC LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def upsert_book(self, b: Dict[str, Any]):
        narrator_name = b.get("narrator") or "DaveFX"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Match narrator_id from narrators table
            cursor.execute("SELECT narrator_id FROM narrators WHERE LOWER(name) = LOWER(?)", (narrator_name,))
            n_row = cursor.fetchone()
            narrator_id = n_row["narrator_id"] if n_row else 1

            cursor.execute("""
                INSERT INTO books (
                    book_id, title, author, publisher, year, language, description,
                    isbn, genre, series, volume, estimated_duration, cover_image,
                    total_sections, start_node, narrator_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    start_node = excluded.start_node,
                    narrator_id = excluded.narrator_id
            """, (
                b.get("book_id"), b.get("title"), b.get("author"), b.get("publisher"),
                b.get("year"), b.get("language", "es"), b.get("description"), b.get("isbn"),
                b.get("genre", "Ficción Interactiva"), b.get("series"), b.get("volume"),
                b.get("estimated_duration", "30 minutos"), b.get("cover_image"),
                b.get("total_sections", 1), b.get("start_node"), narrator_id
            ))

            # Sync genres into genres & book_genres 3FN tables
            genre_str = b.get("genre") or ""
            if genre_str:
                for g in genre_str.replace("·", ",").replace("/", ",").split(","):
                    g_clean = g.strip()
                    if g_clean:
                        slug = g_clean.lower().replace(" ", "_")
                        cursor.execute("INSERT OR IGNORE INTO genres (name, slug) VALUES (?, ?)", (g_clean, slug))
                        cursor.execute("SELECT genre_id FROM genres WHERE slug = ?", (slug,))
                        g_row = cursor.fetchone()
                        if g_row:
                            cursor.execute("INSERT OR IGNORE INTO book_genres (book_id, genre_id) VALUES (?, ?)", (b.get("book_id"), g_row["genre_id"]))

            conn.commit()

    # --- Narrators Management ---

    def get_narrators_stats(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM narrators ORDER BY narrator_id ASC")
            narrators = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT narrator_id, COUNT(*) as count 
                FROM books 
                GROUP BY narrator_id
            """)
            counts = {r["narrator_id"]: r["count"] for r in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) as count FROM books")
            total_books = cursor.fetchone()["count"]

        for n in narrators:
            n["id"] = n["name"]
            c = counts.get(n["narrator_id"], 0)
            if n["name"] == "DaveFX" and c == 0:
                c = total_books
            n["story_count"] = c

        return narrators

    def create_narrator_admin(self, name: str, display_name: str, specialty: Optional[str] = None, avatar_url: Optional[str] = None, bio: Optional[str] = None) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO narrators (name, display_name, specialty, avatar_url, bio) VALUES (?, ?, ?, ?, ?)",
                (name.strip(), display_name.strip(), specialty, avatar_url or "/assets/narrator_davefx.jpg", bio)
            )
            nid = cursor.lastrowid
            conn.commit()
            return {"narrator_id": nid, "name": name, "display_name": display_name, "specialty": specialty, "avatar_url": avatar_url}

    def update_narrator_admin(self, narrator_id: int, display_name: Optional[str] = None, specialty: Optional[str] = None, avatar_url: Optional[str] = None, bio: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if display_name:
                cursor.execute("UPDATE narrators SET display_name = ? WHERE narrator_id = ?", (display_name, narrator_id))
            if specialty is not None:
                cursor.execute("UPDATE narrators SET specialty = ? WHERE narrator_id = ?", (specialty, narrator_id))
            if avatar_url is not None:
                cursor.execute("UPDATE narrators SET avatar_url = ? WHERE narrator_id = ?", (avatar_url, narrator_id))
            if bio is not None:
                cursor.execute("UPDATE narrators SET bio = ? WHERE narrator_id = ?", (bio, narrator_id))
            conn.commit()

    def delete_narrator_admin(self, narrator_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as c FROM books WHERE narrator_id = ?", (narrator_id,))
            if cursor.fetchone()["c"] > 0:
                raise ValueError("No se puede eliminar un narrador que tiene libros asignados.")
            cursor.execute("DELETE FROM narrators WHERE narrator_id = ?", (narrator_id,))
            conn.commit()

    # --- Books Admin Management ---

    def get_all_books_admin(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, n.display_name as narrator_name,
                       COALESCE(st.name, 'Demo Gratuita') as tier_name,
                       COALESCE(st.code, 'demo') as tier_code,
                       COALESCE(st.level, 0) as tier_level
                FROM books b
                LEFT JOIN narrators n ON b.narrator_id = n.narrator_id
                LEFT JOIN subscription_tiers st ON b.tier_id = st.tier_id
                ORDER BY b.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def update_book_admin(self, book_id: str, updates: Dict[str, Any]):
        fields = []
        values = []
        for k in ["title", "author", "genre", "series", "volume", "description", "language", "narrator_id", "tier_id", "is_visible"]:
            if k in updates and updates[k] is not None:
                fields.append(f"{k} = ?")
                val = updates[k]
                if val is True:
                    val = 1
                elif val is False:
                    val = 0
                values.append(val)
        if not fields:
            return
        values.append(book_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE books SET {', '.join(fields)} WHERE book_id = ?", values)
            conn.commit()

    def delete_book_admin(self, book_id: str, hard_delete: bool = False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if hard_delete:
                # Hard Delete: permanent removal from DB
                cursor.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
                cursor.execute("DELETE FROM savegames WHERE book_id = ?", (book_id,))
                cursor.execute("DELETE FROM reading_logs WHERE book_id = ?", (book_id,))
                cursor.execute("DELETE FROM book_endings WHERE book_id = ?", (book_id,))
            else:
                # Soft Delete: hide from catalog, preserving history
                cursor.execute("UPDATE books SET is_visible = 0 WHERE book_id = ?", (book_id,))
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

            # Record reading audit log
            cursor.execute("""
                INSERT INTO reading_logs (user_id, book_id, node_id, action_type)
                VALUES (?, ?, ?, 'progress_save')
            """, (user_id, book_id, current_node_id))
            conn.commit()

    def record_step(self, user_id: int, book_id: str, from_node_id: Optional[str], to_node_id: str, choice_text: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (user_id, book_id, from_node_id, to_node_id, choice_text)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, book_id, from_node_id, to_node_id, choice_text))

            # Record 3FN Audit Reading Log
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

    def log_audit_event(self, user_id: int, action_type: str, book_id: Optional[str] = None, node_id: Optional[str] = None, detail: str = ''):
        """Logs specific audit events: login, book_open, ending_reached, logout."""
        self.get_or_create_user(user_id)
        clean_book_id = str(book_id).strip() if (book_id and str(book_id).strip()) else None
        clean_node_id = str(node_id).strip() if (node_id and str(node_id).strip()) else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reading_logs (user_id, book_id, node_id, choice_made, action_type)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, clean_book_id, clean_node_id, detail or '', action_type))
            conn.commit()

    def get_reading_logs_admin(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns filtered audit history logs for the admin dashboard."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.*, u.username, u.first_name, COALESCE(b.title, l.book_id, '-') as book_title
                FROM reading_logs l
                JOIN users u ON l.user_id = u.user_id
                LEFT JOIN books b ON l.book_id = b.book_id
                WHERE l.action_type IN ('login', 'book_open', 'ending_reached', 'logout')
                ORDER BY l.log_id DESC
                LIMIT ?
            """, (limit,))
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

            cursor.execute("SELECT COUNT(DISTINCT ending_id) as endings_reached FROM user_book_endings WHERE user_id = ?", (user_id,))
            endings_row = cursor.fetchone()
            endings_count = endings_row["endings_reached"] if endings_row else 0
            
            return {
                "books_started": books_count,
                "decisions_made": decisions_count,
                "endings_reached": endings_count
            }

    # --- Endings & Comprehensive Analytics ---

    def register_book_endings(self, book_id: str, endings: List[Dict[str, Any]]):
        """Inserts or updates ending nodes for a book."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for end in endings:
                node_id = end.get("node_id")
                label = end.get("label", "Final de la aventura")
                is_good = end.get("is_good_ending", None)
                if node_id:
                    cursor.execute("""
                        INSERT INTO book_endings (book_id, node_id, label, is_good_ending)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(book_id, node_id) DO UPDATE SET
                            label = excluded.label,
                            is_good_ending = excluded.is_good_ending
                    """, (book_id, node_id, label, is_good))
            conn.commit()

    def record_ending_reached(self, user_id: int, book_id: str, node_id: str, is_terminal: bool = False) -> Optional[Dict[str, Any]]:
        """Records when a user reaches a book ending node."""
        self.get_or_create_user(user_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check if this node is an ending registered in book_endings
            cursor.execute("SELECT ending_id, label FROM book_endings WHERE book_id = ? AND node_id = ?", (book_id, node_id))
            ending = cursor.fetchone()
            if not ending and is_terminal:
                # If node has no choices (terminal node), auto-register as an ending
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

    def get_user_stats_detailed(self, user_id: int) -> Dict[str, Any]:
        """Returns comprehensive stats for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Summary stats
            cursor.execute("SELECT COUNT(DISTINCT book_id) as total FROM savegames WHERE user_id = ?", (user_id,))
            books_started = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as total FROM history WHERE user_id = ?", (user_id,))
            decisions_made = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(DISTINCT be.book_id) as completed
                FROM user_book_endings ube
                JOIN book_endings be ON be.ending_id = ube.ending_id
                WHERE ube.user_id = ?
            """, (user_id,))
            books_completed = cursor.fetchone()["completed"]

            # Per-book progress breakdown
            cursor.execute("""
                SELECT 
                    b.book_id,
                    b.title,
                    b.cover_image,
                    b.total_sections,
                    COALESCE(
                      (SELECT ROUND(CAST(COUNT(DISTINCT rl.node_id) AS FLOAT) / MAX(1, b.total_sections) * 100)
                       FROM reading_logs rl 
                       WHERE rl.user_id = ? AND rl.book_id = b.book_id AND rl.action_type = 'node_visit'),
                      0
                    ) as progress_percent,
                    (SELECT COUNT(DISTINCT be.ending_id) FROM book_endings be WHERE be.book_id = b.book_id) as total_endings,
                    (SELECT COUNT(DISTINCT ube.ending_id) 
                     FROM user_book_endings ube 
                     JOIN book_endings be ON be.ending_id = ube.ending_id 
                     WHERE be.book_id = b.book_id AND ube.user_id = ?) as endings_reached
                FROM savegames sg
                JOIN books b ON b.book_id = sg.book_id
                WHERE sg.user_id = ?
                ORDER BY sg.updated_at DESC
            """, (user_id, user_id, user_id))
            book_progress = [dict(r) for r in cursor.fetchall()]

            return {
                "user_id": user_id,
                "books_started": books_started,
                "books_completed": books_completed,
                "decisions_made": decisions_made,
                "books_progress": book_progress
            }

    def get_global_stats(self) -> Dict[str, Any]:
        """Returns platform-wide statistics for public and user view."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as c FROM users")
            total_users = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM books WHERE is_visible = 1")
            total_books = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM reading_logs WHERE action_type = 'node_visit'")
            total_reads = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM history")
            total_decisions = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM user_book_endings")
            total_endings_unlocked = cursor.fetchone()["c"]

            # 2.1 Most read book by community
            cursor.execute("""
                SELECT b.book_id, b.title, b.cover_image, COUNT(rl.log_id) as total_visits
                FROM books b
                LEFT JOIN reading_logs rl ON b.book_id = rl.book_id AND rl.action_type = 'node_visit'
                WHERE b.is_visible = 1
                GROUP BY b.book_id
                ORDER BY total_visits DESC, b.created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            most_read_book = dict(row) if row else None

            # 2.2 Highest rated book
            cursor.execute("""
                SELECT book_id, title, cover_image, rating
                FROM books
                WHERE is_visible = 1
                ORDER BY rating DESC, title ASC
                LIMIT 1
            """)
            row = cursor.fetchone()
            highest_rated_book = dict(row) if row else None

            # 2.3 Book with most endings unlocked by community
            cursor.execute("""
                SELECT b.book_id, b.title, b.cover_image, COUNT(DISTINCT ube.ending_id) as endings_count
                FROM books b
                LEFT JOIN book_endings be ON be.book_id = b.book_id
                LEFT JOIN user_book_endings ube ON be.ending_id = ube.ending_id
                WHERE b.is_visible = 1
                GROUP BY b.book_id
                ORDER BY endings_count DESC, b.created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            most_endings_book = dict(row) if row else None

            # Popularity ranking
            cursor.execute("""
                SELECT book_id, title, readers, total_visits
                FROM vw_book_popularity
                LIMIT 5
            """)
            top_books = [dict(r) for r in cursor.fetchall()]

            return {
                "total_users": total_users,
                "total_books": total_books,
                "total_reads": total_reads,
                "total_decisions": total_decisions,
                "total_endings_unlocked": total_endings_unlocked,
                "most_read_book": most_read_book,
                "highest_rated_book": highest_rated_book,
                "most_endings_book": most_endings_book,
                "top_books": top_books
            }
