"""
Redis Cache Utility

Provides Redis connection and caching utilities for the application.
Falls back to in-memory cache if Redis is not configured.

Usage:
    from utils.cache import cache, get_cached, set_cached
    
    # Simple caching
    await set_cached("key", {"data": "value"}, ttl=300)
    data = await get_cached("key")
"""

import json
from typing import Optional, Any
from functools import lru_cache

from config.settings import settings
from utils.logging import get_logger

logger = get_logger(__name__)

# Redis client (lazy loaded)
_redis_client = None
_redis_available = None


async def get_redis_client():
    """
    Get Redis client with lazy initialization.
    
    Returns None if Redis is not configured or unavailable.
    """
    global _redis_client, _redis_available
    
    # Already checked and not available
    if _redis_available is False:
        return None
    
    # Already connected
    if _redis_client is not None:
        return _redis_client
    
    # No Redis URL configured
    if not settings.REDIS_URL:
        logger.info("Redis not configured - using in-memory cache")
        _redis_available = False
        return None
    
    try:
        import redis.asyncio as redis
        
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        
        # Test connection
        await _redis_client.ping()
        logger.info("✅ Redis connected successfully")
        _redis_available = True
        return _redis_client
        
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - using in-memory cache")
        _redis_available = False
        return None


# =============================================================================
# In-Memory Fallback Cache with TTL Support
# =============================================================================

import time
from typing import Tuple

_memory_cache: dict = {}
_memory_cache_ttl: dict = {}  # Track expiration times


# =============================================================================
# Cache Operations
# =============================================================================

async def get_cached(key: str) -> Optional[Any]:
    """
    Get value from cache with robust error handling.
    
    Args:
        key: Cache key
        
    Returns:
        Cached value or None if not found/corrupted
    """
    redis = await get_redis_client()
    
    if redis:
        try:
            value = await redis.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError as e:
                    logger.warning(f"Corrupted cache data for key '{key}': {e}")
                    # Delete corrupted key to prevent repeated errors
                    try:
                        await redis.delete(key)
                    except Exception:
                        pass
                    return None
        except Exception as e:
            logger.debug(f"Redis get failed: {e}")
    
    # Check memory cache with TTL validation
    if key in _memory_cache:
        if key in _memory_cache_ttl:
            if time.time() > _memory_cache_ttl[key]:
                # Expired - remove from cache
                del _memory_cache[key]
                del _memory_cache_ttl[key]
                return None
        return _memory_cache[key]
    
    return None


async def set_cached(
    key: str,
    value: Any,
    ttl: int = 300  # 5 minutes default
) -> bool:
    """
    Set value in cache with TTL support.
    
    Args:
        key: Cache key
        value: Value to cache (must be JSON serializable)
        ttl: Time-to-live in seconds
        
    Returns:
        True if cached successfully
    """
    redis = await get_redis_client()
    
    if redis:
        try:
            await redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.debug(f"Redis set failed: {e}")
    
    # Fallback to memory with TTL tracking
    _memory_cache[key] = value
    _memory_cache_ttl[key] = time.time() + ttl
    return True


async def delete_cached(key: str) -> bool:
    """Delete value from cache."""
    redis = await get_redis_client()
    
    if redis:
        try:
            await redis.delete(key)
        except Exception:
            pass
    
    # Remove from memory cache and TTL tracking
    _memory_cache.pop(key, None)
    _memory_cache_ttl.pop(key, None)
    return True


async def clear_cache_pattern(pattern: str) -> int:
    """
    Clear all keys matching pattern.
    
    Args:
        pattern: Redis pattern (e.g., "speech:*")
        
    Returns:
        Number of keys deleted
    """
    redis = await get_redis_client()
    count = 0
    
    if redis:
        try:
            async for key in redis.scan_iter(match=pattern):
                await redis.delete(key)
                count += 1
        except Exception as e:
            logger.debug(f"Redis pattern clear failed: {e}")
    
    # Clear from memory cache too
    pattern_prefix = pattern.replace("*", "")
    keys_to_delete = [k for k in _memory_cache if k.startswith(pattern_prefix)]
    for key in keys_to_delete:
        del _memory_cache[key]
        _memory_cache_ttl.pop(key, None)  # Also remove TTL entry
        count += 1
    
    return count


# =============================================================================
# Health Check
# =============================================================================

async def check_redis_health() -> bool:
    """Check if Redis is connected and healthy."""
    redis = await get_redis_client()
    if redis:
        try:
            await redis.ping()
            return True
        except Exception:
            return False
    return False
