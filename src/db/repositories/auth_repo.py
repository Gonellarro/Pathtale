import hashlib
import os
import secrets
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from src.db.base import BaseRepository
from config import SESSION_EXPIRE_DAYS

class AuthRepository(BaseRepository):
    def _hash_password(self, password: str, salt_hex: str) -> str:
        salt_bytes = bytes.fromhex(salt_hex)
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000).hex()

    def register_user(self, username: str, password: str, first_name: Optional[str] = None) -> Dict[str, Any]:
        username_clean = username.strip().lower()
        display_name = first_name.strip() if first_name else username_clean

        if len(username_clean) < 3:
            raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
        if len(password) < 4:
            raise ValueError("La contraseña debe tener al menos 4 caracteres.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username_clean,))
            if cursor.fetchone():
                raise ValueError("El nombre de usuario ya está registrado.")

            salt_hex = os.urandom(16).hex()
            pwd_hash = self._hash_password(password, salt_hex)

            cursor.execute(
                "INSERT INTO users (username, first_name, password_hash, salt, role_id) VALUES (?, ?, ?, ?, 2)",
                (username_clean, display_name, pwd_hash, salt_hex)
            )
            user_id = cursor.lastrowid
            token = secrets.token_hex(32)
            expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            session_cols = [c["name"] for c in cursor.execute("PRAGMA table_info(sessions)").fetchall()]
            if "expires_at" in session_cols:
                cursor.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
            else:
                cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
            conn.commit()

            return {
                "user_id": user_id,
                "username": username_clean,
                "first_name": display_name,
                "role": "user",
                "role_name": "user",
                "token": token
            }

    def login_user(self, username: str, password: str) -> Dict[str, Any]:
        username_clean = username.strip().lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, r.name as role_name 
                FROM users u 
                LEFT JOIN roles r ON u.role_id = r.role_id 
                WHERE LOWER(u.username) = ?
            """, (username_clean,))
            user = cursor.fetchone()
            if not user or not user["password_hash"] or not user["salt"]:
                raise ValueError("Usuario o contraseña incorrectos.")

            if dict(user).get("is_active") == 0:
                raise ValueError("Esta cuenta de usuario ha sido desactivada.")

            computed_hash = self._hash_password(password, user["salt"])
            if computed_hash != user["password_hash"]:
                raise ValueError("Usuario o contraseña incorrectos.")

            token = secrets.token_hex(32)
            expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            session_cols = [c["name"] for c in cursor.execute("PRAGMA table_info(sessions)").fetchall()]
            if "expires_at" in session_cols:
                cursor.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user["user_id"], expires_at))
            else:
                cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["user_id"]))
            conn.commit()

            role_val = user["role_name"] or "user"
            return {
                "user_id": user["user_id"],
                "username": user["username"],
                "first_name": user["first_name"] or user["username"],
                "role": role_val,
                "role_name": role_val,
                "token": token
            }

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, s.created_at as session_created_at, r.name as role_name
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                LEFT JOIN roles r ON u.role_id = r.role_id
                WHERE s.token = ?
            """, (token,))
            row = cursor.fetchone()
            if not row:
                return None

            row_dict = dict(row)
            if row_dict.get("is_active") == 0:
                return None

            expires_at = row_dict.get("expires_at")
            if expires_at:
                try:
                    exp_dt = datetime.strptime(str(expires_at), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > exp_dt:
                        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
                        conn.commit()
                        return None
                except Exception:
                    pass

            role_val = row_dict.get("role_name") or "user"
            return {
                "user_id": row_dict["user_id"],
                "username": row_dict["username"],
                "first_name": row_dict.get("first_name") or row_dict["username"],
                "role": role_val,
                "role_name": role_val,
                "settings": json.loads(row_dict.get("settings") or "{}"),
                "created_at": row_dict.get("created_at")
            }

    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE token = ?", (token,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def logout_user(self, token: str):
        if not token:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, r.name as role_name 
                FROM users u 
                LEFT JOIN roles r ON u.role_id = r.role_id 
                WHERE u.user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["settings"] = json.loads(res.get("settings") or "{}")
            res["role"] = res.get("role_name") or "user"
            return res

    def get_or_create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                uname = username or f"user_{user_id}"
                fname = first_name or uname
                cursor.execute(
                    "INSERT INTO users (user_id, username, first_name, role_id) VALUES (?, ?, ?, 2)",
                    (user_id, uname, fname)
                )
                conn.commit()

    def get_all_subscription_tiers(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscription_tiers ORDER BY level ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_user_active_tier(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT st.* FROM subscription_tiers st
                JOIN users u ON u.tier_id = st.tier_id
                WHERE u.user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0}

    def assign_user_subscription(self, user_id: int, tier_id: int, duration_days: Optional[int] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET tier_id = ? WHERE user_id = ?", (tier_id, user_id))
            conn.commit()

    def get_book_tier(self, book_id: str) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT st.* FROM subscription_tiers st
                JOIN books b ON b.tier_id = st.tier_id
                WHERE b.book_id = ?
            """, (book_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0}

    def get_all_users_admin(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.created_at, u.tier_id, u.role_id, r.name as role, st.name as tier_name, st.code as tier_code
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.role_id
                LEFT JOIN subscription_tiers st ON u.tier_id = st.tier_id
                ORDER BY u.user_id ASC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_all_roles(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM roles ORDER BY role_id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def create_user_admin(self, username: str, password: str, first_name: Optional[str] = None, role: str = "user", tier_id: int = 1) -> Dict[str, Any]:
        username_clean = username.strip().lower()
        display_name = first_name.strip() if first_name else username_clean
        if len(username_clean) < 3:
            raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
        if len(password) < 4:
            raise ValueError("La contraseña debe tener al menos 4 caracteres.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username_clean,))
            if cursor.fetchone():
                raise ValueError(f"El usuario '@{username_clean}' ya existe.")

            cursor.execute("SELECT role_id FROM roles WHERE name = ?", (role,))
            role_row = cursor.fetchone()
            role_id = role_row["role_id"] if role_row else 2

            salt_hex = os.urandom(16).hex()
            pwd_hash = self._hash_password(password, salt_hex)

            cursor.execute("""
                INSERT INTO users (username, first_name, password_hash, salt, role_id, tier_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username_clean, display_name, pwd_hash, salt_hex, role_id, tier_id))
            user_id = cursor.lastrowid
            conn.commit()

            return {
                "user_id": user_id,
                "username": username_clean,
                "first_name": display_name,
                "role": role,
                "tier_id": tier_id
            }

    def update_user_admin(self, user_id: int, first_name: Optional[str] = None, role: Optional[str] = None, password: Optional[str] = None, tier_id: Optional[int] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if first_name is not None:
                cursor.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (first_name, user_id))
            if role is not None:
                cursor.execute("SELECT role_id FROM roles WHERE name = ?", (role,))
                role_row = cursor.fetchone()
                if role_row:
                    cursor.execute("UPDATE users SET role_id = ? WHERE user_id = ?", (role_row["role_id"], user_id))
            if tier_id is not None:
                cursor.execute("UPDATE users SET tier_id = ? WHERE user_id = ?", (tier_id, user_id))
            if password and len(password) >= 4:
                salt_hex = os.urandom(16).hex()
                pwd_hash = self._hash_password(password, salt_hex)
                cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE user_id = ?", (pwd_hash, salt_hex, user_id))
            conn.commit()

    def delete_user_admin(self, user_id: int, hard_delete: bool = False):
        if user_id == 1:
            raise ValueError("No se puede eliminar el usuario administrador principal (ID 1).")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if hard_delete:
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.commit()

    def update_user_settings(self, user_id: int, settings: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            settings_json = json.dumps(settings)
            cursor.execute("UPDATE users SET settings = ? WHERE user_id = ?", (settings_json, user_id))
            conn.commit()

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        user = self.get_user(user_id)
        if user and "settings" in user:
            return user["settings"]
        return {}
