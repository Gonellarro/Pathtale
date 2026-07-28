import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional
from gtts import gTTS
from config import PIPER_BIN, PIPER_MODEL

logger = logging.getLogger("TTS")

class TTSManager:
    def __init__(self, piper_bin: str = PIPER_BIN, piper_model: str = PIPER_MODEL):
        self.piper_bin = piper_bin
        self.piper_model = piper_model
        self.has_piper = bool(shutil.which(piper_bin)) and bool(piper_model and Path(piper_model).exists())
        if self.has_piper:
            logger.info(f"Using Piper TTS with binary '{piper_bin}' and model '{piper_model}'")
        else:
            logger.info("Piper binary/model not found. Falling back to gTTS (Google Text-to-Speech).")

    def generate_audio(self, text: str, output_file: Path) -> bool:
        """Generates audio for text and saves it to output_file (.ogg or .mp3)."""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS generation.")
            return False

        # Attempt 1: Piper TTS if configured
        if self.has_piper:
            try:
                cmd = [
                    self.piper_bin,
                    "--model", self.piper_model,
                    "--output_file", str(output_file)
                ]
                proc = subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                logger.info(f"Generated Piper audio: {output_file}")
                return True
            except Exception as e:
                logger.error(f"Piper execution failed: {e}. Trying fallback TTS.")

        # Attempt 2: gTTS Fallback
        try:
            tts = gTTS(text=text, lang="es", slow=False)
            mp3_path = output_file.with_suffix(".mp3")
            tts.save(str(mp3_path))
            logger.info(f"Generated gTTS audio: {mp3_path}")
            return True
        except Exception as e:
            logger.error(f"gTTS generation failed: {e}")
            return False
