import time
import logging
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Header

from config import BASE_DIR
from src.engine import GameEngine
from src.stt import STTManager
from src.voice_parser import VoiceParser
from src.api_models import (
    AdminBookUpdateRequest,
    AdminConfirmBookImportRequest,
    AdminNarratorCreateRequest,
    AdminNarratorUpdateRequest,
    AdminRegenerateAudiosRequest,
    AdminUserCreateRequest,
    AdminUserSubscriptionRequest,
    AdminUserUpdateRequest,
    ChoiceRequest,
    PlaybackPositionRequest,
    LoginRequest,
    RegisterRequest,
    StartGameRequest,
)

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
