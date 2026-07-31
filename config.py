import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.resolve()

# Data paths
DATA_DIR = BASE_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"
DB_PATH = DATA_DIR / "game.db"
INPUT_BOOKS_DIR = BASE_DIR / "Libros"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True, parents=True)
BOOKS_DIR.mkdir(exist_ok=True, parents=True)
INPUT_BOOKS_DIR.mkdir(exist_ok=True, parents=True)

# Piper TTS settings
PIPER_BIN = os.getenv("PIPER_BIN", str(BASE_DIR / "venv" / "bin" / "piper"))
PIPER_MODEL_ES = os.getenv("PIPER_MODEL_ES", os.getenv("PIPER_MODEL", "/app/models/piper/es_ES-davefx-medium.onnx"))
PIPER_MODEL_EN = os.getenv("PIPER_MODEL_EN", "/app/models/piper/en_US-lessac-medium.onnx")
PIPER_MODEL = PIPER_MODEL_ES

# LLM Intent Classifier settings (optional)
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434/api/generate") # Default Ollama
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen2.5:3b")
USE_LLM_FALLBACK = os.getenv("USE_LLM_FALLBACK", "true").lower() in ("true", "1", "yes")

# CORS allowed origins (comma-separated list, or '*' for all origins in development)
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
if ALLOWED_ORIGINS_RAW.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_RAW.split(",") if origin.strip()]

# Duración de validez de las sesiones de usuario activas en días (por defecto: 7 días)
SESSION_EXPIRE_DAYS = int(os.getenv("SESSION_EXPIRE_DAYS", "7"))

# Credenciales del usuario Administrador inicial (para la primera instalación)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
