"""
Webhook Service Module

Notifies external systems about population events.
Features:
- HMAC signature for security
- Retry with exponential backoff
- Async fire-and-forget delivery
- Event types (success, failure, partial)

Uses circuit breaker for resilient delivery.
"""

import hmac
import hashlib
import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import httpx

from utils.circuit_breaker import resilient_call, get_circuit_breaker
from utils.logging import get_logger

logger = get_logger(__name__)


class WebhookEvent(str, Enum):
    """Webhook event types."""
    POPULATION_SUCCESS = "population.success"
    POPULATION_FAILED = "population.failed"
    POPULATION_PARTIAL = "population.partial"
    SESSION_STARTED = "session.started"
    SESSION_COMPLETED = "session.completed"
    SESSION_EXPIRED = "session.expired"


@dataclass
class WebhookConfig:
    """Webhook configuration from plugin settings."""
    url: str
    secret: str
    events: List[str] = field(default_factory=list)
    timeout_seconds: int = 10
    max_retries: int = 3
    enabled: bool = True


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt."""
    event: WebhookEvent
    payload: Dict[str, Any]
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    succeeded: bool = False
    duration_ms: int = 0


class WebhookService:
    """
    Webhook delivery service.
    
    Sends webhooks to external systems with:
    - HMAC-SHA256 signature verification
    - Retry with exponential backoff
    - Circuit breaker protection
    
    Usage:
        service = WebhookService()
        await service.send(
            config=webhook_config,
            event=WebhookEvent.POPULATION_SUCCESS,
            payload={"session_id": "abc", "inserted": 5}
        )
    """
    
    SIGNATURE_HEADER = "X-FormFlow-Signature"
    TIMESTAMP_HEADER = "X-FormFlow-Timestamp"
    EVENT_HEADER = "X-FormFlow-Event"
    
    # Retry backoff (seconds): 1, 4, 16
    RETRY_BASE = 1
    RETRY_MULTIPLIER = 4
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initialize webhook service.
        
        Args:
            http_client: Optional pre-configured HTTP client
        """
        self._client = http_client
        self._pending_deliveries: List[WebhookDelivery] = []
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True
            )
        return self._client
    
    def _sign_payload(self, payload: str, secret: str, timestamp: str) -> str:
        """
        Create HMAC-SHA256 signature.
        
        Signature format: sha256=HMAC(secret, timestamp.payload)
        """
        message = f"{timestamp}.{payload}"
        signature = hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    def _should_send(self, config: WebhookConfig, event: WebhookEvent) -> bool:
        """Check if event should be sent based on config."""
        if not config.enabled:
            return False
        
        if not config.events:
            return True  # Send all events if not filtered
        
        return event.value in config.events
    
    async def send(
        self,
        config: WebhookConfig,
        event: WebhookEvent,
        payload: Dict[str, Any],
        plugin_id: int = 0
    ) -> WebhookDelivery:
        """
        Send a webhook.
        
        Args:
            config: Webhook configuration
            event: Event type
            payload: Payload data
            plugin_id: Plugin ID for circuit breaker
            
        Returns:
            WebhookDelivery with result
        """
        delivery = WebhookDelivery(event=event, payload=payload)
        
        if not self._should_send(config, event):
            logger.debug(f"Skipping webhook {event.value} (not in allowed events)")
            return delivery
        
        # Add metadata to payload
        timestamp = datetime.utcnow().isoformat()
        full_payload = {
            "event": event.value,
            "timestamp": timestamp,
            "data": payload
        }
        
        payload_json = json.dumps(full_payload, default=str)
        signature = self._sign_payload(payload_json, config.secret, timestamp)
        
        headers = {
            "Content-Type": "application/json",
            self.SIGNATURE_HEADER: signature,
            self.TIMESTAMP_HEADER: timestamp,
            self.EVENT_HEADER: event.value,
        }
        
        # Send with retry
        start_time = datetime.now()
        
        try:
            async def do_send():
                client = await self._get_client()
                response = await client.post(
                    config.url,
                    content=payload_json,
                    headers=headers,
                    timeout=config.timeout_seconds
                )
                return response
            
            response = await resilient_call(
                do_send,
                max_retries=config.max_retries,
                circuit_name=f"webhook_{plugin_id}"
            )
            
            delivery.status_code = response.status_code
            delivery.response_body = response.text[:500]  # Truncate
            delivery.succeeded = 200 <= response.status_code < 300
            delivery.attempts = 1  # At least 1 attempt
            
            if delivery.succeeded:
                logger.info(f"Webhook {event.value} delivered to {config.url}")
            else:
                logger.warning(f"Webhook {event.value} failed: {response.status_code}")
        
        except Exception as e:
            delivery.error = str(e)
            logger.error(f"Webhook {event.value} error: {e}")
        
        delivery.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return delivery
    
    async def send_fire_and_forget(
        self,
        config: WebhookConfig,
        event: WebhookEvent,
        payload: Dict[str, Any],
        plugin_id: int = 0
    ) -> None:
        """
        Send webhook without waiting for result.
        
        Used for non-critical notifications where we don't want
        to block the main flow.
        """
        asyncio.create_task(
            self._send_with_logging(config, event, payload, plugin_id)
        )
    
    async def _send_with_logging(
        self,
        config: WebhookConfig,
        event: WebhookEvent,
        payload: Dict[str, Any],
        plugin_id: int
    ) -> None:
        """Helper for fire-and-forget with logging."""
        try:
            delivery = await self.send(config, event, payload, plugin_id)
            if not delivery.succeeded and delivery.error:
                logger.warning(f"Background webhook failed: {delivery.error}")
        except Exception as e:
            logger.error(f"Background webhook exception: {e}")
    
    async def send_batch(
        self,
        configs: List[WebhookConfig],
        event: WebhookEvent,
        payload: Dict[str, Any],
        plugin_id: int = 0
    ) -> List[WebhookDelivery]:
        """
        Send to multiple webhook endpoints concurrently.
        
        Used when a plugin has multiple webhook URLs configured.
        """
        tasks = [
            self.send(config, event, payload, plugin_id)
            for config in configs
            if self._should_send(config, event)
        ]
        
        if not tasks:
            return []
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    @staticmethod
    def verify_signature(
        payload: str,
        secret: str,
        timestamp: str,
        signature: str
    ) -> bool:
        """
        Verify incoming webhook signature.
        
        Useful for receiving webhooks from external sources.
        Can be used in reverse when other systems call our endpoints.
        """
        expected = f"sha256={hmac.new(secret.encode(), f'{timestamp}.{payload}'.encode(), hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(signature, expected)
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_webhook_service: Optional[WebhookService] = None


def get_webhook_service(
    http_client: Optional[httpx.AsyncClient] = None
) -> WebhookService:
    """Get singleton webhook service."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService(http_client)
    return _webhook_service
