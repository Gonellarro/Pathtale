"""Subscription tiers and access-level lookup."""

from typing import Any, Dict, List, Optional

from src.db.base import BaseRepository


class SubscriptionRepository(BaseRepository):
    def get_all_subscription_tiers(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM subscription_tiers ORDER BY level ASC").fetchall()]

    def get_user_active_tier(self, user_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT st.* FROM subscription_tiers st JOIN users u ON u.tier_id = st.tier_id
                WHERE u.user_id = ?
            """, (user_id,)).fetchone()
            return dict(row) if row else {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0}

    def assign_user_subscription(self, user_id: int, tier_id: int, duration_days: Optional[int] = None) -> None:
        with self.get_connection() as conn:
            conn.execute("UPDATE users SET tier_id = ? WHERE user_id = ?", (tier_id, user_id))
            conn.commit()

    def get_book_tier(self, book_id: str) -> Dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT st.*, b.is_visible FROM subscription_tiers st
                JOIN books b ON b.tier_id = st.tier_id WHERE b.book_id = ?
            """, (book_id,)).fetchone()
            return dict(row) if row else {"tier_id": 1, "code": "demo", "name": "Demo Gratuita", "level": 0}
