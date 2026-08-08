"""Administrative audit-log routes."""

from typing import Optional

from fastapi import APIRouter, Header, Query

from src.dependencies import engine, require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin Audit"])


@router.get("/logs")
def list_logs(limit: int = Query(50), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return {"logs": engine.db.get_reading_logs_admin(limit=limit)}
