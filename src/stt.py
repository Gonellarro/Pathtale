import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("STT")

class STTManager:
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.whisper_model = None
        self._init_whisper()

    def _init_whisper(self):
        try:
            import whisper
            logger.info(f"Loading Whisper model '{self.model_size}'...")
            self.whisper_model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load OpenAI Whisper: {e}. STT fallback mode enabled.")

    def transcribe(self, audio_path: Path, language: str = "es") -> Optional[str]:
        """Transcribes audio file to text."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        if self.whisper_model is not None:
            try:
                result = self.whisper_model.transcribe(str(audio_path), language=language)
                text = result.get("text", "").strip()
                logger.info(f"Whisper transcription: '{text}'")
                return text
            except Exception as e:
                logger.error(f"Whisper transcription error: {e}")

        logger.error("STT transcription unavailable (Whisper model failed).")
        return None
