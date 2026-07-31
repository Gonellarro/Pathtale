from typing import Optional, Dict, Any, List
from src.db.base import BaseRepository

class BooksRepository(BaseRepository):
    def upsert_book(self, b: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO books (
                    book_id, title, author, publisher, year, language,
                    description, isbn, genre, series, volume,
                    estimated_duration, cover_image, total_sections, start_node, narrator_id, rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    title=excluded.title,
                    author=excluded.author,
                    publisher=excluded.publisher,
                    year=excluded.year,
                    language=excluded.language,
                    description=excluded.description,
                    isbn=excluded.isbn,
                    genre=excluded.genre,
                    series=excluded.series,
                    volume=excluded.volume,
                    estimated_duration=excluded.estimated_duration,
                    cover_image=excluded.cover_image,
                    total_sections=excluded.total_sections,
                    start_node=excluded.start_node,
                    narrator_id=excluded.narrator_id,
                    rating=excluded.rating
            """, (
                b.get("book_id"), b.get("title"), b.get("author"), b.get("publisher"),
                b.get("year"), b.get("language", "es"), b.get("description"), b.get("isbn"),
                b.get("genre"), b.get("series"), b.get("volume"), b.get("estimated_duration"),
                b.get("cover_image"), b.get("total_sections", 1), b.get("start_node", "sec_001"),
                b.get("narrator_id", 1), b.get("rating", 4.8)
            ))
            conn.commit()

    def get_all_books_admin(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, n.display_name as narrator_name, st.name as tier_name, st.code as tier_code
                FROM books b
                LEFT JOIN narrators n ON b.narrator_id = n.narrator_id
                LEFT JOIN subscription_tiers st ON b.tier_id = st.tier_id
                ORDER BY b.title ASC
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
                cursor.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
                cursor.execute("DELETE FROM savegames WHERE book_id = ?", (book_id,))
                cursor.execute("DELETE FROM reading_logs WHERE book_id = ?", (book_id,))
                cursor.execute("DELETE FROM book_endings WHERE book_id = ?", (book_id,))
            else:
                cursor.execute("UPDATE books SET is_visible = 0 WHERE book_id = ?", (book_id,))
            conn.commit()

    def get_top_tags(self, limit: int = 5) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT genre, series FROM books")
            rows = cursor.fetchall()
            tags_map = {}
            for r in rows:
                if r["genre"]:
                    for g in r["genre"].split(","):
                        g_clean = g.strip()
                        if g_clean:
                            tags_map[g_clean] = tags_map.get(g_clean, 0) + 1
                if r["series"]:
                    s_clean = r["series"].strip()
                    if s_clean:
                        tags_map[s_clean] = tags_map.get(s_clean, 0) + 1

            sorted_tags = sorted(tags_map.items(), key=lambda x: x[1], reverse=True)
            return [t[0] for t in sorted_tags[:limit]]

    def register_book_endings(self, book_id: str, endings: List[Dict[str, Any]]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM book_endings WHERE book_id = ?", (book_id,))
            for e in endings:
                node_id = e.get("node_id")
                label = e.get("label", "Final de la aventura")
                is_good = e.get("is_good_ending", None)
                if node_id:
                    cursor.execute("""
                        INSERT OR IGNORE INTO book_endings (book_id, node_id, label, is_good_ending)
                        VALUES (?, ?, ?, ?)
                    """, (book_id, node_id, label, is_good))
            conn.commit()
