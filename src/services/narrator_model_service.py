"""Filesystem/model-download work for narrator administration."""

from pathlib import Path

from src.tts import TTSManager


class NarratorModelService:
    def __init__(self, models_dir: Path):
        self.models_dir = Path(models_dir)

    def download(self, narrator: dict) -> str:
        if not narrator.get("download_url"):
            raise ValueError("Este narrador no requiere descarga o no tiene URL configurada.")
        filename = narrator.get("model_filename") or f"{narrator.get('voice_code')}.onnx"
        target = self.models_dir / filename
        if not TTSManager()._ensure_model_exists(str(target), custom_download_url=narrator["download_url"]):
            raise RuntimeError(f"No se pudo descargar el modelo desde {narrator['download_url']}.")
        return filename
