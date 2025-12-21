"""
Circuit Breaker and Resilience Utilities

Provides retry logic, fallback chains, and circuit breaker patterns
for robust external API calls.

Usage:
    from utils.circuit_breaker import resilient_call, with_fallback
    
    result = await resilient_call(primary_function, max_retries=3)
    result = await with_fallback([func1, func2, func3])
"""

import asyncio
from typing import Callable, TypeVar, List, Optional, Any
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    When failures exceed threshold, circuit opens and rejects calls
    for a cooldown period before allowing test calls through.
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout: int = 30  # seconds
    half_open_calls: int = 3
    
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    success_count: int = field(default=0)
    last_failure_time: Optional[datetime] = field(default=None)
    
    def can_execute(self) -> bool:
        """Check if a call can be made."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).seconds
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit {self.name} entering half-open state")
                    return True
            return False
        
        # HALF_OPEN: allow limited calls
        return True
    
    def record_success(self):
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit {self.name} closed (recovered)")
        else:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during testing, go back to open
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} reopened (half-open failure)")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} opened (threshold exceeded)")


# Global circuit breaker registry
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _circuit_breakers[name]


async def resilient_call(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    circuit_name: Optional[str] = None,
    **kwargs
) -> T:
    """
    Execute a function with retry logic and exponential backoff.
    
    Args:
        func: Async function to execute
        max_retries: Maximum retry attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        circuit_name: Optional circuit breaker name
    
    Returns:
        Result from the function
        
    Raises:
        Exception: Last exception if all retries fail
    """
    circuit = get_circuit_breaker(circuit_name) if circuit_name else None
    
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        # Check circuit breaker
        if circuit and not circuit.can_execute():
            logger.warning(f"Circuit {circuit_name} is open, skipping call")
            raise Exception(f"Circuit breaker {circuit_name} is open")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            if circuit:
                circuit.record_success()
            
            return result
            
        except Exception as e:
            last_exception = e
            
            if circuit:
                circuit.record_failure()
            
            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * exponential_base, max_delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")
    
    raise last_exception


async def with_fallback(
    functions: List[Callable[..., T]],
    *args,
    **kwargs
) -> T:
    """
    Try functions in order until one succeeds.
    
    Args:
        functions: List of functions to try in order
        *args, **kwargs: Arguments to pass to each function
        
    Returns:
        Result from first successful function
        
    Raises:
        Exception: If all functions fail
    """
    last_exception = None
    
    for i, func in enumerate(functions):
        try:
            func_name = getattr(func, '__name__', f'function_{i}')
            logger.debug(f"Trying fallback function: {func_name}")
            
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            logger.info(f"Fallback succeeded with: {func_name}")
            return result
            
        except Exception as e:
            last_exception = e
            logger.warning(f"Fallback {i + 1}/{len(functions)} failed: {e}")
    
    logger.error(f"All {len(functions)} fallback functions failed")
    raise last_exception


def circuit_protected(name: str, **circuit_kwargs):
    """
    Decorator to protect a function with a circuit breaker.
    
    Example:
        @circuit_protected("gemini_api")
        async def call_gemini():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await resilient_call(
                func, *args,
                circuit_name=name,
                **circuit_kwargs,
                **kwargs
            )
        return wrapper
    return decorator


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exceptions: tuple = (Exception,)
):
    """
    Simple retry decorator.
    
    Example:
        @retry(max_retries=3)
        async def unstable_function():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
                        delay *= 2
            
            raise last_exception
        return wrapper
    return decorator


class ResilientService:
    """
    Base class for services that need resilience patterns.
    
    Provides retry, fallback, and circuit breaker functionality.
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.circuit = get_circuit_breaker(
            service_name,
            failure_threshold=5,
            recovery_timeout=60
        )
    
    async def call_with_retry(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        **kwargs
    ):
        """Execute function with retry logic."""
        return await resilient_call(
            func, *args,
            max_retries=max_retries,
            circuit_name=self.service_name,
            **kwargs
        )
    
    async def call_with_fallback(
        self,
        primary: Callable,
        fallbacks: List[Callable],
        *args,
        **kwargs
    ):
        """Execute primary function with fallbacks."""
        return await with_fallback(
            [primary] + fallbacks,
            *args,
            **kwargs
        )
    
    @property
    def is_healthy(self) -> bool:
        """Check if service circuit is healthy."""
        return self.circuit.state == CircuitState.CLOSED
    
    @property
    def status(self) -> dict:
        """Get circuit breaker status."""
        return {
            "service": self.service_name,
            "state": self.circuit.state.value,
            "failure_count": self.circuit.failure_count,
            "is_healthy": self.is_healthy
        }
