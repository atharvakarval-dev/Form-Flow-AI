"""
Rate Limiting Middleware

Provides request rate limiting using Redis (production) or in-memory (development).
Uses slowapi for FastAPI-compatible rate limiting.

Usage:
    from utils.rate_limit import limiter, rate_limit_exceeded_handler
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from config.settings import settings
from utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Rate Limiter Configuration
# =============================================================================

def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.
    
    Handles X-Forwarded-For header for requests behind a proxy/load balancer.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _get_storage_uri() -> str:
    """
    Get storage URI for rate limiter.
    
    Uses Redis if configured, otherwise falls back to in-memory.
    """
    if settings.REDIS_URL:
        logger.info("Rate limiter using Redis storage")
        return settings.REDIS_URL
    else:
        logger.info("Rate limiter using in-memory storage")
        return "memory://"


# Create limiter instance with appropriate storage
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["200/minute"],  # Higher default for scaling
    storage_uri=_get_storage_uri(),
)


# =============================================================================
# Rate Limit Presets
# =============================================================================

RATE_LIMITS = {
    "auth": "10/minute",       # Login/register
    "scrape": "20/minute",     # Form scraping (resource intensive)
    "submit": "30/minute",     # Form submission
    "speech": "60/minute",     # TTS/STT
    "default": "200/minute",   # General endpoints
}


# =============================================================================
# Exception Handler
# =============================================================================

async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded
) -> JSONResponse:
    """Handle rate limit exceeded exceptions."""
    client_ip = get_client_ip(request)
    logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "RateLimitExceeded",
            "message": f"Too many requests. Limit: {exc.detail}",
            "retry_after": "60 seconds"
        },
        headers={"Retry-After": "60"}
    )


# =============================================================================
# Decorator Helpers
# =============================================================================

def limit_auth(func):
    """Apply auth rate limit."""
    return limiter.limit(RATE_LIMITS["auth"])(func)


def limit_scrape(func):
    """Apply scrape rate limit."""
    return limiter.limit(RATE_LIMITS["scrape"])(func)


def limit_submit(func):
    """Apply submit rate limit."""
    return limiter.limit(RATE_LIMITS["submit"])(func)


def limit_speech(func):
    """Apply speech rate limit."""
    return limiter.limit(RATE_LIMITS["speech"])(func)
