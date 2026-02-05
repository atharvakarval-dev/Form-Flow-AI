"""
Security Audit Log Models

SQLAlchemy models for security audit logging.
Tracks all security-sensitive operations for compliance and debugging.

Single table design with JSON payload for flexibility without schema bloat.
Indexed for efficient querying by user, action type, and time range.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Index, JSON
from sqlalchemy.sql import func

from core.database import Base


class AuditLog(Base):
    """
    Security audit log for tracking sensitive operations.
    
    Captures:
    - API key operations (create, revoke, use)
    - Plugin access and modifications
    - Data exports and deletions (GDPR)
    - Authentication failures
    
    Design:
    - Single table with JSON payload for flexibility
    - No foreign keys (logs survive entity deletion)
    - Indexed for common query patterns
    """
    
    __tablename__ = "audit_logs"
    __table_args__ = (
        # Composite index for user + time range queries
        Index("ix_audit_user_time", "user_id", "created_at"),
        # Index for action type filtering
        Index("ix_audit_action", "action"),
        # Index for entity lookups
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Who performed the action
    user_id = Column(Integer, nullable=True, index=True)  # None for API key auth
    api_key_prefix = Column(String(12), nullable=True)  # For API key operations
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(String(500), nullable=True)
    
    # What action was performed
    action = Column(String(50), nullable=False)
    # Actions: api_key_created, api_key_revoked, api_key_rotated, api_key_used,
    #          plugin_created, plugin_updated, plugin_deleted,
    #          data_exported, data_deleted, auth_failed
    
    # Target entity
    entity_type = Column(String(50), nullable=True)  # plugin, api_key, user
    entity_id = Column(Integer, nullable=True)
    
    # Details (flexible JSON payload)
    details = Column(JSON, nullable=True)
    # Examples:
    # - api_key_created: {"key_prefix": "ffp_abc1", "expires_in_days": 30}
    # - data_exported: {"tables_exported": ["users", "orders"], "record_count": 150}
    # - auth_failed: {"reason": "expired", "key_prefix": "ffp_xyz9"}
    
    # Outcome
    success = Column(String(10), default="success", nullable=False)  # success, failure
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', user={self.user_id})>"


# =============================================================================
# Audit Action Constants (DRY - reuse across services)
# =============================================================================

class AuditAction:
    """Audit action type constants."""
    
    # API Key actions
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_ROTATED = "api_key_rotated"
    API_KEY_USED = "api_key_used"
    API_KEY_RATE_LIMITED = "api_key_rate_limited"
    
    # Plugin actions
    PLUGIN_CREATED = "plugin_created"
    PLUGIN_UPDATED = "plugin_updated"
    PLUGIN_DELETED = "plugin_deleted"
    PLUGIN_ACCESSED = "plugin_accessed"
    
    # GDPR actions
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    RETENTION_CLEANUP = "retention_cleanup"
    
    # Auth actions
    AUTH_FAILED = "auth_failed"
    AUTH_SUCCESS = "auth_success"
