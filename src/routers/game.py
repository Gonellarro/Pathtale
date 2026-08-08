"""Compatibility router grouping the independently owned game subdomains."""

from fastapi import APIRouter

from src.routers.gameplay import router as gameplay_router
from src.routers.game_progress import router as progress_router
from src.routers.playback import router as playback_router
from src.routers.voice import router as voice_router

router = APIRouter()
router.include_router(gameplay_router)
router.include_router(progress_router)
router.include_router(playback_router)
router.include_router(voice_router)
