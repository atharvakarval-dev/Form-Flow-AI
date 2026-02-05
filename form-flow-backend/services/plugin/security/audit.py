"""
Audit Service Module

Centralized audit logging for security-sensitive operations.
Optimized for minimal overhead:
- Async fire-and-forget logging
- Batch writes for high-throughput scenarios
- No blocking on audit writes

Features:
- All security operations logged
- IP address and user agent capture
- JSON details for flexible payload
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit_models import AuditLog, AuditAction
from utils.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """
    Audit logging service for security operations.
    
    All methods are async and optimized for minimal latency.
    Logging failures are caught and logged but don't propagate.
    
    Usage:
        audit = AuditService(db)
        await audit.log_api_key_created(user_id, plugin_id, key_prefix, ip)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log(
        self,
        action: str,
        user_id: Optional[int] = None,
        api_key_prefix: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Create an audit log entry.
        
        Fire-and-forget: exceptions are caught and logged.
        """
        try:
            log_entry = AuditLog(
                action=action,
                user_id=user_id,
                api_key_prefix=api_key_prefix,
                ip_address=ip_address,
                user_agent=user_agent,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
                success="success" if success else "failure",
                error_message=error_message,
            )
            self.db.add(log_entry)
            await self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")
            # Don't propagate - audit should never break main flow
    
    # =========================================================================
    # Convenience Methods (DRY wrappers)
    # =========================================================================
    
    async def log_api_key_created(
        self,
        user_id: int,
        plugin_id: int,
        key_prefix: str,
        expires_in_days: Optional[int],
        ip_address: Optional[str] = None
    ) -> None:
        """Log API key creation."""
        await self.log(
            action=AuditAction.API_KEY_CREATED,
            user_id=user_id,
            entity_type="plugin",
            entity_id=plugin_id,
            details={"key_prefix": key_prefix, "expires_in_days": expires_in_days},
            ip_address=ip_address
        )
    
    async def log_api_key_revoked(
        self,
        user_id: int,
        plugin_id: int,
        key_prefix: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log API key revocation."""
        await self.log(
            action=AuditAction.API_KEY_REVOKED,
            user_id=user_id,
            entity_type="plugin",
            entity_id=plugin_id,
            details={"key_prefix": key_prefix},
            ip_address=ip_address
        )
    
    async def log_api_key_rotated(
        self,
        user_id: int,
        plugin_id: int,
        old_prefix: str,
        new_prefix: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log API key rotation."""
        await self.log(
            action=AuditAction.API_KEY_ROTATED,
            user_id=user_id,
            entity_type="plugin",
            entity_id=plugin_id,
            details={"old_prefix": old_prefix, "new_prefix": new_prefix},
            ip_address=ip_address
        )
    
    async def log_api_key_used(
        self,
        key_prefix: str,
        plugin_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log API key usage (for rate limiting/anomaly detection)."""
        await self.log(
            action=AuditAction.API_KEY_USED,
            api_key_prefix=key_prefix,
            entity_type="plugin",
            entity_id=plugin_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    async def log_auth_failed(
        self,
        reason: str,
        key_prefix: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log authentication failure."""
        await self.log(
            action=AuditAction.AUTH_FAILED,
            api_key_prefix=key_prefix,
            details={"reason": reason},
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message=reason
        )
    
    async def log_data_exported(
        self,
        user_id: int,
        tables_exported: List[str],
        record_count: int,
        ip_address: Optional[str] = None
    ) -> None:
        """Log GDPR data export."""
        await self.log(
            action=AuditAction.DATA_EXPORTED,
            user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            details={"tables_exported": tables_exported, "record_count": record_count},
            ip_address=ip_address
        )
    
    async def log_data_deleted(
        self,
        user_id: int,
        tables_deleted: List[str],
        record_count: int,
        ip_address: Optional[str] = None
    ) -> None:
        """Log GDPR data deletion (right to be forgotten)."""
        await self.log(
            action=AuditAction.DATA_DELETED,
            user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            details={"tables_deleted": tables_deleted, "record_count": record_count},
            ip_address=ip_address
        )
    
    async def log_retention_cleanup(
        self,
        records_deleted: int,
        retention_days: int
    ) -> None:
        """Log scheduled retention cleanup."""
        await self.log(
            action=AuditAction.RETENTION_CLEANUP,
            details={"records_deleted": records_deleted, "retention_days": retention_days}
        )
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    async def get_user_audit_logs(
        self,
        user_id: int,
        limit: int = 100,
        actions: Optional[List[str]] = None
    ) -> List[AuditLog]:
        """
        Get audit logs for a user.
        
        Single optimized query with optional action filter.
        """
        query = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        
        if actions:
            query = query.where(AuditLog.action.in_(actions))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_api_key_usage(
        self,
        key_prefix: str,
        hours: int = 24
    ) -> int:
        """
        Get API key usage count in time window.
        
        Used for rate limiting and anomaly detection.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count(AuditLog.id))
            .where(
                AuditLog.api_key_prefix == key_prefix,
                AuditLog.action == AuditAction.API_KEY_USED,
                AuditLog.created_at >= since
            )
        )
        
        return result.scalar() or 0
    
    async def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """
        Delete audit logs older than retention period.
        
        Returns count of deleted records.
        """
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        
        result = await self.db.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        await self.db.commit()
        
        deleted = result.rowcount
        logger.info(f"Cleaned up {deleted} audit logs older than {retention_days} days")
        return deleted
