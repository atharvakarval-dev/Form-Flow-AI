"""
Database Connector Package

Provides connectors for external databases used by plugins.

Supported:
- PostgreSQL (asyncpg with connection pooling)
- MySQL (aiomysql with connection pooling)

All connectors:
- Use parameterized queries (SQL injection safe)
- Have circuit breaker protection
- Support schema introspection
- Cache connections per plugin
"""

from services.plugin.database.base import (
    DatabaseType,
    ConnectionConfig,
    DatabaseConnector,
    ConnectorFactory,
    get_connector_factory,
    ColumnInfo,
    TableInfo,
)
from services.plugin.database.schema_validator import (
    SchemaValidationService,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    get_schema_validator,
)

__all__ = [
    "DatabaseType",
    "ConnectionConfig",
    "DatabaseConnector",
    "ConnectorFactory",
    "get_connector_factory",
    "ColumnInfo",
    "TableInfo",
    "SchemaValidationService",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "get_schema_validator",
]
