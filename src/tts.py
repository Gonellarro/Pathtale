import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional
from gtts import gTTS
from config import PIPER_BIN, PIPER_MODEL_ES, PIPER_MODEL_EN

logger = logging.getLogger("TTS")

class TTSManager:
    def __init__(self, piper_bin: str = PIPER_BIN, piper_model_es: str = PIPER_MODEL_ES, piper_model_en: str = PIPER_MODEL_EN):
        self.piper_bin = piper_bin
        self.piper_model_es = piper_model_es
        self.piper_model_en = piper_model_en
        self.has_piper_bin = bool(shutil.which(piper_bin))
        if self.has_piper_bin:
            logger.info(f"TTSManager ready with Piper binary '{piper_bin}'")

    def generate_audio(self, text: str, output_file: Path, language: str = "es") -> bool:
        """Generates audio for text and saves it to output_file (.mp3). Supports Spanish ('es') and English ('en')."""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS generation.")
            return False

        lang_code = language.lower()[:2] if language else "es"
        chosen_model = self.piper_model_en if lang_code == "en" else self.piper_model_es

        # Attempt 1: Piper TTS if configured and model exists
        if self.has_piper_bin and chosen_model and Path(chosen_model).exists():
            try:
                cmd = [
                    self.piper_bin,
                    "--model", chosen_model,
                    "--output_file", str(output_file)
                ]
                subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                logger.info(f"Generated Piper audio ({lang_code}): {output_file}")
                return True
            except Exception as e:
                logger.error(f"Piper execution failed ({lang_code}): {e}. Trying fallback TTS.")

        # Attempt 2: gTTS Fallback
        try:
            tts_lang = "en" if lang_code == "en" else "es"
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            mp3_path = output_file.with_suffix(".mp3")
            tts.save(str(mp3_path))
            logger.info(f"Generated gTTS audio ({tts_lang}): {mp3_path}")
            return True
        except Exception as e:
            logger.error(f"gTTS generation failed: {e}")
            return False
