import base64
import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("TTS.Google")


class GoogleCloudTTSProvider:
    def __init__(self, api_key: str, default_voice_es: str, default_voice_en: str):
        self.api_key = api_key or ""
        self.default_voice_es = default_voice_es
        self.default_voice_en = default_voice_en

    def generate(self, text: str, output_file: Path, language: str, voice_name: Optional[str] = None) -> bool:
        if not self.api_key or not text or not text.strip():
            return False
        clean_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()
        if not clean_text:
            return False
        chunks = self._split_chunks(clean_text)
        lang_code = language.lower()[:2] if language else "es"
        voice_name = voice_name if voice_name and voice_name not in ("default", "auto") else (self.default_voice_en if lang_code == "en" else self.default_voice_es)
        parts = voice_name.split("-")
        voice_language = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else ("en-US" if lang_code == "en" else "es-ES")
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.api_key}"
        segments = []
        for chunk in chunks:
            request = urllib.request.Request(url, data=json.dumps({"input": {"text": chunk}, "voice": {"languageCode": voice_language, "name": voice_name}, "audioConfig": {"audioEncoding": "MP3"}}).encode("utf-8"), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request) as response:
                    audio = json.loads(response.read().decode("utf-8")).get("audioContent")
                    if audio:
                        segments.append(base64.b64decode(audio))
            except urllib.error.HTTPError as exc:
                logger.error("Google Cloud TTS HTTP %s: %s", exc.code, exc.read().decode("utf-8", errors="ignore"))
                return False
            except Exception as exc:
                logger.error("Google Cloud TTS failed: %s", exc)
                return False
        if not segments:
            return False
        with open(Path(output_file).with_suffix(".mp3"), "wb") as target:
            for segment in segments:
                target.write(segment)
        return True

    @staticmethod
    def _split_chunks(text: str):
        if len(text.encode("utf-8")) <= 4200:
            return [text]
        chunks, current = [], ""
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate.encode("utf-8")) <= 4200:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = sentence
        if current:
            chunks.append(current)
        return chunks
