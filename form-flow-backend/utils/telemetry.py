"""
Telemetry and Metrics Service

Provides structured logging, metrics collection, and observability endpoints
for monitoring application health and performance.

Usage:
    from utils.telemetry import metrics, track_event
    
    metrics.increment("form_submissions")
    metrics.timing("voice_latency", elapsed_ms)
    track_event("form_completed", {"fields": 10})
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
import asyncio

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    In-memory metrics collector for application observability.
    
    Collects counters, gauges, and timing metrics.
    """
    
    def __init__(self, retention_minutes: int = 60):
        self.retention_minutes = retention_minutes
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._timings: Dict[str, List[float]] = defaultdict(list)
        self._events: List[MetricPoint] = []
        self._last_cleanup: datetime = datetime.now()
    
    def increment(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        key = self._make_key(name, tags)
        self._counters[key] += value
        self._record_event(name, value, tags)
    
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric to a specific value."""
        key = self._make_key(name, tags)
        self._gauges[key] = value
        self._record_event(name, value, tags)
    
    def timing(self, name: str, value_ms: float, tags: Dict[str, str] = None):
        """Record a timing metric in milliseconds."""
        key = self._make_key(name, tags)
        self._timings[key].append(value_ms)
        self._record_event(name, value_ms, tags)
        
        # Keep only recent timings (last 1000)
        if len(self._timings[key]) > 1000:
            self._timings[key] = self._timings[key][-1000:]
    
    def _make_key(self, name: str, tags: Dict[str, str] = None) -> str:
        """Create a unique key for a metric."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def _record_event(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record an event for time-series analysis."""
        self._events.append(MetricPoint(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {}
        ))
        
        # Cleanup old events periodically
        if (datetime.now() - self._last_cleanup).seconds > 300:
            self._cleanup()
    
    def _cleanup(self):
        """Remove old events."""
        cutoff = datetime.now() - timedelta(minutes=self.retention_minutes)
        self._events = [e for e in self._events if e.timestamp > cutoff]
        self._last_cleanup = datetime.now()
    
    def get_counter(self, name: str, tags: Dict[str, str] = None) -> int:
        """Get current counter value."""
        key = self._make_key(name, tags)
        return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, tags: Dict[str, str] = None) -> Optional[float]:
        """Get current gauge value."""
        key = self._make_key(name, tags)
        return self._gauges.get(key)
    
    def get_timing_stats(self, name: str, tags: Dict[str, str] = None) -> Dict[str, float]:
        """Get timing statistics (avg, min, max, p95, p99)."""
        key = self._make_key(name, tags)
        values = self._timings.get(key, [])
        
        if not values:
            return {}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            "count": count,
            "avg": sum(sorted_values) / count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[count // 2],
            "p95": sorted_values[int(count * 0.95)] if count > 20 else sorted_values[-1],
            "p99": sorted_values[int(count * 0.99)] if count > 100 else sorted_values[-1]
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get overall metrics summary."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timings": {
                name: self.get_timing_stats(name.split("[")[0])
                for name in self._timings.keys()
            },
            "event_count": len(self._events),
            "collected_at": datetime.now().isoformat()
        }
    
    def reset(self):
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._timings.clear()
        self._events.clear()


# Global metrics instance
metrics = MetricsCollector()


def track_event(
    event_name: str,
    properties: Dict[str, Any] = None,
    user_id: Optional[str] = None
):
    """
    Track a business event for analytics.
    
    Args:
        event_name: Name of the event (e.g., "form_submitted")
        properties: Additional event properties
        user_id: Optional user identifier
    """
    props = properties or {}
    if user_id:
        props["user_id"] = user_id
    
    logger.info(
        "event_tracked",
        extra={
            "event": event_name,
            "properties": props,
            "timestamp": datetime.now().isoformat()
        }
    )
    
    # Also record as metric
    metrics.increment(f"event.{event_name}")


def timed(metric_name: str = None):
    """
    Decorator to measure function execution time.
    
    Example:
        @timed("api.form_submit")
        async def submit_form():
            ...
    """
    def decorator(func):
        name = metric_name or f"function.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                metrics.increment(f"{name}.success")
                return result
            except Exception as e:
                metrics.increment(f"{name}.error")
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                metrics.timing(name, elapsed_ms)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                metrics.increment(f"{name}.success")
                return result
            except Exception as e:
                metrics.increment(f"{name}.error")
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                metrics.timing(name, elapsed_ms)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Pre-defined metric keys for consistency
class MetricNames:
    """Standard metric names for the application."""
    
    # Form operations
    FORM_SCRAPE = "form.scrape"
    FORM_SUBMIT = "form.submit"
    FORM_FILL = "form.fill"
    
    # Voice operations
    VOICE_TRANSCRIBE = "voice.transcribe"
    VOICE_TTS = "voice.tts"
    VOICE_LATENCY = "voice.latency"
    
    # AI operations
    AI_GEMINI_CALL = "ai.gemini.call"
    AI_CONVERSATION = "ai.conversation"
    AI_EXTRACTION = "ai.extraction"
    
    # Session operations
    SESSION_CREATE = "session.create"
    SESSION_END = "session.end"
    SESSION_ACTIVE = "session.active"
    
    # Errors
    ERROR_RATE = "error.rate"
    ERROR_API = "error.api"
    ERROR_VALIDATION = "error.validation"


def get_telemetry_dashboard() -> Dict[str, Any]:
    """
    Get a comprehensive telemetry dashboard.
    
    Returns data suitable for a monitoring UI.
    """
    summary = metrics.get_summary()
    
    # Calculate derived metrics
    form_success = metrics.get_counter(f"{MetricNames.FORM_SUBMIT}.success")
    form_error = metrics.get_counter(f"{MetricNames.FORM_SUBMIT}.error")
    total_forms = form_success + form_error
    success_rate = (form_success / total_forms * 100) if total_forms > 0 else 100
    
    return {
        "overview": {
            "forms_submitted": total_forms,
            "success_rate_pct": round(success_rate, 2),
            "active_sessions": metrics.get_gauge(MetricNames.SESSION_ACTIVE) or 0
        },
        "performance": {
            "voice_latency": metrics.get_timing_stats(MetricNames.VOICE_LATENCY),
            "ai_latency": metrics.get_timing_stats(MetricNames.AI_GEMINI_CALL),
            "form_fill_time": metrics.get_timing_stats(MetricNames.FORM_FILL)
        },
        "errors": {
            "api_errors": metrics.get_counter(MetricNames.ERROR_API),
            "validation_errors": metrics.get_counter(MetricNames.ERROR_VALIDATION)
        },
        "raw": summary,
        "generated_at": datetime.now().isoformat()
    }
