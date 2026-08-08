"""Audio synthesis for an already published book."""

import json
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from src.tts import TTSManager

logger = logging.getLogger("BookAudioService")

ProgressCallback = Callable[[Dict[str, object]], None]


class BookAudioService:
    """Builds and synthesizes a book's audio tracks without HTTP concerns."""

    def __init__(self, books_dir: Path, database):
        self.books_dir = Path(books_dir)
        self.database = database

    def generate(
        self,
        book_id: str,
        *,
        tts_engine: str = "auto",
        voice_name: Optional[str] = None,
        language: Optional[str] = None,
        narrator_id: Optional[int] = None,
        overwrite: bool = False,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Dict[str, int]:
        """Generate missing tracks, or all tracks when ``overwrite`` is true."""
        book_folder, book_data = self._load_book(book_id)
        final_language = (language or book_data.get("language") or "es").lower()[:2]
        selected_narrator_id, narrator_info = self._resolve_narrator(book_id, book_data, narrator_id)
        tasks = self._build_tasks(book_data, final_language)

        if overwrite:
            self._remove_existing_audio(book_folder / "audios")

        total = len(tasks)
        generated = 0
        skipped = 0
        self._report(on_progress, total=total, completed=0, generated=0, skipped=0, current_item=None)
        tts_manager = TTSManager()

        for index, task in enumerate(tasks, start=1):
            output_path = book_folder / task["relative_path"]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists():
                skipped += 1
            else:
                success = self._generate(
                    tts_manager,
                    task["text"],
                    output_path,
                    final_language,
                    narrator_info,
                    tts_engine,
                    voice_name,
                )
                if not success:
                    raise RuntimeError(f"No se pudo generar el audio '{task['relative_path']}'.")
                generated += 1
            self._report(
                on_progress,
                total=total,
                completed=index,
                generated=generated,
                skipped=skipped,
                current_item=task["relative_path"],
            )

        logger.info(
            "Audio generation complete for '%s': %d generated, %d already available.",
            book_id,
            generated,
            skipped,
        )
        return {"total": total, "generated": generated, "skipped": skipped, "narrator_id": selected_narrator_id or 0}

    def regenerate(self, book_id: str, **kwargs) -> Dict[str, int]:
        """Regenerate every track while preserving the same synthesis workflow."""
        return self.generate(book_id, overwrite=True, **kwargs)

    def _load_book(self, book_id: str):
        book_folder = self.books_dir / book_id
        json_path = book_folder / "book.json"
        if not json_path.exists():
            raise FileNotFoundError(f"No se encontró book.json para el libro '{book_id}'.")
        with json_path.open("r", encoding="utf-8") as source:
            return book_folder, json.load(source)

    def _resolve_narrator(self, book_id: str, book_data: Dict, narrator_id: Optional[int]):
        db_book = self.database.get_book_by_id(book_id)
        selected_narrator_id = narrator_id or (db_book.get("narrator_id") if db_book else None) or book_data.get("narrator_id")
        narrator_info = self.database.get_narrator_by_id(selected_narrator_id) if selected_narrator_id else None
        if selected_narrator_id and not narrator_info:
            raise ValueError(f"El narrador #{selected_narrator_id} no existe o está inactivo.")
        return selected_narrator_id, narrator_info

    @staticmethod
    def _build_tasks(book_data: Dict, language: str) -> List[Dict[str, str]]:
        tasks: List[Dict[str, str]] = []
        for node in book_data.get("nodes", {}).values():
            text_parts = [part for part in (node.get("title"), node.get("text")) if part]
            if node.get("audio") and text_parts:
                tasks.append({"relative_path": node["audio"], "text": "\n\n".join(text_parts)})
            if node.get("audio_options") and node.get("choices"):
                prefix = "Opción" if language == "es" else "Option"
                heading = "¿Qué deseas hacer?" if language == "es" else "What do you want to do?"
                choices = [f"{prefix} {choice['choice_id']}: {choice['text']}." for choice in node["choices"]]
                tasks.append({"relative_path": node["audio_options"], "text": "\n\n".join([heading, *choices])})
        for supplement in book_data.get("supplements", []):
            text = supplement.get("text", "").strip()
            if supplement.get("audio") and text:
                tasks.append({
                    "relative_path": supplement["audio"],
                    "text": "\n\n".join(filter(None, [supplement.get("title"), text])),
                })
        return tasks

    @staticmethod
    def _remove_existing_audio(audio_dir: Path) -> None:
        if not audio_dir.exists():
            return
        for audio_file in audio_dir.rglob("*.mp3"):
            try:
                audio_file.unlink()
            except OSError:
                logger.warning("Could not remove old audio '%s'", audio_file)

    @staticmethod
    def _generate(tts_manager, text, output_path, language, narrator_info, tts_engine, voice_name) -> bool:
        if narrator_info:
            return tts_manager.generate_audio_by_narrator(text, output_path, narrator_info, language=language)
        return tts_manager.generate_audio(
            text,
            output_path,
            language=language,
            tts_engine=tts_engine,
            voice_name=voice_name,
        )

    @staticmethod
    def _report(callback: Optional[ProgressCallback], **payload) -> None:
        if callback:
            callback(payload)
