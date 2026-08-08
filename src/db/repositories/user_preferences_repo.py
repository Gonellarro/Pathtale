"""Per-user application preferences."""

import json
from typing import Any, Dict

from src.db.base import BaseRepository


class UserPreferencesRepository(BaseRepository):
    def update_user_settings(self, user_id: int, settings: Dict[str, Any]) -> None:
        with self.get_connection() as conn:
            conn.execute("UPDATE users SET settings = ? WHERE user_id = ?", (json.dumps(settings), user_id))
            conn.commit()

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT settings FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return json.loads(row["settings"] or "{}") if row else {}
