"""
Multi-Level Rate Limiter Module

Production-grade rate limiting at multiple levels:
- API Key: Per-key limits (configured per key)
- Plugin: Per-plugin limits (prevent single plugin DoS)
- User: Per-user limits (prevent abuse)
- IP: Per-IP limits (prevent distributed attacks)

Uses Redis for distributed rate limiting (falls back to in-memory).
Sliding window algorithm for accurate limiting.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import asyncio
import time

from config.settings import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitLevel(Enum):
    """Rate limit levels with default limits."""
    API_KEY = "api_key"      # Configured per key
    PLUGIN = "plugin"        # 1000/hour
    USER = "user"            # 500/hour
    IP = "ip"                # 200/minute


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit level."""
    requests: int
    window_seconds: int
    
    @property
    def window_minutes(self) -> float:
        return self.window_seconds / 60


# Default configurations per level
DEFAULT_LIMITS: Dict[RateLimitLevel, RateLimitConfig] = {
    RateLimitLevel.API_KEY: RateLimitConfig(100, 60),    # 100/minute (overridden by key config)
    RateLimitLevel.PLUGIN: RateLimitConfig(1000, 3600),  # 1000/hour
    RateLimitLevel.USER: RateLimitConfig(500, 3600),     # 500/hour
    RateLimitLevel.IP: RateLimitConfig(200, 60),         # 200/minute
}


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    level: Optional[RateLimitLevel] = None  # Which level denied (if any)
    current_count: int = 0
    limit: int = 0
    reset_at: Optional[datetime] = None
    retry_after_seconds: int = 0
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.limit - self.current_count)),
        }
        if self.reset_at:
            headers["X-RateLimit-Reset"] = str(int(self.reset_at.timestamp()))
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after_seconds)
        return headers


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter for development/single-instance.
    
    Uses sliding window algorithm with per-key tracking.
    Not suitable for multi-instance deployments.
    """
    
    def __init__(self):
        self._windows: Dict[str, Dict[float, int]] = {}
        self._lock = asyncio.Lock()
    
    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> Tuple[bool, int, datetime]:
        """
        Check if request is allowed and increment counter.
        
        Returns: (allowed, current_count, reset_time)
        """
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            
            # Initialize or get window
            if key not in self._windows:
                self._windows[key] = {}
            
            window = self._windows[key]
            
            # Clean old entries
            window = {ts: count for ts, count in window.items() if ts > window_start}
            self._windows[key] = window
            
            # Count current requests
            current_count = sum(window.values())
            
            # Check limit
            if current_count >= limit:
                reset_at = datetime.fromtimestamp(min(window.keys()) + window_seconds)
                return False, current_count, reset_at
            
            # Increment
            window[now] = window.get(now, 0) + 1
            reset_at = datetime.fromtimestamp(now + window_seconds)
            
            return True, current_count + 1, reset_at
    
    async def get_count(self, key: str, window_seconds: int) -> int:
        """Get current count without incrementing."""
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            
            if key not in self._windows:
                return 0
            
            window = self._windows[key]
            return sum(count for ts, count in window.items() if ts > window_start)


class RedisRateLimiter:
    """
    Redis-based rate limiter for production/multi-instance.
    
    Uses sliding window log algorithm with sorted sets.
    Falls back to in-memory if Redis unavailable.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or settings.REDIS_URL
        self._redis = None
        self._fallback = InMemoryRateLimiter()
    
    async def _get_redis(self):
        """Lazy initialize Redis connection."""
        if self._redis is None and self._redis_url:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self._redis_url)
                await self._redis.ping()
                logger.info("Multi-level rate limiter using Redis")
            except Exception as e:
                logger.warning(f"Redis unavailable, using in-memory: {e}")
                self._redis = False  # Mark as unavailable
        return self._redis if self._redis else None
    
    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> Tuple[bool, int, datetime]:
        """Check and increment using Redis sorted set."""
        redis = await self._get_redis()
        
        if not redis:
            return await self._fallback.check_and_increment(key, limit, window_seconds)
        
        try:
            now = time.time()
            window_start = now - window_seconds
            
            pipe = redis.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current
            pipe.zcard(key)
            
            # Add new entry
            pipe.zadd(key, {str(now): now})
            
            # Set expiry
            pipe.expire(key, window_seconds + 1)
            
            results = await pipe.execute()
            current_count = results[1]
            
            if current_count >= limit:
                # Get oldest timestamp for reset time
                oldest = await redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    reset_at = datetime.fromtimestamp(oldest[0][1] + window_seconds)
                else:
                    reset_at = datetime.fromtimestamp(now + window_seconds)
                return False, current_count, reset_at
            
            reset_at = datetime.fromtimestamp(now + window_seconds)
            return True, current_count + 1, reset_at
            
        except Exception as e:
            logger.warning(f"Redis error, falling back: {e}")
            return await self._fallback.check_and_increment(key, limit, window_seconds)


class MultiLevelRateLimiter:
    """
    Multi-level rate limiter checking all configured levels.
    
    Checks in order: IP -> User -> Plugin -> API Key
    Stops at first failure.
    
    Usage:
        limiter = get_rate_limiter()
        result = await limiter.check(
            api_key_id=123,
            api_key_limit=100,
            plugin_id=456,
            user_id=789,
            ip_address="192.168.1.1"
        )
        if not result.allowed:
            raise HTTPException(429, headers=result.to_headers())
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self._backend = RedisRateLimiter(redis_url)
    
    def _make_key(self, level: RateLimitLevel, identifier: str) -> str:
        """Create cache key for rate limit."""
        return f"ratelimit:{level.value}:{identifier}"
    
    async def check(
        self,
        api_key_id: Optional[int] = None,
        api_key_limit: Optional[int] = None,  # From PluginAPIKey.rate_limit
        plugin_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> RateLimitResult:
        """
        Check all rate limits.
        
        Checks in order: IP -> User -> Plugin -> API Key
        Returns on first failure or success if all pass.
        """
        checks = []
        
        # Build check list (order matters: most general first)
        if ip_address:
            config = DEFAULT_LIMITS[RateLimitLevel.IP]
            checks.append((RateLimitLevel.IP, ip_address, config.requests, config.window_seconds))
        
        if user_id:
            config = DEFAULT_LIMITS[RateLimitLevel.USER]
            checks.append((RateLimitLevel.USER, str(user_id), config.requests, config.window_seconds))
        
        if plugin_id:
            config = DEFAULT_LIMITS[RateLimitLevel.PLUGIN]
            checks.append((RateLimitLevel.PLUGIN, str(plugin_id), config.requests, config.window_seconds))
        
        if api_key_id:
            limit = api_key_limit or DEFAULT_LIMITS[RateLimitLevel.API_KEY].requests
            window = DEFAULT_LIMITS[RateLimitLevel.API_KEY].window_seconds
            checks.append((RateLimitLevel.API_KEY, str(api_key_id), limit, window))
        
        # Check each level
        for level, identifier, limit, window in checks:
            key = self._make_key(level, identifier)
            allowed, count, reset_at = await self._backend.check_and_increment(key, limit, window)
            
            if not allowed:
                retry_after = int((reset_at - datetime.now()).total_seconds())
                return RateLimitResult(
                    allowed=False,
                    level=level,
                    current_count=count,
                    limit=limit,
                    reset_at=reset_at,
                    retry_after_seconds=max(1, retry_after)
                )
        
        # All checks passed - return last check's info (most specific)
        if checks:
            _, _, limit, _ = checks[-1]
            return RateLimitResult(
                allowed=True,
                current_count=count if 'count' in dir() else 0,
                limit=limit,
                reset_at=reset_at if 'reset_at' in dir() else None
            )
        
        return RateLimitResult(allowed=True)
    
    async def get_usage(
        self,
        level: RateLimitLevel,
        identifier: str
    ) -> Dict[str, int]:
        """Get current usage for a specific level/identifier."""
        config = DEFAULT_LIMITS[level]
        key = self._make_key(level, identifier)
        
        count = await self._backend._fallback.get_count(key, config.window_seconds)
        
        return {
            "current": count,
            "limit": config.requests,
            "window_seconds": config.window_seconds,
            "remaining": max(0, config.requests - count)
        }


@lru_cache(maxsize=1)
def get_rate_limiter() -> MultiLevelRateLimiter:
    """Get singleton rate limiter instance."""
    return MultiLevelRateLimiter(settings.REDIS_URL)
