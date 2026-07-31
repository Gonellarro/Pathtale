import sqlite3
from config import DB_PATH

class BaseRepository:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
