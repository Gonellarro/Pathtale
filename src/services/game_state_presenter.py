"""Transforms internal game state into the PWA response contract."""

from typing import Optional

from src.services.audio_catalog import AudioCatalog, AudioCatalogError


class GameStatePresenter:
    def __init__(self, engine, audio_catalog: Optional[AudioCatalog] = None):
        self.engine = engine
        self.audio_catalog = audio_catalog or AudioCatalog()

    def _audio_runtime(self, book: dict, node_id: str) -> Optional[dict]:
        runtime = book.get("audio")
        if not runtime:
            return None
        scenes = {}
        for scene_id, scene in (runtime.get("music_scenes") or {}).items():
            tracks = []
            for track in scene.get("tracks", []):
                try:
                    asset = self.audio_catalog.get_asset(track["asset_id"])
                except (AudioCatalogError, KeyError):
                    continue
                if asset.get("type") == "music":
                    tracks.append({**track, "file": self.audio_catalog.public_url(track["asset_id"])})
            if tracks:
                scenes[scene_id] = {**scene, "tracks": tracks}
        return {
            "schema": runtime.get("schema", "pathtale.audio-runtime/1.0"),
            "catalog_version": runtime.get("catalog_version"),
            "music_scenes": scenes,
            "fx_library": runtime.get("fx_library", {}),
            "node_directive": (runtime.get("node_directives") or {}).get(node_id, {}),
        }

    def format(self, user_id: int, book_id: str, state: dict) -> dict:
        node = state["current_node"]
        book = self.engine.books.get(book_id, {})
        asset_url = f"/api/books/{book_id}/asset"
        history = self.engine.db.get_history(user_id, book_id, limit=100)
        visited_count = len({entry["to_node_id"] for entry in history})
        total_sections = book.get("total_sections", 1)
        narrator_id = book.get("narrator_id")
        narrator = self.engine.db.get_narrator_by_id(narrator_id) if narrator_id else None
        return {
            "user_id": user_id,
            "book_id": book_id,
            "book_title": state.get("book_title"),
            "book_author": book.get("author"),
            "narrator_name": narrator.get("display_name") if narrator else None,
            "narrator_engine": narrator.get("engine_name") if narrator else None,
            "total_sections": total_sections,
            "node_id": node.get("id"),
            "display_number": node.get("display_number"),
            "title": node.get("title"),
            "text": node.get("text"),
            "text_html": node.get("text_html"),
            "images": [f"{asset_url}/{image}" for image in node.get("images", [])],
            "audio_url": f"{asset_url}/{node['audio']}" if node.get("audio") else None,
            "audio_options_url": f"{asset_url}/{node['audio_options']}" if node.get("audio_options") else None,
            "cover_image_url": f"{asset_url}/{book['cover_image']}" if book.get("cover_image") else None,
            "audio_runtime": self._audio_runtime(book, node.get("id")),
            "choices": node.get("choices", []),
            "inventory": state.get("inventory", {}),
            "variables": state.get("variables", {}),
            "progress_percent": min(100, int((visited_count / max(1, total_sections)) * 100)),
            "history_count": len(history),
            "playback_position_seconds": (
                state.get("playback_position_seconds", 0)
                if state.get("playback_node_id") == node.get("id")
                else 0
            ),
        }
