"""Compatibility router for the catalogue's independently owned subdomains."""

from fastapi import APIRouter

from src.routers.catalog_assets import router as assets_router
from src.routers.catalog_books import router as books_router
from src.routers.catalog_narrators import router as narrators_router
from src.routers.catalog_ratings import router as ratings_router
from src.routers.catalog_supplements import router as supplements_router

router = APIRouter()
router.include_router(books_router)
router.include_router(ratings_router)
router.include_router(supplements_router)
router.include_router(narrators_router)
router.include_router(assets_router)
