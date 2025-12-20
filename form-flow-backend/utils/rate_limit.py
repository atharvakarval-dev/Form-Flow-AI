"""
Rate Limiting Middleware

Provides request rate limiting to prevent abuse and ensure fair usage.
Uses slowapi for FastAPI-compatible rate limiting with in-memory storage.

Usage:
    from utils.rate_limit import limiter, rate_limit_exceeded_handler
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    
    @router.post("/endpoint")
    @limiter.limit("10/minute")
    async def my_endpoint(request: Request):
        ...
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Rate Limiter Configuration
# =============================================================================

def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.
    
    Handles X-Forwarded-For header for requests behind a proxy/load balancer.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Client IP address
    """
    # Check X-Forwarded-For header (for reverse proxy setups)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (client IP)
        return forwarded.split(",")[0].strip()
    
    # Fall back to direct client IP
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["100/minute"],  # Default limit for all endpoints
    storage_uri="memory://",  # Use Redis in production: "redis://localhost:6379"
)


# =============================================================================
# Rate Limit Presets
# =============================================================================

# Rate limit presets for different endpoint types
RATE_LIMITS = {
    "auth": "5/minute",        # Login/register - strict limit
    "scrape": "10/minute",     # Form scraping - resource intensive
    "submit": "20/minute",     # Form submission
    "speech": "30/minute",     # TTS/STT - API calls
    "default": "100/minute",   # General endpoints
}


# =============================================================================
# Exception Handler
# =============================================================================

async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded
) -> JSONResponse:
    """
    Handle rate limit exceeded exceptions.
    
    Returns a standardized JSON error response with retry information.
    
    Args:
        request: The request that exceeded the limit
        exc: The rate limit exception
        
    Returns:
        JSONResponse: Error response with 429 status code
    """
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
    """Apply auth rate limit (5/minute)."""
    return limiter.limit(RATE_LIMITS["auth"])(func)


def limit_scrape(func):
    """Apply scrape rate limit (10/minute)."""
    return limiter.limit(RATE_LIMITS["scrape"])(func)


def limit_submit(func):
    """Apply submit rate limit (20/minute)."""
    return limiter.limit(RATE_LIMITS["submit"])(func)


def limit_speech(func):
    """Apply speech rate limit (30/minute)."""
    return limiter.limit(RATE_LIMITS["speech"])(func)
