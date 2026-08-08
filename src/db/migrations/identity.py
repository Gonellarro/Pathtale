"""Identity, session and narrator schema."""

def apply(cursor):

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
