import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import ALLOWED_ORIGINS, BASE_DIR
from src.dependencies import WEB_DIR
from src.routers.auth import router as auth_router
from src.routers.catalog import router as catalog_router
from src.routers.game import router as game_router
from src.routers.admin import router as admin_router
from src.routers.admin_books import router as admin_books_router
from src.routers.stats import router as stats_router

logger = logging.getLogger("API")

app = FastAPI(
    title="PathTale Engine API",
    description="REST API para alimentar PWA Web y clientes de ficción interactiva.",
    version="1.0.0"
)

# Enable CORS for PWA and Web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"status": "error", "detail": str(exc)}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no capturado procesando {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "Ocurrió un error interno en el servidor. Por favor, reintenta más tarde."}
    )

@app.get("/favicon.ico")
def get_favicon():
    fav = WEB_DIR / "assets" / "pathtale_logo_clear.png"
    if fav.exists():
        return FileResponse(fav)
    return Response(status_code=204)

# Include Modular Routers
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(game_router)
app.include_router(admin_router)
app.include_router(admin_books_router)
app.include_router(stats_router)

# --- Serve PWA Static Files ---
if WEB_DIR.exists():
    @app.get("/")
    def serve_index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
