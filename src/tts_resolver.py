from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TTSSelection:
    engine: str
    voice: str
    model_filename: str
    download_url: Optional[str] = None


class TTSResolver:
    """Resolves the executable TTS configuration from narrator metadata."""

    @staticmethod
    def resolve(narrator_info: Optional[dict], language: str = "es") -> TTSSelection:
        lang_code = language.lower()[:2] if language else "es"
        default_voice = "en_US-lessac-medium.onnx" if lang_code == "en" else "es_ES-davefx-medium.onnx"
        if not narrator_info:
            return TTSSelection("auto", "default", default_voice)

        engine = (narrator_info.get("engine_code") or "piper").lower()
        voice = narrator_info.get("voice_code") or default_voice
        model_filename = narrator_info.get("model_filename") or (
            voice if voice.endswith(".onnx") else f"{voice}.onnx"
        )
        return TTSSelection(
            engine=engine,
            voice=voice,
            model_filename=model_filename,
            download_url=narrator_info.get("download_url"),
        )
