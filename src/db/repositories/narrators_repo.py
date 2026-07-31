from typing import Optional, Dict, Any, List
from src.db.base import BaseRepository

class NarratorsRepository(BaseRepository):
    def get_narrators_stats(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT n.*, COUNT(b.book_id) as book_count
                FROM narrators n
                LEFT JOIN books b ON b.narrator_id = n.narrator_id
                GROUP BY n.narrator_id
                ORDER BY n.narrator_id ASC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def create_narrator_admin(self, name: str, display_name: str, specialty: Optional[str] = None, avatar_url: Optional[str] = None, bio: Optional[str] = None) -> Dict[str, Any]:
        name_clean = name.strip()
        display_clean = display_name.strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT narrator_id FROM narrators WHERE LOWER(name) = ?", (name_clean.lower(),))
            if cursor.fetchone():
                raise ValueError(f"Ya existe un narrador con el nombre '{name_clean}'.")

            cursor.execute("""
                INSERT INTO narrators (name, display_name, specialty, avatar_url, bio)
                VALUES (?, ?, ?, ?, ?)
            """, (name_clean, display_clean, specialty, avatar_url, bio))
            narrator_id = cursor.lastrowid
            conn.commit()
            return {
                "narrator_id": narrator_id,
                "name": name_clean,
                "display_name": display_clean,
                "specialty": specialty,
                "avatar_url": avatar_url,
                "bio": bio
            }

    def update_narrator_admin(self, narrator_id: int, display_name: Optional[str] = None, specialty: Optional[str] = None, avatar_url: Optional[str] = None, bio: Optional[str] = None):
        fields = []
        values = []
        if display_name is not None:
            fields.append("display_name = ?")
            values.append(display_name.strip())
        if specialty is not None:
            fields.append("specialty = ?")
            values.append(specialty.strip())
        if avatar_url is not None:
            fields.append("avatar_url = ?")
            values.append(avatar_url.strip())
        if bio is not None:
            fields.append("bio = ?")
            values.append(bio.strip())

        if not fields:
            return

        values.append(narrator_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE narrators SET {', '.join(fields)} WHERE narrator_id = ?", values)
            conn.commit()

    def delete_narrator_admin(self, narrator_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as c FROM books WHERE narrator_id = ?", (narrator_id,))
            if cursor.fetchone()["c"] > 0:
                raise ValueError("No se puede eliminar un narrador asignado a audiolibros activos.")

            cursor.execute("DELETE FROM narrators WHERE narrator_id = ?", (narrator_id,))
            conn.commit()
