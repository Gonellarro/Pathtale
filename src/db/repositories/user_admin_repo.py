"""Administrative user and role operations."""

import os
from typing import Any, Dict, List, Optional

from src.db.base import BaseRepository
from src.db.repositories.passwords import hash_password


class UserAdminRepository(BaseRepository):
    def get_all_users_admin(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT u.user_id, u.username, u.first_name, u.created_at, u.tier_id, u.role_id,
                       r.name AS role, st.name AS tier_name, st.code AS tier_code
                FROM users u LEFT JOIN roles r ON u.role_id = r.role_id
                LEFT JOIN subscription_tiers st ON u.tier_id = st.tier_id ORDER BY u.user_id ASC
            """).fetchall()
            return [dict(row) for row in rows]

    def get_all_roles(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM roles ORDER BY role_id ASC").fetchall()]

    def create_user_admin(self, username: str, password: str, first_name: Optional[str] = None,
                          role: str = "user", tier_id: int = 1) -> Dict[str, Any]:
        username = username.strip().lower()
        if len(username) < 3:
            raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
        if len(password) < 4:
            raise ValueError("La contraseña debe tener al menos 4 caracteres.")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if cursor.execute("SELECT 1 FROM users WHERE LOWER(username) = ?", (username,)).fetchone():
                raise ValueError(f"El usuario '@{username}' ya existe.")
            role_row = cursor.execute("SELECT role_id FROM roles WHERE name = ?", (role,)).fetchone()
            salt = os.urandom(16).hex()
            cursor.execute("""
                INSERT INTO users (username, first_name, password_hash, salt, role_id, tier_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, first_name.strip() if first_name else username, hash_password(password, salt), salt,
                  role_row["role_id"] if role_row else 2, tier_id))
            conn.commit()
            return {"user_id": cursor.lastrowid, "username": username,
                    "first_name": first_name.strip() if first_name else username, "role": role, "tier_id": tier_id}

    def update_user_admin(self, user_id: int, first_name: Optional[str] = None, role: Optional[str] = None,
                          password: Optional[str] = None, tier_id: Optional[int] = None) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if first_name is not None:
                cursor.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (first_name, user_id))
            if role is not None:
                role_row = cursor.execute("SELECT role_id FROM roles WHERE name = ?", (role,)).fetchone()
                if role_row:
                    cursor.execute("UPDATE users SET role_id = ? WHERE user_id = ?", (role_row["role_id"], user_id))
            if tier_id is not None:
                cursor.execute("UPDATE users SET tier_id = ? WHERE user_id = ?", (tier_id, user_id))
            if password and len(password) >= 4:
                salt = os.urandom(16).hex()
                cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE user_id = ?",
                               (hash_password(password, salt), salt, user_id))
            conn.commit()

    def delete_user_admin(self, user_id: int, hard_delete: bool = False) -> None:
        if user_id == 1:
            raise ValueError("No se puede eliminar el usuario administrador principal (ID 1).")
        with self.get_connection() as conn:
            if hard_delete:
                conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            else:
                conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.commit()
