import logging
from pathlib import Path
from typing import Dict, Any, Optional

from src.tts import TTSManager

logger = logging.getLogger("Importer.TTS")

def generate_nodes_audio(
    tts_manager: TTSManager,
    nodes: Dict[str, Any],
    output_dir: Path,
    language: str = "es",
    tts_engine: str = "auto",
    voice_name: Optional[str] = None,
    narrator_id: Optional[int] = None
):
    """Generates audio files (narrative and choice options) for all nodes in the book."""
    total_sections = len(nodes)
    
    narrator_info = None
    if narrator_id:
        try:
            from src.db import Database
            db = Database()
            narrator_info = db.get_narrator_by_id(narrator_id)
        except Exception as e:
            logger.warning(f"Could not fetch narrator #{narrator_id} from DB: {e}")

    narrator_name = narrator_info.get("display_name") if narrator_info else (voice_name or tts_engine)
    logger.info(f"Generating TTS audio for {total_sections} nodes (narrator='{narrator_name}', lang='{language}')...")
    
    for n_id, n_data in nodes.items():
        # 1. Main story narrative audio
        audio_path = output_dir / n_data["audio"]
        if not audio_path.exists():
            tts_parts = []
            if n_data.get('title'):
                tts_parts.append(n_data['title'])
            if n_data.get('text'):
                tts_parts.append(n_data['text'])
            if tts_parts:
                tts_text = "\n\n".join(tts_parts)
                if narrator_info:
                    tts_manager.generate_audio_by_narrator(tts_text, audio_path, narrator_info, language=language)
                else:
                    tts_manager.generate_audio(tts_text, audio_path, language=language, tts_engine=tts_engine, voice_name=voice_name)

        # 2. Options audio (_options.mp3)
        if n_data.get("audio_options"):
            audio_opt_path = output_dir / n_data["audio_options"]
            if not audio_opt_path.exists():
                choices = n_data.get('choices', [])
                if choices:
                    opt_parts = ["¿Qué deseas hacer?" if language == "es" else "What do you want to do?"]
                    for c in choices:
                        prefix = "Opción" if language == "es" else "Option"
                        opt_parts.append(f"{prefix} {c['choice_id']}: {c['text']}.")
                    opt_text = "\n\n".join(opt_parts)
                    if narrator_info:
                        tts_manager.generate_audio_by_narrator(opt_text, audio_opt_path, narrator_info, language=language)
                    else:
                        tts_manager.generate_audio(opt_text, audio_opt_path, language=language, tts_engine=tts_engine, voice_name=voice_name)
