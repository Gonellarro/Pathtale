"""Registration, login and session persistence."""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from config import SESSION_EXPIRE_DAYS
from src.db.base import BaseRepository
from src.db.repositories.passwords import hash_password


class IdentityRepository(BaseRepository):
    def _new_session(self, cursor, user_id: int) -> str:
        token = secrets.token_hex(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        columns = {column["name"] for column in cursor.execute("PRAGMA table_info(sessions)").fetchall()}
        if "expires_at" in columns:
            cursor.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
        else:
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
        return token

    @staticmethod
    def _validate_credentials(username: str, password: str) -> tuple[str, str]:
        clean_username = username.strip().lower()
        if len(clean_username) < 3:
            raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
        if len(password) < 4:
            raise ValueError("La contraseña debe tener al menos 4 caracteres.")
        return clean_username, password

    def register_user(self, username: str, password: str, first_name: Optional[str] = None) -> Dict[str, Any]:
        username, password = self._validate_credentials(username, password)
        display_name = first_name.strip() if first_name else username
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username,)).fetchone():
                raise ValueError("El nombre de usuario ya está registrado.")
            salt = os.urandom(16).hex()
            cursor.execute(
                "INSERT INTO users (username, first_name, password_hash, salt, role_id) VALUES (?, ?, ?, ?, 2)",
                (username, display_name, hash_password(password, salt), salt),
            )
            user_id = cursor.lastrowid
            token = self._new_session(cursor, user_id)
            conn.commit()
            return {"user_id": user_id, "username": username, "first_name": display_name,
                    "role": "user", "role_name": "user", "token": token}

    def login_user(self, username: str, password: str) -> Dict[str, Any]:
        username = username.strip().lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            user = cursor.execute("""
                SELECT u.*, r.name AS role_name FROM users u
                LEFT JOIN roles r ON u.role_id = r.role_id WHERE LOWER(u.username) = ?
            """, (username,)).fetchone()
            if not user or not user["password_hash"] or not user["salt"] or user["is_active"] == 0:
                raise ValueError("Usuario o contraseña incorrectos.")
            if hash_password(password, user["salt"]) != user["password_hash"]:
                raise ValueError("Usuario o contraseña incorrectos.")
            token = self._new_session(cursor, user["user_id"])
            conn.commit()
            role = user["role_name"] or "user"
            return {"user_id": user["user_id"], "username": user["username"],
                    "first_name": user["first_name"] or user["username"],
                    "role": role, "role_name": role, "token": token}

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            session_columns = {column["name"] for column in cursor.execute("PRAGMA table_info(sessions)").fetchall()}
            expiry_select = ", s.expires_at" if "expires_at" in session_columns else ""
            row = cursor.execute("""
                SELECT u.*, s.created_at AS session_created_at%s, r.name AS role_name
                FROM sessions s JOIN users u ON s.user_id = u.user_id
                LEFT JOIN roles r ON u.role_id = r.role_id WHERE s.token = ?
            """ % expiry_select, (token,)).fetchone()
            if not row:
                return None
            user = dict(row)
            if user.get("is_active") == 0:
                return None
            expires_at = user.get("expires_at")
            if expires_at:
                try:
                    expired = datetime.now(timezone.utc) > datetime.strptime(str(expires_at), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                except ValueError:
                    expired = False
                if expired:
                    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
                    conn.commit()
                    return None
            role = user.get("role_name") or "user"
            return {"user_id": user["user_id"], "username": user["username"],
                    "first_name": user.get("first_name") or user["username"], "role": role,
                    "role_name": role, "settings": json.loads(user.get("settings") or "{}"),
                    "created_at": user.get("created_at")}

    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
            return dict(row) if row else None

    def logout_user(self, token: str) -> None:
        if token:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT u.*, r.name AS role_name FROM users u
                LEFT JOIN roles r ON u.role_id = r.role_id WHERE u.user_id = ?
            """, (user_id,)).fetchone()
            if not row:
                return None
            user = dict(row)
            user["settings"] = json.loads(user.get("settings") or "{}")
            user["role"] = user.get("role_name") or "user"
            return user

    def get_or_create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> None:
        with self.get_connection() as conn:
            if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone():
                name = username or f"user_{user_id}"
                conn.execute("INSERT INTO users (user_id, username, first_name, role_id) VALUES (?, ?, ?, 2)",
                             (user_id, name, first_name or name))
                conn.commit()
