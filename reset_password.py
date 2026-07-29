#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from src.db import Database

def main():
    if len(sys.argv) < 3:
        print("❌ Uso: python3 reset_password.py <usuario_o_id> <nueva_contraseña>")
        print("💡 Ejemplo: python3 reset_password.py marti mi_nueva_clave123")
        sys.exit(1)

    target = sys.argv[1].strip().lower()
    new_password = sys.argv[2]

    if len(new_password) < 4:
        print("❌ Error: La contraseña debe tener al menos 4 caracteres.")
        sys.exit(1)

    db = Database()

    # Resolve user ID
    user_id = None
    if target.isdigit():
        user_id = int(target)
    else:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM users WHERE LOWER(username) = ?", (target,))
            row = cursor.fetchone()
            if row:
                user_id = row["user_id"]

    if not user_id:
        if target in ("marti", "admin"):
            user_id = 1
        else:
            print(f"❌ Error: No se encontró el usuario '{target}'.")
            sys.exit(1)

    db.update_user_admin(user_id, password=new_password)
    print(f"✅ ¡Contraseña para el usuario (ID #{user_id}) actualizada correctamente!")

if __name__ == "__main__":
    main()
