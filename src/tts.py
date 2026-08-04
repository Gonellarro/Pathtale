import os
import logging
from pathlib import Path
from typing import Optional
from config import PIPER_BIN, PIPER_MODEL_ES, PIPER_MODEL_EN, GOOGLE_TTS_API_KEY, GOOGLE_VOICE_ES, GOOGLE_VOICE_EN
from src.providers.google_tts import GoogleCloudTTSProvider
from src.providers.piper import PiperTTSProvider
from src.tts_resolver import TTSResolver

logger = logging.getLogger("TTS")

class TTSManager:
    def __init__(self, piper_bin: str = PIPER_BIN, piper_model_es: str = PIPER_MODEL_ES, piper_model_en: str = PIPER_MODEL_EN, google_api_key: str = GOOGLE_TTS_API_KEY):
        self.piper_bin = piper_bin
        self.piper_model_es = piper_model_es
        self.piper_model_en = piper_model_en
        self.google_api_key = google_api_key or os.getenv("GOOGLE_TTS_API_KEY", "")
        self.google_voice_es = os.getenv("GOOGLE_VOICE_ES", GOOGLE_VOICE_ES)
        self.google_voice_en = os.getenv("GOOGLE_VOICE_EN", GOOGLE_VOICE_EN)
        self.google_provider = GoogleCloudTTSProvider(self.google_api_key, self.google_voice_es, self.google_voice_en)
        self.piper_provider = PiperTTSProvider(piper_bin, piper_model_es, piper_model_en)
        self.has_piper_bin = self.piper_provider.available
        if self.google_api_key:
            logger.info("TTSManager ready with Google Cloud Text-to-Speech API Key")
        elif self.has_piper_bin:
            logger.info(f"TTSManager ready with Piper binary '{piper_bin}'")

    def _ensure_model_exists(self, model_path_str: str, custom_download_url: Optional[str] = None) -> bool:
        """Checks if a Piper ONNX model exists, and downloads it (and its .json config) automatically if missing."""
        return self.piper_provider.ensure_model(model_path_str, custom_download_url)

    def _generate_google_cloud_tts(self, text: str, output_file: Path, language: str, voice_name: Optional[str] = None) -> bool:
        return self.google_provider.generate(text, output_file, language, voice_name)

    def generate_audio(self, text: str, output_file: Path, language: str = "es", tts_engine: str = "auto", voice_name: Optional[str] = None) -> bool:
        """Generates audio for text and saves it to output_file (.mp3)."""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS generation. Skipping.")
            return False

        lang_code = language.lower()[:2] if language else "es"

        # Explicit Google Cloud TTS request OR auto with API key available
        if tts_engine == "google" and not self.google_api_key:
            logger.warning("⚠️ Google Cloud TTS requested, but GOOGLE_TTS_API_KEY is not set in environment or container. Falling back to Piper...")

        if (tts_engine == "google" or (tts_engine == "auto" and self.google_api_key)) and self.google_api_key:
            if self._generate_google_cloud_tts(text, output_file, language, voice_name=voice_name):
                return True

        if self.piper_provider.generate(text, output_file, language=language, voice_name=voice_name):
            logger.info("Generated Piper audio (%s): %s", lang_code, output_file.name)
            return True
        return False

    def generate_audio_by_narrator(self, text: str, output_file: Path, narrator_info: dict, language: str = "es") -> bool:
        """Synthesizes text dynamically using DB Narrator info (engine_code, voice_code, download_url, model_filename)."""
        if not narrator_info:
            return self.generate_audio(text, output_file, language=language)

        selection = TTSResolver.resolve(narrator_info, language)

        if selection.engine == "google":
            if self.google_api_key and self._generate_google_cloud_tts(text, output_file, language, voice_name=selection.voice):
                return True
            logger.warning("Google Cloud TTS requested by narrator but API key missing/failed. Falling back to Piper...")

        if self.piper_provider.generate(text, output_file, language=language, model_filename=selection.model_filename, download_url=selection.download_url):
            logger.info("Generated Piper audio via Narrator '%s'", narrator_info.get("display_name"))
            return True

        # Default fallback
        return self.generate_audio(text, output_file, language=language, tts_engine=selection.engine, voice_name=selection.voice)
