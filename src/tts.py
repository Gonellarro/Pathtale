import os
import time
import json
import base64
import urllib.request
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional
from gtts import gTTS
from config import PIPER_BIN, PIPER_MODEL_ES, PIPER_MODEL_EN, GOOGLE_TTS_API_KEY, GOOGLE_VOICE_ES, GOOGLE_VOICE_EN

logger = logging.getLogger("TTS")

# Known Piper voice model download URLs from HuggingFace
PIPER_MODEL_DOWNLOAD_URLS = {
    "es_ES-davefx-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
    "en_US-lessac-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
}

class TTSManager:
    def __init__(self, piper_bin: str = PIPER_BIN, piper_model_es: str = PIPER_MODEL_ES, piper_model_en: str = PIPER_MODEL_EN, google_api_key: str = GOOGLE_TTS_API_KEY):
        self.piper_bin = piper_bin
        self.piper_model_es = piper_model_es
        self.piper_model_en = piper_model_en
        self.google_api_key = google_api_key or os.getenv("GOOGLE_TTS_API_KEY", "")
        self.google_voice_es = os.getenv("GOOGLE_VOICE_ES", GOOGLE_VOICE_ES)
        self.google_voice_en = os.getenv("GOOGLE_VOICE_EN", GOOGLE_VOICE_EN)
        self.has_piper_bin = bool(shutil.which(piper_bin))
        if self.google_api_key:
            logger.info("TTSManager ready with Google Cloud Text-to-Speech API Key")
        elif self.has_piper_bin:
            logger.info(f"TTSManager ready with Piper binary '{piper_bin}'")

    def _ensure_model_exists(self, model_path_str: str, custom_download_url: Optional[str] = None) -> bool:
        """Checks if a Piper ONNX model exists, and downloads it (and its .json config) automatically if missing."""
        if not model_path_str:
            return False
        model_path = Path(model_path_str)
        if model_path.exists():
            return True

        filename = model_path.name
        url = custom_download_url or PIPER_MODEL_DOWNLOAD_URLS.get(filename)
        if not url:
            logger.warning(f"No download URL configured for missing Piper model: {filename}")
            return False

        logger.info(f"📥 Piper voice model '{filename}' not found locally. Auto-downloading from {url}...")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        json_path = model_path.with_suffix(".onnx.json")
        json_url = url + ".json"

        try:
            logger.info(f"Downloading {url} -> {model_path}...")
            urllib.request.urlretrieve(url, str(model_path))
            try:
                logger.info(f"Downloading {json_url} -> {json_path}...")
                urllib.request.urlretrieve(json_url, str(json_path))
            except Exception as e_json:
                logger.warning(f"Could not download .json config for '{filename}' ({e_json}), continuing if ONNX exists.")
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

    def _generate_google_cloud_tts(self, text: str, output_file: Path, language: str, voice_name: Optional[str] = None) -> bool:
        """Synthesizes text using Google Cloud Text-to-Speech official REST API with Neural2/WaveNet voices."""
        if not self.google_api_key or not text or not text.strip():
            return False

        import re
        clean_text = re.sub(r'<[^>]+>', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        if not clean_text:
            return False

        # Split long text into sentence-aware chunks of max 4200 bytes UTF-8 (Google limit is 5000 bytes)
        encoded_bytes = clean_text.encode("utf-8")
        MAX_BYTES = 4200

        if len(encoded_bytes) <= MAX_BYTES:
            chunks = [clean_text]
        else:
            sentences = re.split(r'(?<=[.!?])\s+', clean_text)
            chunks = []
            current_chunk = ""
            for s in sentences:
                test_chunk = f"{current_chunk} {s}".strip() if current_chunk else s
                if len(test_chunk.encode("utf-8")) <= MAX_BYTES:
                    current_chunk = test_chunk
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = s
            if current_chunk:
                chunks.append(current_chunk)

        lang_code = language.lower()[:2] if language else "es"
        if not voice_name or voice_name in ("default", "auto"):
            voice_name = self.google_voice_en if lang_code == "en" else self.google_voice_es

        parts = voice_name.split("-")
        voice_lang = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else ("en-US" if lang_code == "en" else "es-ES")

        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.google_api_key}"

        audio_segments = []
        for chunk in chunks:
            payload = {
                "input": {"text": chunk},
                "voice": {
                    "languageCode": voice_lang,
                    "name": voice_name
                },
                "audioConfig": {
                    "audioEncoding": "MP3"
                }
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    audio_base64 = result.get("audioContent")
                    if audio_base64:
                        audio_segments.append(base64.b64decode(audio_base64))
            except urllib.error.HTTPError as e:
                try:
                    err_body = e.read().decode("utf-8", errors="ignore")
                    logger.error(f"Google Cloud TTS API HTTP {e.code} error: {err_body}")
                except Exception:
                    logger.error(f"Google Cloud TTS API HTTP {e.code} error: {e}")
                return False
            except Exception as e:
                logger.error(f"Google Cloud TTS API failed: {e}")
                return False

        if audio_segments:
            mp3_path = output_file.with_suffix(".mp3")
            with open(mp3_path, "wb") as f:
                for seg in audio_segments:
                    f.write(seg)
            logger.info(f"Generated Google Cloud TTS audio ({voice_name}, {len(chunks)} chunks): {mp3_path.name}")
            return True

        return False

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

        # Piper TTS request OR auto fallback
        target_model_str = self.piper_model_en if lang_code == "en" else self.piper_model_es
        if voice_name and voice_name.endswith(".onnx"):
            models_dir = Path(self.piper_model_es).parent
            custom_model = models_dir / voice_name
            if custom_model.exists():
                target_model_str = str(custom_model)

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

    def generate_audio_by_narrator(self, text: str, output_file: Path, narrator_info: dict, language: str = "es") -> bool:
        """Synthesizes text dynamically using DB Narrator info (engine_code, voice_code, download_url, model_filename)."""
        if not narrator_info:
            return self.generate_audio(text, output_file, language=language)

        engine_code = narrator_info.get("engine_code", "piper").lower()
        voice_code = narrator_info.get("voice_code", "es_ES-davefx-medium.onnx")
        download_url = narrator_info.get("download_url")
        model_filename = narrator_info.get("model_filename") or (voice_code if voice_code.endswith(".onnx") else f"{voice_code}.onnx")

        if engine_code == "google":
            if self.google_api_key and self._generate_google_cloud_tts(text, output_file, language, voice_name=voice_code):
                return True
            logger.warning("Google Cloud TTS requested by narrator but API key missing/failed. Falling back to Piper...")

        # Piper Local ONNX engine
        models_dir = Path(self.piper_model_es).parent
        target_model_path = models_dir / model_filename

        if self.has_piper_bin:
            if self._ensure_model_exists(str(target_model_path), custom_download_url=download_url):
                try:
                    cmd = [
                        self.piper_bin,
                        "--model", str(target_model_path),
                        "--output_file", str(output_file)
                    ]
                    subprocess.run(
                        cmd,
                        input=text.encode("utf-8"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                    logger.info(f"Generated Piper audio via Narrator '{narrator_info.get('display_name')}': {output_file.name}")
                    return True
                except Exception as e:
                    logger.error(f"Piper execution failed for Narrator '{narrator_info.get('name')}': {e}")

        # Default fallback
        return self.generate_audio(text, output_file, language=language, tts_engine=engine_code, voice_name=voice_code)

        # gTTS Fallback
        try:
            tts_lang = "en" if lang_code == "en" else "es"
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            mp3_path = output_file.with_suffix(".mp3")
            tts.save(str(mp3_path))
            logger.info(f"Generated gTTS audio ({tts_lang}): {mp3_path.name}")
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.error(f"gTTS generation failed ({lang_code}): {e}")
            time.sleep(1.0)
            return False
