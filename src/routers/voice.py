"""Speech-to-text routes."""

import os
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.dependencies import stt_manager, temp_dir

router = APIRouter(prefix="/api", tags=["Voice"])


@router.post("/voice/transcribe")
async def transcribe_voice(file: UploadFile = File(...)):
    try:
        suffix = Path(file.filename).suffix or ".wav"
        temp_file = temp_dir / f"voice_{os.getpid()}{suffix}"
        temp_file.write_bytes(await file.read())
        transcription = stt_manager.transcribe(str(temp_file))
        temp_file.unlink(missing_ok=True)
        return {"status": "success", "text": transcription}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error processing voice: {str(exc)}")
