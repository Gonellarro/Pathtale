import os
import hashlib
from src.db.base import BaseRepository
from config import ADMIN_USERNAME, ADMIN_PASSWORD

class SchemaManager(BaseRepository):
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
                    tier_id INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    settings TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE RESTRICT,
                    FOREIGN KEY (tier_id) REFERENCES subscription_tiers(tier_id) ON DELETE RESTRICT
                )
            """)

            # Migration check for tier_id column if users table existed without it
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN tier_id INTEGER DEFAULT 1")
            except Exception:
                pass

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

            # 3b. TTS Engines table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tts_engines (
                    engine_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    engine_type TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("INSERT OR IGNORE INTO tts_engines (engine_id, code, name, engine_type, description) VALUES (1, 'piper', 'Piper Local C++ Engine', 'local_onnx', 'Síntesis local de alta velocidad sin costes ni latencia de red')")
            cursor.execute("INSERT OR IGNORE INTO tts_engines (engine_id, code, name, engine_type, description) VALUES (2, 'google', 'Google Cloud Text-to-Speech API', 'cloud_api', 'Síntesis en la nube con voces neuronales Neural2 de máxima calidad')")

            # 4. Narrators table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS narrators (
                    narrator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    engine_id INTEGER NOT NULL DEFAULT 1,
                    voice_code TEXT NOT NULL DEFAULT 'es_ES-davefx-medium.onnx',
                    language TEXT DEFAULT 'es',
                    gender TEXT DEFAULT 'male',
                    specialty TEXT,
                    avatar_url TEXT,
                    download_url TEXT,
                    model_filename TEXT,
                    sample_audio_url TEXT,
                    bio TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (engine_id) REFERENCES tts_engines(engine_id) ON DELETE RESTRICT
                )
            """)

            # Add missing columns if narrators table pre-existed
            for col, d_type in [
                ("engine_id", "INTEGER DEFAULT 1"),
                ("voice_code", "TEXT DEFAULT 'es_ES-davefx-medium.onnx'"),
                ("language", "TEXT DEFAULT 'es'"),
                ("gender", "TEXT DEFAULT 'male'"),
                ("download_url", "TEXT"),
                ("model_filename", "TEXT"),
                ("sample_audio_url", "TEXT"),
                ("is_active", "INTEGER DEFAULT 1")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE narrators ADD COLUMN {col} {d_type}")
                except Exception:
                    pass

            # Seed / update default narrators
            cursor.execute("SELECT COUNT(*) as c FROM narrators")
            if cursor.fetchone()["c"] <= 2:
                cursor.execute("DELETE FROM narrators")
                cursor.execute("""
                    INSERT INTO narrators (narrator_id, name, display_name, engine_id, voice_code, language, gender, specialty, avatar_url, download_url, model_filename) VALUES 
                    (1, 'piper_davefx', 'DAVEFX (Piper Local)', 1, 'es_ES-davefx-medium.onnx', 'es', 'male', 'Español · Épico / Fantasía', '/assets/narrator_davefx.jpg', 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx', 'es_ES-davefx-medium.onnx'),
                    (2, 'piper_lessac', 'LESSAC (Piper Local)', 1, 'en_US-lessac-medium.onnx', 'en', 'female', 'Inglés · Drama y Aventuras', '/assets/narrator_lessac.jpg', 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx', 'en_US-lessac-medium.onnx'),
                    (3, 'google_es_neural2_b', 'DIEGO (Google Neural2)', 2, 'es-ES-Neural2-B', 'es', 'male', 'Español · Voz Masculina Épica', '/assets/narrator_davefx.jpg', NULL, NULL),
                    (4, 'google_es_neural2_a', 'CARMEN (Google Neural2)', 2, 'es-ES-Neural2-A', 'es', 'female', 'Español · Voz Femenina Narrativa', '/assets/narrator_lessac.jpg', NULL, NULL),
                    (5, 'google_en_neural2_f', 'SARAH (Google Neural2)', 2, 'en-US-Neural2-F', 'en', 'female', 'Inglés · Voice Over Profesional', '/assets/narrator_lessac.jpg', NULL, NULL)
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

            # 8. Savegames table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS savegames (
                    save_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    current_node_id TEXT NOT NULL,
                    inventory TEXT DEFAULT '[]',
                    variables TEXT DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE,
                    UNIQUE (user_id, book_id)
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
                salt_bytes = bytes.fromhex(salt_hex)
                pwd_hash = hashlib.pbkdf2_hmac('sha256', ADMIN_PASSWORD.encode('utf-8'), salt_bytes, 100000).hex()
                admin_name = ADMIN_USERNAME.strip().lower()
                display_name = ADMIN_USERNAME.strip().capitalize()
                cursor.execute(
                    "INSERT INTO users (username, first_name, password_hash, salt, role_id) VALUES (?, ?, ?, ?, 1)",
                    (admin_name, display_name, pwd_hash, salt_hex)
                )

            conn.commit()
