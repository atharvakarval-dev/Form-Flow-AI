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


import warnings
import sys
import asyncio

# Fix for Playwright on Windows - ProactorEventLoop required for subprocess
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Suppress Pydantic V1 warning from LangChain
warnings.filterwarnings("ignore", message=".*Core Pydantic V1 functionality.*")

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
from routers import auth, forms, speech, conversation, advanced_voice, analytics, websocket, local_llm, pdf, suggestions, docx, profile

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
    
    # Validate AI dependencies and warn if degraded
    try:
        from services.ai.dependency_checker import validate_ai_dependencies
        ai_mode = validate_ai_dependencies()
        logger.info(f"AI mode: {ai_mode}")
        
        # Eagerly initialize Local LLM if available (in background/non-blocking)
        # using run_in_executor to avoid blocking the main startup sequence too long
        loop = asyncio.get_running_loop()
        from services.ai.local_llm import get_local_llm_service
        local_llm = get_local_llm_service()
        if local_llm:
             # Fire and forget initialization task
             loop.create_task(local_llm.initialize_async())
             logger.info("Triggered background initialization of Local LLM")
            
    except Exception as e:
        logger.warning(f"AI dependency check/init failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Close browser pool to prevent zombie processes
    from services.form.browser_pool import close_browser_pool
    await close_browser_pool()
    
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
# CORS Configuration
# =============================================================================

# Allow requests from Chrome extension and localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        *settings.cors_origins_list,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex='chrome-extension://.*',  # Allow all Chrome extensions
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# =============================================================================
# Middleware
# =============================================================================



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
app.include_router(conversation.router)
app.include_router(advanced_voice.router)
app.include_router(analytics.router)
app.include_router(websocket.router)
app.include_router(local_llm.router)
app.include_router(pdf.router)
app.include_router(docx.router)
app.include_router(suggestions.router)
app.include_router(profile.router)


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


@app.get("/health/ai", tags=["Health"])
async def ai_health_check():
    """
    AI subsystem health check.
    
    Returns:
        dict: AI mode and dependency status
    """
    try:
        from services.ai.dependency_checker import get_dependency_checker
        checker = get_dependency_checker()
        if not checker.results:
            checker.check_all()
        return checker.to_dict()
    except Exception as e:
        return {
            "mode": "unknown",
            "error": str(e)
        }


@app.get("/health/captcha", tags=["Health"])
async def captcha_health_check():
    """
    CAPTCHA solver configuration status.
    
    Returns:
        dict: Whether auto-solve is configured
    """
    import os
    twocaptcha_key = os.getenv("TWOCAPTCHA_API_KEY")
    anticaptcha_key = os.getenv("ANTICAPTCHA_API_KEY")
    
    has_api_key = bool(twocaptcha_key or anticaptcha_key)
    
    return {
        "auto_solve": has_api_key,
        "provider": "2captcha" if twocaptcha_key else ("anticaptcha" if anticaptcha_key else None),
        "mode": "auto" if has_api_key else "manual"
    }


@app.get("/metrics", tags=["Health"])
async def metrics_dashboard():
    """
    Telemetry and metrics dashboard.
    
    Returns application metrics including:
        - Form submission success rates
        - Voice processing latency
        - AI call performance
        - Error rates
    """
    from utils.telemetry import get_telemetry_dashboard
    from utils.circuit_breaker import _circuit_breakers
    
    dashboard = get_telemetry_dashboard()
    
    # Add circuit breaker status
    dashboard["circuit_breakers"] = {
        name: {
            "state": cb.state.value,
            "failures": cb.failure_count
        }
        for name, cb in _circuit_breakers.items()
    }
    
    return dashboard


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
