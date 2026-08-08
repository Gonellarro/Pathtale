from config import DB_PATH
from src.db.base import BaseRepository
from src.db.schema import SchemaManager
from src.db.repositories.auth_repo import AuthRepository
from src.db.repositories.books_repo import BooksRepository
from src.db.repositories.narrators_repo import NarratorsRepository
from src.db.repositories.gameplay_repo import GameplayRepository
from src.db.repositories.analytics_repo import AnalyticsRepository

class Database(BaseRepository):
    """
    Unified Facade for PathTale Database Operations.
    Delegates domain-specific tasks to dedicated repositories while maintaining 100% backwards compatibility.
    """
    def __init__(self, db_path=DB_PATH):
        super().__init__(db_path)
        self.schema = SchemaManager(self.db_path)
        self.auth = AuthRepository(self.db_path)
        self.books = BooksRepository(self.db_path)
        self.narrators = NarratorsRepository(self.db_path)
        self.gameplay = GameplayRepository(self.db_path)
        self.analytics = AnalyticsRepository(self.db_path)
        
        # Initialize schema and seed default data
        self.init_db()

    def init_db(self):
        self.schema.init_db()

    # --- Auth & User Delegations ---
    def _hash_password(self, password: str, salt_hex: str):
        return self.auth._hash_password(password, salt_hex)

    def register_user(self, *args, **kwargs):
        return self.auth.register_user(*args, **kwargs)

    def login_user(self, *args, **kwargs):
        return self.auth.login_user(*args, **kwargs)

    def get_user_by_token(self, *args, **kwargs):
        return self.auth.get_user_by_token(*args, **kwargs)

    def get_session(self, *args, **kwargs):
        return self.auth.get_session(*args, **kwargs)

    def logout_user(self, *args, **kwargs):
        return self.auth.logout_user(*args, **kwargs)

    def get_user(self, *args, **kwargs):
        return self.auth.get_user(*args, **kwargs)

    def get_or_create_user(self, *args, **kwargs):
        return self.auth.get_or_create_user(*args, **kwargs)

    def get_all_subscription_tiers(self, *args, **kwargs):
        return self.auth.get_all_subscription_tiers(*args, **kwargs)

    def get_user_active_tier(self, *args, **kwargs):
        return self.auth.get_user_active_tier(*args, **kwargs)

    def assign_user_subscription(self, *args, **kwargs):
        return self.auth.assign_user_subscription(*args, **kwargs)

    def get_book_tier(self, *args, **kwargs):
        return self.auth.get_book_tier(*args, **kwargs)

    def get_all_users_admin(self, *args, **kwargs):
        return self.auth.get_all_users_admin(*args, **kwargs)

    def get_all_roles(self, *args, **kwargs):
        return self.auth.get_all_roles(*args, **kwargs)

    def create_user_admin(self, *args, **kwargs):
        return self.auth.create_user_admin(*args, **kwargs)

    def update_user_admin(self, *args, **kwargs):
        return self.auth.update_user_admin(*args, **kwargs)

    def delete_user_admin(self, *args, **kwargs):
        return self.auth.delete_user_admin(*args, **kwargs)

    def update_user_settings(self, *args, **kwargs):
        return self.auth.update_user_settings(*args, **kwargs)

    def get_user_settings(self, *args, **kwargs):
        return self.auth.get_user_settings(*args, **kwargs)

    # --- Books Delegations ---
    def upsert_book(self, *args, **kwargs):
        return self.books.upsert_book(*args, **kwargs)

    def get_all_books_admin(self, *args, **kwargs):
        return self.books.get_all_books_admin(*args, **kwargs)

    def get_book_by_id(self, *args, **kwargs):
        return self.books.get_book_by_id(*args, **kwargs)

    def update_book_admin(self, *args, **kwargs):
        return self.books.update_book_admin(*args, **kwargs)

    def get_user_book_rating(self, *args, **kwargs):
        return self.books.get_user_book_rating(*args, **kwargs)

    def set_user_book_rating(self, *args, **kwargs):
        return self.books.set_user_book_rating(*args, **kwargs)

    def get_book_rating_summary(self, *args, **kwargs):
        return self.books.get_book_rating_summary(*args, **kwargs)

    def delete_book_admin(self, *args, **kwargs):
        return self.books.delete_book_admin(*args, **kwargs)

    def get_top_tags(self, *args, **kwargs):
        return self.books.get_top_tags(*args, **kwargs)

    def register_book_endings(self, *args, **kwargs):
        return self.books.register_book_endings(*args, **kwargs)

    # --- Narrators Delegations ---
    def get_all_tts_engines(self, *args, **kwargs):
        return self.narrators.get_all_tts_engines(*args, **kwargs)

    def get_narrators_stats(self, *args, **kwargs):
        return self.narrators.get_narrators_stats(*args, **kwargs)

    def get_narrator_by_id(self, *args, **kwargs):
        return self.narrators.get_narrator_by_id(*args, **kwargs)

    def create_narrator_admin(self, *args, **kwargs):
        return self.narrators.create_narrator_admin(*args, **kwargs)

    def update_narrator_admin(self, *args, **kwargs):
        return self.narrators.update_narrator_admin(*args, **kwargs)

    def delete_narrator_admin(self, *args, **kwargs):
        return self.narrators.delete_narrator_admin(*args, **kwargs)

    # --- Gameplay Delegations ---
    def get_savegame(self, *args, **kwargs):
        return self.gameplay.get_savegame(*args, **kwargs)

    def get_last_active_game(self, *args, **kwargs):
        return self.gameplay.get_last_active_game(*args, **kwargs)

    def get_in_progress_games(self, *args, **kwargs):
        return self.gameplay.get_in_progress_games(*args, **kwargs)

    def save_game(self, *args, **kwargs):
        return self.gameplay.save_game(*args, **kwargs)

    def touch_savegame(self, *args, **kwargs):
        return self.gameplay.touch_savegame(*args, **kwargs)

    def save_playback_position(self, *args, **kwargs):
        return self.gameplay.save_playback_position(*args, **kwargs)

    def record_step(self, *args, **kwargs):
        return self.gameplay.record_step(*args, **kwargs)

    def get_history(self, *args, **kwargs):
        return self.gameplay.get_history(*args, **kwargs)

    def record_ending_reached(self, *args, **kwargs):
        return self.gameplay.record_ending_reached(*args, **kwargs)

    # --- Analytics & Audit Delegations ---
    def log_audit_event(self, *args, **kwargs):
        return self.analytics.log_audit_event(*args, **kwargs)

    def get_reading_logs_admin(self, *args, **kwargs):
        return self.analytics.get_reading_logs_admin(*args, **kwargs)

    def get_user_stats(self, *args, **kwargs):
        return self.analytics.get_user_stats(*args, **kwargs)

    def get_user_stats_detailed(self, *args, **kwargs):
        return self.analytics.get_user_stats_detailed(*args, **kwargs)

    def get_global_stats(self, *args, **kwargs):
        return self.analytics.get_global_stats(*args, **kwargs)
