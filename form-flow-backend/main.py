"""
Form Flow AI - Backend Application

FastAPI application for voice-powered form automation.
Provides endpoints for form scraping, voice processing, and form submission.

Features:
    - Form URL scraping with Playwright
    - Voice-to-text with Vosk
    - Text-to-speech with ElevenLabs
    - AI-powered form field understanding with Gemini
    - Automated form submission

Run:
    python main.py
    # or
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
import uvicorn

from config.settings import settings
from core import models, database
from utils.logging import setup_logging, get_logger
from utils.exceptions import FormFlowError
from utils.rate_limit import limiter, rate_limit_exceeded_handler

# Import Routers
from routers import auth, forms, speech

# Initialize logging
setup_logging()
logger = get_logger(__name__)


# =============================================================================
# Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    
    Handles startup and shutdown events:
        - Startup: Initialize database tables
        - Shutdown: Cleanup resources
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Create database tables
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        logger.info("Database tables initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await database.engine.dispose()


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="Voice-powered form automation API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Attach rate limiter to app state
app.state.limiter = limiter


# =============================================================================
# Middleware
# =============================================================================

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip Compression (reduces response size by ~70%)
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500)


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(FormFlowError)
async def formflow_exception_handler(request: Request, exc: FormFlowError):
    """
    Handle custom FormFlow exceptions.
    
    Returns standardized error response with appropriate status code.
    """
    logger.error(f"FormFlowError: {exc.message}", extra={"details": exc.details})
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


# Rate limit exceeded handler
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# =============================================================================
# Routers
# =============================================================================

app.include_router(auth.router)
app.include_router(forms.router)
app.include_router(speech.router)


# =============================================================================
# Health Check Endpoints
# =============================================================================

@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint - basic health check.
    
    Returns:
        dict: Simple status message
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check endpoint.
    
    Checks:
        - Database connectivity
        - Redis connectivity
        - API key configuration
        - Lazy-loaded services status
        - Background task queue stats
    
    Returns:
        dict: Health status with component details
    """
    from utils.cache import check_redis_health
    from core.dependencies import get_initialized_services
    from utils.tasks import get_queue_stats
    
    db_healthy = await database.check_database_health()
    redis_healthy = await check_redis_health()
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "components": {
            "database": db_healthy,
            "redis": redis_healthy,
            "gemini_configured": settings.GOOGLE_API_KEY is not None,
            "elevenlabs_configured": settings.ELEVENLABS_API_KEY is not None,
        },
        "services_loaded": get_initialized_services(),
        "task_queue": get_queue_stats(),
        "version": settings.APP_VERSION
    }


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
