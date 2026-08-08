"""Request models shared by the HTTP routers.

Keeping validation schemas separate from service construction makes
``dependencies`` a small runtime wiring module instead of a model registry.
"""

from typing import Any, Optional

from pydantic import BaseModel


class StartGameRequest(BaseModel):
    user_id: Optional[int] = 1
    book_id: str


class ChoiceRequest(BaseModel):
    choice_id: Optional[Any] = None
    target_node: Optional[str] = None
    text: Optional[str] = None
    text_query: Optional[str] = None


class PlaybackPositionRequest(BaseModel):
    node_id: str
    position_seconds: float
    captured_at_ms: int


class JumpRequest(BaseModel):
    target: str


class BookRatingRequest(BaseModel):
    rating: int


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
