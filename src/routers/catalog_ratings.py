"""Per-user book ratings."""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from src.api_models import BookRatingRequest
from src.dependencies import engine, resolve_user_id

router = APIRouter(prefix="/api", tags=["Catalog"])


@router.get("/books/{book_id}/rating")
def get_book_rating(book_id: str, authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization)
    if book_id not in engine.books:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return {"rating": engine.db.get_user_book_rating(user_id, book_id)}


@router.put("/books/{book_id}/rating")
def set_book_rating(book_id: str, req: BookRatingRequest, authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization)
    if book_id not in engine.books:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if not 1 <= req.rating <= 5:
        raise HTTPException(status_code=422, detail="La valoración debe estar entre 1 y 5 estrellas")
    return {"rating": engine.db.set_user_book_rating(user_id, book_id, req.rating)}
