"""Schema coordinator.

Each migration domain owns its SQL in ``src.db.migrations``.  This class only
defines their stable execution order and transaction boundary.
"""

from src.db.base import BaseRepository
from src.db.migrations import bootstrap, catalog, gameplay, identity


class SchemaManager(BaseRepository):
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            identity.apply(cursor)
            catalog.apply(cursor)
            gameplay.apply(cursor)
            bootstrap.apply(cursor)
            conn.commit()
