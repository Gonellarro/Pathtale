import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Header
from pydantic import BaseModel

from config import BOOKS_DIR, BASE_DIR, ALLOWED_ORIGINS, DATA_DIR
from src.engine import GameEngine
from src.stt import STTManager
from src.voice_parser import VoiceParser

logger = logging.getLogger("API")

class SimpleRateLimiter:
    """Sliding-window Rate Limiter for sensitive endpoints like login/register."""
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = {}

    def check_rate_limit(self, client_ip: str):
        now = time.time()
        user_attempts = [t for t in self.attempts.get(client_ip, []) if now - t < self.window_seconds]
        if len(user_attempts) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos de inicio de sesión. Por favor, espera 1 minuto antes de reintentar."
            )
        user_attempts.append(now)
        self.attempts[client_ip] = user_attempts

login_rate_limiter = SimpleRateLimiter(max_requests=10, window_seconds=60)

engine = GameEngine()
stt_manager = STTManager()
voice_parser = VoiceParser()

WEB_DIR = BASE_DIR / "web"
temp_dir = BASE_DIR / "data" / "temp"
temp_dir.mkdir(parents=True, exist_ok=True)

# Shared Pydantic Models
class StartGameRequest(BaseModel):
    user_id: Optional[int] = 1
    book_id: str

class ChoiceRequest(BaseModel):
    choice_id: Optional[Any] = None
    target_node: Optional[str] = None
    text: Optional[str] = None
    text_query: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    first_name: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class AdminUserCreateRequest(BaseModel):
    username: str
    password: str
    first_name: Optional[str] = None
    role: Optional[str] = "user"
    tier_id: Optional[int] = 1

class AdminUserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    role: Optional[str] = None
    tier_id: Optional[int] = None
    password: Optional[str] = None

class AdminConfirmBookImportRequest(BaseModel):
    temp_file_id: str
    title: str
    author: str
    language: str = "es"
    narrator_id: Optional[int] = 1
    tts_engine: str = "auto"
    voice_name: str = "default"
    start_node: str = "sec_001"
    tier_id: int = 1
    generate_audios: bool = False

class AdminNarratorCreateRequest(BaseModel):
    name: str
    display_name: str
    engine_id: Optional[int] = 1
    voice_code: Optional[str] = "default"
    language: Optional[str] = "es"
    gender: Optional[str] = "male"
    specialty: Optional[str] = None
    avatar_url: Optional[str] = None
    download_url: Optional[str] = None
    model_filename: Optional[str] = None
    bio: Optional[str] = None

class AdminNarratorUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    engine_id: Optional[int] = None
    voice_code: Optional[str] = None
    language: Optional[str] = None
    gender: Optional[str] = None
    specialty: Optional[str] = None
    avatar_url: Optional[str] = None
    download_url: Optional[str] = None
    model_filename: Optional[str] = None
    bio: Optional[str] = None

class AdminBookUpdateRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    narrator_id: Optional[int] = None
    tier_id: Optional[int] = None
    is_visible: Optional[bool] = None
    genre: Optional[str] = None
    series: Optional[str] = None
    volume: Optional[int] = None
    description: Optional[str] = None
    language: Optional[str] = None
    start_node: Optional[str] = None
    tts_engine: Optional[str] = None
    voice_name: Optional[str] = None
    regenerate_audios: Optional[bool] = False

class AdminRegenerateAudiosRequest(BaseModel):
    tts_engine: Optional[str] = "auto"
    voice_name: Optional[str] = None
    language: Optional[str] = None

class AdminUserSubscriptionRequest(BaseModel):
    tier_id: int
    duration_days: Optional[int] = None

# Helper to resolve user_id from Authorization Bearer header
def resolve_user_id(authorization: Optional[str] = Header(None)) -> int:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user = engine.db.get_user_by_token(token)
        if user:
            return user["user_id"]
    raise HTTPException(status_code=401, detail="No autenticado. Inicia sesión para continuar.")

# Helper to enforce Admin Role for backend endpoints
def require_admin(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado. Token requerido.")
    token = authorization.split(" ")[1]
    user = engine.db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")
    if user.get("role_name") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requiere rol de Administrador.")
    return user
