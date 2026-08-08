"""Compatibility router grouping independent administration subdomains."""

from fastapi import APIRouter

from src.routers.admin_audit import router as audit_router
from src.routers.admin_narrators import router as narrators_router
from src.routers.admin_users import router as users_router

router = APIRouter()
router.include_router(users_router)
router.include_router(narrators_router)
router.include_router(audit_router)
