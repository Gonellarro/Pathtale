#!/usr/bin/env python3
import hashlib
import os
import sys

def generate_hash_and_salt(password: str):
    # Generar 16 bytes aleatorios de Salt (32 caracteres hexadecimales)
    salt_hex = os.urandom(16).hex()
    
    # Generar el Hash PBKDF2-SHA256 con 100,000 iteraciones
    salt_bytes = bytes.fromhex(salt_hex)
    hash_hex = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000).hex()
    
    return salt_hex, hash_hex

def main():
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = input("🔑 Introduce la contraseña a cifrar: ").strip()

    if not password:
        print("❌ La contraseña no puede estar vacía.")
        sys.exit(1)

    salt, pwd_hash = generate_hash_and_salt(password)

    print("\n" + "=" * 65)
    print(f"🔐 CONTRASEÑA EN TEXTO PLANO: {password}")
    print("=" * 65)
    print(f"📌 salt          : {salt}")
    print(f"📌 password_hash : {pwd_hash}")
    print("=" * 65)
    print("\n📋 CONSULTA SQL PARA PEGAR EN SQLITE3 / DB BROWSER:")
    print("-" * 65)
    print(f"""UPDATE users 
SET password_hash = '{pwd_hash}',
    salt = '{salt}'
WHERE LOWER(username) = 'marti';""")
    print("-" * 65 + "\n")

if __name__ == "__main__":
    main()
