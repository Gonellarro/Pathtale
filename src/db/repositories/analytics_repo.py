from typing import Optional, Dict, Any, List
from src.db.base import BaseRepository

class AnalyticsRepository(BaseRepository):
    def log_audit_event(self, user_id: int, action_type: str, book_id: Optional[str] = None, node_id: Optional[str] = None, detail: str = ''):
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

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT book_id) as books_started FROM savegames WHERE user_id = ?", (user_id,))
            books_started = cursor.fetchone()["books_started"]

            cursor.execute("SELECT COUNT(*) as decisions_made FROM history WHERE user_id = ?", (user_id,))
            decisions_made = cursor.fetchone()["decisions_made"]

            cursor.execute("SELECT COUNT(DISTINCT ending_id) as endings_reached FROM user_book_endings WHERE user_id = ?", (user_id,))
            endings_reached = cursor.fetchone()["endings_reached"]

            return {
                "books_started": books_started,
                "decisions_made": decisions_made,
                "endings_reached": endings_reached
            }

    def get_user_stats_detailed(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            basic_stats = self.get_user_stats(user_id)

            cursor.execute("""
                SELECT COUNT(DISTINCT p.book_id) as books_completed
                FROM vw_user_book_progress p
                WHERE p.user_id = ? AND p.completed = 1
            """, (user_id,))
            row_comp = cursor.fetchone()
            books_completed = row_comp["books_completed"] if row_comp else 0

            cursor.execute("""
                SELECT
                    b.book_id,
                    b.title,
                    b.cover_image,
                    b.total_sections,
                    COALESCE(p.sections_read, 0) as sections_read,
                    ROUND(MIN(100.0, (CAST(COALESCE(p.sections_read, 0) AS REAL) / MAX(1, b.total_sections)) * 100.0), 1) as progress_percent,
                    (SELECT COUNT(DISTINCT be.ending_id) FROM book_endings be WHERE be.book_id = b.book_id) as total_endings,
                    (SELECT COUNT(DISTINCT ube.ending_id) 
                     FROM user_book_endings ube 
                     JOIN book_endings be ON be.ending_id = ube.ending_id 
                     WHERE be.book_id = b.book_id AND ube.user_id = ?) as endings_reached
                FROM savegames s
                JOIN books b ON b.book_id = s.book_id
                LEFT JOIN vw_user_book_progress p ON p.book_id = s.book_id AND p.user_id = s.user_id
                WHERE s.user_id = ?
                ORDER BY s.updated_at DESC
            """, (user_id, user_id))
            progress_rows = [dict(r) for r in cursor.fetchall()]

            return {
                "user_id": user_id,
                "books_started": basic_stats["books_started"],
                "books_completed": books_completed,
                "decisions_made": basic_stats["decisions_made"],
                "endings_reached": basic_stats["endings_reached"],
                "books_progress": progress_rows
            }

    def get_global_stats(self) -> Dict[str, Any]:
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

            cursor.execute("""
                SELECT b.book_id, b.title, b.cover_image, COUNT(rl.log_id) as total_visits
                FROM books b
                LEFT JOIN reading_logs rl ON rl.book_id = b.book_id AND rl.action_type = 'node_visit'
                WHERE b.is_visible = 1
                GROUP BY b.book_id
                ORDER BY total_visits DESC, b.created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            most_read_book = dict(row) if row else None

            cursor.execute("""
                SELECT book_id, title, cover_image, rating
                FROM books
                WHERE is_visible = 1
                ORDER BY rating DESC, created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            highest_rated_book = dict(row) if row else None

            cursor.execute("""
                SELECT b.book_id, b.title, b.cover_image, COUNT(DISTINCT ube.id) as endings_count
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
