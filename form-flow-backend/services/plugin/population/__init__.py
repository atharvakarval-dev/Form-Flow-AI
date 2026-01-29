"""
Plugin Database Population Package

Provides database population for plugins:
- PopulationService: Transaction management and batch inserts
- DeadLetterQueue: Failed insert retry with backoff
- WebhookService: Event notifications with HMAC signatures

All components follow DRY principles and reuse existing infrastructure.
"""

from services.plugin.population.service import (
    PopulationService,
    PopulationResult,
    InsertResult,
    InsertStatus,
    get_population_service,
)
from services.plugin.population.dead_letter import (
    DeadLetterQueue,
    DeadLetterEntry,
    DLQEntry,
    DLQStatus,
    get_dead_letter_queue,
)
from services.plugin.population.webhooks import (
    WebhookService,
    WebhookConfig,
    WebhookDelivery,
    WebhookEvent,
    get_webhook_service,
)

__all__ = [
    # Population Service
    "PopulationService",
    "PopulationResult",
    "InsertResult",
    "InsertStatus",
    "get_population_service",
    # Dead Letter Queue
    "DeadLetterQueue",
    "DeadLetterEntry",
    "DLQEntry",
    "DLQStatus",
    "get_dead_letter_queue",
    # Webhooks
    "WebhookService",
    "WebhookConfig",
    "WebhookDelivery",
    "WebhookEvent",
    "get_webhook_service",
]
