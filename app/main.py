import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from app.routes.pitch import router as pitch_router
from app.utils.logger import get_logger
from app.config import settings

logger = get_logger("main")

app = FastAPI(
    title="Sales Pitch Generator Pro",
    description="Optimized backend with background workers, rate limiting, and structured logging.",
    version="1.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# CORS Configuration (Security Audit & Best Practice)
# Modify the allowed origins as required for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific domain lists
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler (Prevents raw code/db leakage on failure)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}", 
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact support."}
    )

# Include Routers
app.include_router(pitch_router)

# Locate static folder relative to the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount Static Files (Fallback to serve frontend)
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    logger.warning(f"Static directory not found at {STATIC_DIR}. Frontend won't be served directly from FastAPI.")

# Startup log
@app.on_event("startup")
async def startup_event():
    logger.info("Sales Pitch Generator Pro API started successfully.")
    logger.info(f"Debug Mode: {settings.debug}")
    logger.info(f"Rate Limiting active: {settings.rate_limit_requests} requests / {settings.rate_limit_window_seconds}s")
