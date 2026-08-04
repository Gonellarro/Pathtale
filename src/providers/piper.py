import logging
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("TTS.Piper")

PIPER_MODEL_DOWNLOAD_URLS = {
    "es_ES-davefx-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
    "en_US-lessac-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
}


class PiperTTSProvider:
    def __init__(self, binary: str, model_es: str, model_en: str):
        self.binary = binary
        self.model_es = model_es
        self.model_en = model_en
        self.available = bool(shutil.which(binary))

    def ensure_model(self, model_path: str, download_url: Optional[str] = None) -> bool:
        if not model_path:
            return False
        path = Path(model_path)
        if path.exists():
            return True
        url = download_url or PIPER_MODEL_DOWNLOAD_URLS.get(path.name)
        if not url:
            logger.warning("No download URL configured for missing Piper model: %s", path.name)
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        config_path = path.with_suffix(".onnx.json")
        try:
            urllib.request.urlretrieve(url, str(path))
            try:
                urllib.request.urlretrieve(url + ".json", str(config_path))
            except Exception as exc:
                logger.warning("Could not download Piper config '%s': %s", config_path.name, exc)
            return True
        except Exception as exc:
            logger.error("Failed to download Piper model '%s': %s", path.name, exc)
            for candidate in (path, config_path):
                try:
                    candidate.unlink()
                except OSError:
                    pass
            return False

    def generate(self, text: str, output_file: Path, language: str = "es", voice_name: Optional[str] = None, model_filename: Optional[str] = None, download_url: Optional[str] = None) -> bool:
        if not self.available or not text or not text.strip():
            return False
        lang_code = language.lower()[:2] if language else "es"
        target = Path(model_filename) if model_filename else Path(self.model_en if lang_code == "en" else self.model_es)
        if model_filename and not target.is_absolute():
            target = Path(self.model_es).parent / target
        elif voice_name and voice_name.endswith(".onnx"):
            candidate = Path(self.model_es).parent / voice_name
            if candidate.exists():
                target = candidate
        if not self.ensure_model(str(target), download_url):
            return False
        try:
            subprocess.run([self.binary, "--model", str(target), "--output_file", str(output_file)], input=text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception as exc:
            logger.error("Piper execution failed: %s", exc)
            return False
