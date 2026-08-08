"""Gameplay, analytics and history schema."""

def apply(cursor):

    # 8. Savegames table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS savegames (
            save_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id TEXT NOT NULL,
            current_node_id TEXT NOT NULL,
            inventory TEXT DEFAULT '[]',
            variables TEXT DEFAULT '{}',
            playback_node_id TEXT,
            playback_position_seconds REAL NOT NULL DEFAULT 0,
            playback_captured_at_ms INTEGER NOT NULL DEFAULT 0,
            playback_updated_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE,
            UNIQUE (user_id, book_id)
        )
    """)

    # Playback bookmark was added after the original savegame schema.
    # Keep this migration additive so existing libraries remain intact.
    cursor.execute("PRAGMA table_info(savegames)")
    savegame_columns = {row["name"] for row in cursor.fetchall()}
    for col, definition in [
        ("playback_node_id", "TEXT"),
        ("playback_position_seconds", "REAL NOT NULL DEFAULT 0"),
        ("playback_captured_at_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("playback_updated_at", "TIMESTAMP"),
    ]:
        if col not in savegame_columns:
            cursor.execute(f"ALTER TABLE savegames ADD COLUMN {col} {definition}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_book_ratings (
            user_id INTEGER NOT NULL,
            book_id TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
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
