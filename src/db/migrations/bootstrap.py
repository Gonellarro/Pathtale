"""Initial administrator bootstrap."""
import hashlib
import os

from config import ADMIN_PASSWORD, ADMIN_USERNAME

def apply(cursor):
    # Seed initial Admin user if no admin account exists in the database
    cursor.execute("""
        SELECT COUNT(*) as c FROM users u
        JOIN roles r ON u.role_id = r.role_id
        WHERE r.name = 'admin'
    """)
    admin_row = cursor.fetchone()
    if not admin_row or admin_row["c"] == 0:
        salt_hex = os.urandom(16).hex()
        salt_bytes = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', ADMIN_PASSWORD.encode('utf-8'), salt_bytes, 100000).hex()
        admin_name = ADMIN_USERNAME.strip().lower()
        display_name = ADMIN_USERNAME.strip().capitalize()
        cursor.execute(
            "INSERT INTO users (username, first_name, password_hash, salt, role_id) VALUES (?, ?, ?, ?, 1)",
            (admin_name, display_name, pwd_hash, salt_hex)
        )
