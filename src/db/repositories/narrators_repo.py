from typing import Optional, Dict, Any, List
from src.db.base import BaseRepository

class NarratorsRepository(BaseRepository):
    def get_all_tts_engines(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tts_engines WHERE is_active = 1 ORDER BY engine_id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_narrators_stats(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    n.*, 
                    e.code as engine_code,
                    e.name as engine_name,
                    e.engine_type,
                    COUNT(b.book_id) as book_count
                FROM narrators n
                JOIN tts_engines e ON n.engine_id = e.engine_id
                LEFT JOIN books b ON b.narrator_id = n.narrator_id
                WHERE n.is_active = 1
                GROUP BY n.narrator_id
                ORDER BY n.narrator_id ASC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_narrator_by_id(self, narrator_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT n.*, e.code as engine_code, e.name as engine_name, e.engine_type
                FROM narrators n
                JOIN tts_engines e ON n.engine_id = e.engine_id
                WHERE n.narrator_id = ?
            """, (narrator_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_narrator_admin(
        self,
        name: str,
        display_name: str,
        engine_id: int = 1,
        voice_code: str = "default",
        language: str = "es",
        gender: str = "male",
        specialty: Optional[str] = None,
        avatar_url: Optional[str] = None,
        download_url: Optional[str] = None,
        model_filename: Optional[str] = None,
        bio: Optional[str] = None
    ) -> Dict[str, Any]:
        name_clean = name.strip()
        display_clean = display_name.strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT narrator_id FROM narrators WHERE LOWER(name) = ?", (name_clean.lower(),))
            if cursor.fetchone():
                raise ValueError(f"Ya existe un narrador con el nombre o identificador '{name_clean}'.")

            cursor.execute("""
                INSERT INTO narrators (
                    name, display_name, engine_id, voice_code, language, gender,
                    specialty, avatar_url, download_url, model_filename, bio
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name_clean, display_clean, engine_id, voice_code, language, gender,
                specialty, avatar_url, download_url, model_filename, bio
            ))
            narrator_id = cursor.lastrowid
            conn.commit()
            return self.get_narrator_by_id(narrator_id)

    def update_narrator_admin(
        self,
        narrator_id: int,
        display_name: Optional[str] = None,
        engine_id: Optional[int] = None,
        voice_code: Optional[str] = None,
        language: Optional[str] = None,
        gender: Optional[str] = None,
        specialty: Optional[str] = None,
        avatar_url: Optional[str] = None,
        download_url: Optional[str] = None,
        model_filename: Optional[str] = None,
        bio: Optional[str] = None
    ):
        fields = []
        values = []
        if display_name is not None:
            fields.append("display_name = ?")
            values.append(display_name.strip())
        if engine_id is not None:
            fields.append("engine_id = ?")
            values.append(engine_id)
        if voice_code is not None:
            fields.append("voice_code = ?")
            values.append(voice_code.strip())
        if language is not None:
            fields.append("language = ?")
            values.append(language.strip())
        if gender is not None:
            fields.append("gender = ?")
            values.append(gender.strip())
        if specialty is not None:
            fields.append("specialty = ?")
            values.append(specialty.strip())
        if avatar_url is not None:
            fields.append("avatar_url = ?")
            values.append(avatar_url.strip())
        if download_url is not None:
            fields.append("download_url = ?")
            values.append(download_url.strip())
        if model_filename is not None:
            fields.append("model_filename = ?")
            values.append(model_filename.strip())
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
