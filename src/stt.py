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
            from faster_whisper import WhisperModel
            logger.info(f"Loading Faster-Whisper model '{self.model_size}' (CPU / int8)...")
            self.whisper_model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            logger.info("Faster-Whisper model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load Faster-Whisper: {e}. STT in fallback mode.")

    def transcribe(self, audio_path: Path, language: str = "es") -> Optional[str]:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        if self.whisper_model is not None:
            try:
                segments, info = self.whisper_model.transcribe(str(audio_path), language=language)
                text = " ".join([s.text.strip() for s in segments]).strip()
                logger.info(f"Whisper transcription: '{text}'")
                return text
            except Exception as e:
                logger.error(f"Whisper transcription error: {e}")

        logger.error("STT transcription unavailable.")
        return None
