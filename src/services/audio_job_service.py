"""Single-worker background queue for long-running book audio synthesis."""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Optional

from src.services.book_audio_service import BookAudioService

logger = logging.getLogger("AudioJobs")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AudioJobService:
    """Keeps TTS outside the request lifecycle and limits synthesis to one job."""

    def __init__(self, audio_service: BookAudioService):
        self.audio_service = audio_service
        self._jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pathtale-tts")

    def start(
        self,
        book_id: str,
        *,
        tts_engine: str = "auto",
        voice_name: Optional[str] = None,
        language: Optional[str] = None,
        narrator_id: Optional[int] = None,
        overwrite: bool = False,
    ) -> Dict:
        with self._lock:
            existing = next((job for job in self._jobs.values() if job["book_id"] == book_id and job["state"] in {"queued", "running"}), None)
            if existing:
                return self._snapshot(existing)
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "book_id": book_id,
                "state": "queued",
                "total": 0,
                "completed": 0,
                "generated": 0,
                "skipped": 0,
                "current_item": None,
                "error": None,
                "created_at": _now(),
                "started_at": None,
                "finished_at": None,
            }
            self._jobs[job_id] = job
        self._executor.submit(
            self._run,
            job_id,
            book_id,
            tts_engine,
            voice_name,
            language,
            narrator_id,
            overwrite,
        )
        return self.get(job_id)

    def get(self, job_id: str) -> Optional[Dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._snapshot(job) if job else None

    def _run(self, job_id, book_id, tts_engine, voice_name, language, narrator_id, overwrite):
        self._update(job_id, state="running", started_at=_now())
        logger.info("Audio job %s started for '%s'.", job_id, book_id)
        try:
            result = self.audio_service.generate(
                book_id,
                tts_engine=tts_engine,
                voice_name=voice_name,
                language=language,
                narrator_id=narrator_id,
                overwrite=overwrite,
                on_progress=lambda progress: self._update(job_id, **progress),
            )
        except Exception as exc:
            logger.exception("Audio job %s failed for '%s'.", job_id, book_id)
            self._update(job_id, state="failed", error=str(exc), finished_at=_now())
            return
        self._update(job_id, state="completed", finished_at=_now(), **result)
        logger.info("Audio job %s completed for '%s'.", job_id, book_id)

    def _update(self, job_id: str, **updates) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.update(updates)

    @staticmethod
    def _snapshot(job: Dict) -> Dict:
        return dict(job)
