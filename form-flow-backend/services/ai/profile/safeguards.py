"""
Production Safeguards

Implements stability patterns:
1. Circuit Breaker: To fail fast when LLM APIs are down/erroring.
2. Rate Limiter: To prevent abuse and control costs.
"""

import time
from typing import Dict, Tuple
from .config import profile_config
from utils.logging import get_logger

logger = get_logger(__name__)

class CircuitBreaker:
    """
    Simple state machine for circuit breaking.
    States: CLOSED (Normal), OPEN (Failing, reject requests), HALF-OPEN (Testing)
    """
    def __init__(self):
        self.failures = 0
        self.last_failure_time = 0
        self.is_open = False
        self._max_failures = profile_config.MAX_CONSECUTIVE_FAILURES
        self._reset_timeout = profile_config.CIRCUIT_RESET_TIMEOUT

    def can_proceed(self) -> bool:
        """Check if request should be allowed."""
        if not self.is_open:
            return True
        
        # Check if timeout has passed (Half-Open logic)
        if time.time() - self.last_failure_time > self._reset_timeout:
            return True # Allow one request to try
            
        return False

    def record_success(self):
        """Reset failures on success."""
        if self.failures > 0 or self.is_open:
            logger.info("Circuit Breaker: Recovered/Reset. Failures cleared.")
        self.failures = 0
        self.is_open = False

    def record_failure(self):
        """Record a failure and potentially open circuit."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self._max_failures:
            if not self.is_open:
                logger.error(f"Circuit Breaker: OPENED after {self.failures} failures. Requests blocked for {self._reset_timeout}s.")
            self.is_open = True

class RateLimiter:
    """
    In-memory Token Bucket or Sliding Window rate limiter.
    Using simplified sliding window for this implementation.
    """
    def __init__(self):
        # Map user_id -> list of timestamps
        self._requests: Dict[int, list] = {}
        self._limit = profile_config.MAX_UPDATES_PER_HOUR
        self._window = 3600 # 1 hour in seconds

    def check_limit(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if user is within rate limits.
        Returns (is_allowed, reason)
        """
        now = time.time()
        
        if user_id not in self._requests:
            self._requests[user_id] = []
            
        # Clean old requests
        self._requests[user_id] = [t for t in self._requests[user_id] if now - t < self._window]
        
        # Check count
        current_count = len(self._requests[user_id])
        if current_count >= self._limit:
            wait_time = int(self._window - (now - self._requests[user_id][0])) if self._requests[user_id] else 60
            return False, f"Rate limit exceeded. Try again in {wait_time}s."
            
        return True, "Allowed"

    def record_request(self, user_id: int):
        """Record a successful request consumption."""
        if user_id not in self._requests:
            self._requests[user_id] = []
        self._requests[user_id].append(time.time())

# Singleton instances
circuit_breaker = CircuitBreaker()
rate_limiter = RateLimiter()
