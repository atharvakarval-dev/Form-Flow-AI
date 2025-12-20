"""
API Response Caching Decorator

Provides caching for expensive API operations like form scraping.
Uses Redis when available, falls back to in-memory cache.

Usage:
    from utils.api_cache import cached_response
    
    @router.post("/scrape")
    @cached_response(ttl=3600, key_builder=lambda url: f"form:{url}")
    async def scrape_form(url: str):
        ...
"""

import hashlib
import json
from typing import Optional, Callable, Any
from functools import wraps

from utils.cache import get_cached, set_cached
from utils.logging import get_logger

logger = get_logger(__name__)


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a cache key from function arguments.
    
    Args:
        prefix: Cache key prefix (e.g., "form_schema")
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        str: MD5 hash-based cache key
    """
    # Create a string from all arguments
    key_parts = [prefix]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    
    key_string = "|".join(key_parts)
    
    # Hash for consistent length
    hash_value = hashlib.md5(key_string.encode()).hexdigest()[:16]
    
    return f"{prefix}:{hash_value}"


def cached_response(
    ttl: int = 3600,
    prefix: str = "api",
    key_builder: Optional[Callable] = None
):
    """
    Decorator to cache API responses in Redis.
    
    Args:
        ttl: Time-to-live in seconds (default: 1 hour)
        prefix: Cache key prefix
        key_builder: Optional custom function to build cache key
        
    Usage:
        @cached_response(ttl=3600, prefix="form_schema")
        async def scrape_form(url: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = generate_cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached = await get_cached(cache_key)
            if cached is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached
            
            logger.debug(f"Cache MISS: {cache_key}")
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                await set_cached(cache_key, result, ttl=ttl)
                logger.debug(f"Cached response: {cache_key} (TTL: {ttl}s)")
            
            return result
        
        return wrapper
    return decorator


async def cache_form_schema(url: str, schema: dict, ttl: int = 3600) -> None:
    """
    Cache a form schema by URL.
    
    Args:
        url: Form URL
        schema: Parsed form schema
        ttl: Cache time in seconds (default: 1 hour)
    """
    cache_key = f"form_schema:{hashlib.md5(url.encode()).hexdigest()[:16]}"
    await set_cached(cache_key, schema, ttl=ttl)
    logger.info(f"Cached form schema for: {url[:50]}...")


async def get_cached_form_schema(url: str) -> Optional[dict]:
    """
    Get cached form schema by URL.
    
    Args:
        url: Form URL
        
    Returns:
        Cached schema or None
    """
    cache_key = f"form_schema:{hashlib.md5(url.encode()).hexdigest()[:16]}"
    schema = await get_cached(cache_key)
    
    if schema:
        logger.info(f"Cache HIT for form: {url[:50]}...")
    
    return schema


async def invalidate_form_cache(url: str) -> None:
    """Invalidate cached form schema."""
    from utils.cache import delete_cached
    
    cache_key = f"form_schema:{hashlib.md5(url.encode()).hexdigest()[:16]}"
    await delete_cached(cache_key)
    logger.debug(f"Invalidated cache for: {url[:50]}...")
