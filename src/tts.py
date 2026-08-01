import os
import time
import urllib.request
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional
from gtts import gTTS
from config import PIPER_BIN, PIPER_MODEL_ES, PIPER_MODEL_EN

logger = logging.getLogger("TTS")

# Known Piper voice model download URLs from HuggingFace
PIPER_MODEL_DOWNLOAD_URLS = {
    "es_ES-davefx-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
    "en_US-lessac-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
}

class TTSManager:
    def __init__(self, piper_bin: str = PIPER_BIN, piper_model_es: str = PIPER_MODEL_ES, piper_model_en: str = PIPER_MODEL_EN):
        self.piper_bin = piper_bin
        self.piper_model_es = piper_model_es
        self.piper_model_en = piper_model_en
        self.has_piper_bin = bool(shutil.which(piper_bin))
        if self.has_piper_bin:
            logger.info(f"TTSManager ready with Piper binary '{piper_bin}'")

    def _ensure_model_exists(self, model_path_str: str) -> bool:
        """Checks if a Piper ONNX model exists, and downloads it (and its .json config) automatically if missing."""
        if not model_path_str:
            return False
        model_path = Path(model_path_str)
        if model_path.exists():
            return True

        filename = model_path.name
        url = PIPER_MODEL_DOWNLOAD_URLS.get(filename)
        if not url:
            logger.warning(f"No download URL configured for missing Piper model: {filename}")
            return False

        logger.info(f"📥 Piper voice model '{filename}' not found locally. Auto-downloading from HuggingFace...")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        json_path = model_path.with_suffix(".onnx.json")
        json_url = url + ".json"

        try:
            logger.info(f"Downloading {url} -> {model_path}...")
            urllib.request.urlretrieve(url, str(model_path))
            logger.info(f"Downloading {json_url} -> {json_path}...")
            urllib.request.urlretrieve(json_url, str(json_path))
            logger.info(f"✅ Successfully downloaded Piper voice model '{filename}'!")
            return True
        except Exception as e:
            logger.error(f"Failed to auto-download Piper model '{filename}': {e}")
            if model_path.exists():
                try: model_path.unlink()
                except Exception: pass
            if json_path.exists():
                try: json_path.unlink()
                except Exception: pass
            return False

    def generate_audio(self, text: str, output_file: Path, language: str = "es") -> bool:
        """Generates audio for text and saves it to output_file (.mp3). Supports Spanish ('es') and English ('en')."""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS generation. Skipping.")
            return False

        lang_code = language.lower()[:2] if language else "es"
        target_model_str = self.piper_model_en if lang_code == "en" else self.piper_model_es

        # Attempt 1: Piper TTS (with auto-download of missing voice model)
        if self.has_piper_bin and target_model_str:
            if self._ensure_model_exists(target_model_str):
                try:
                    cmd = [
                        self.piper_bin,
                        "--model", target_model_str,
                        "--output_file", str(output_file)
                    ]
                    subprocess.run(
                        cmd,
                        input=text.encode("utf-8"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                    logger.info(f"Generated Piper audio ({lang_code}): {output_file.name}")
                    return True
                except Exception as e:
                    logger.error(f"Piper execution failed ({lang_code}): {e}. Trying fallback TTS.")

        # Attempt 2: gTTS Fallback (with rate-limiting delay to prevent HTTP 429)
        try:
            tts_lang = "en" if lang_code == "en" else "es"
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            mp3_path = output_file.with_suffix(".mp3")
            tts.save(str(mp3_path))
            logger.info(f"Generated gTTS audio ({tts_lang}): {mp3_path.name}")
            time.sleep(0.3)  # Throttle requests to avoid Google 429 rate limits
            return True
        except Exception as e:
            logger.error(f"gTTS generation failed ({lang_code}): {e}")
            time.sleep(1.0)  # Backoff delay when rate limited
            return False
