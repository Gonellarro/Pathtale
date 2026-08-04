import json
import logging
from pathlib import Path
from typing import Optional

from src.tts import TTSManager
from src.importer.tts_pipeline import generate_supplements_audio

logger = logging.getLogger("BookAudioService")


class BookAudioService:
    """Coordinates audio regeneration for an already imported book.

    The service owns filesystem traversal and TTS orchestration. HTTP routers
    should only perform authorization, validation and response formatting.
    """

    def __init__(self, books_dir: Path, database):
        self.books_dir = Path(books_dir)
        self.database = database

    def regenerate(
        self,
        book_id: str,
        tts_engine: str = "auto",
        voice_name: Optional[str] = None,
        language: Optional[str] = None,
        narrator_id: Optional[int] = None,
    ) -> None:
        book_folder = self.books_dir / book_id
        json_path = book_folder / "book.json"
        if not json_path.exists():
            raise FileNotFoundError(f"No se encontró book.json para el libro '{book_id}'.")

        with open(json_path, "r", encoding="utf-8") as f:
            book_data = json.load(f)

        final_language = (language or book_data.get("language") or "es").lower()[:2]
        nodes = book_data.get("nodes", {})
        tts_manager = TTSManager()

        audio_dir = book_folder / "audios"
        audio_dir.mkdir(exist_ok=True)
        for mp3_file in audio_dir.glob("*.mp3"):
            try:
                mp3_file.unlink()
            except OSError:
                logger.warning("Could not remove old audio '%s'", mp3_file)

        supplements_audio_dir = audio_dir / "supplements"
        if supplements_audio_dir.exists():
            for mp3_file in supplements_audio_dir.glob("*.mp3"):
                try:
                    mp3_file.unlink()
                except OSError:
                    logger.warning("Could not remove old supplement audio '%s'", mp3_file)

        db_book = self.database.get_book_by_id(book_id)
        selected_narrator_id = (
            narrator_id
            or (db_book.get("narrator_id") if db_book else None)
            or book_data.get("narrator_id")
        )
        narrator_info = (
            self.database.get_narrator_by_id(selected_narrator_id)
            if selected_narrator_id
            else None
        )
        if selected_narrator_id and not narrator_info:
            raise ValueError(f"El narrador #{selected_narrator_id} no existe o está inactivo.")

        narrator_label = narrator_info.get("display_name") if narrator_info else tts_engine
        logger.info(
            "Regenerating audios for '%s' (%d nodes, narrator='%s', lang='%s')...",
            book_id,
            len(nodes),
            narrator_label,
            final_language,
        )

        for node_data in nodes.values():
            audio_path = book_folder / node_data["audio"]
            text_parts = [part for part in (node_data.get("title"), node_data.get("text")) if part]
            if text_parts:
                self._generate(
                    tts_manager,
                    "\n\n".join(text_parts),
                    audio_path,
                    final_language,
                    narrator_info,
                    tts_engine,
                    voice_name,
                )

            if node_data.get("audio_options") and node_data.get("choices"):
                options = [
                    "¿Qué deseas hacer?" if final_language == "es" else "What do you want to do?"
                ]
                prefix = "Opción" if final_language == "es" else "Option"
                options.extend(
                    f"{prefix} {choice['choice_id']}: {choice['text']}."
                    for choice in node_data["choices"]
                )
                self._generate(
                    tts_manager,
                    "\n\n".join(options),
                    book_folder / node_data["audio_options"],
                    final_language,
                    narrator_info,
                    tts_engine,
                    voice_name,
                )

        generate_supplements_audio(
            tts_manager,
            book_data.get("supplements", []),
            book_folder,
            language=final_language,
            tts_engine=tts_engine,
            voice_name=voice_name,
            narrator_id=selected_narrator_id,
        )

    @staticmethod
    def _generate(tts_manager, text, output_path, language, narrator_info, tts_engine, voice_name):
        if narrator_info:
            tts_manager.generate_audio_by_narrator(text, output_path, narrator_info, language=language)
        else:
            tts_manager.generate_audio(
                text,
                output_path,
                language=language,
                tts_engine=tts_engine,
                voice_name=voice_name,
            )
