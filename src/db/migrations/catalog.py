"""Book catalogue and subscription schema."""

def apply(cursor):

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
            tier_id INTEGER NOT NULL DEFAULT 1,
            is_visible INTEGER NOT NULL DEFAULT 1,
            rating REAL DEFAULT 4.8,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (narrator_id) REFERENCES narrators(narrator_id) ON DELETE SET NULL
        )
    """)

    # Migrate databases created before book access-control fields existed.
    cursor.execute("PRAGMA table_info(books)")
    book_columns = {row["name"] for row in cursor.fetchall()}
    if "tier_id" not in book_columns:
        cursor.execute("ALTER TABLE books ADD COLUMN tier_id INTEGER NOT NULL DEFAULT 1")
    if "is_visible" not in book_columns:
        cursor.execute("ALTER TABLE books ADD COLUMN is_visible INTEGER NOT NULL DEFAULT 1")

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
