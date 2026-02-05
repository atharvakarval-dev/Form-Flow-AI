"""
GDPR Compliance Service Module

Implements GDPR rights:
- Right to access (data export)
- Right to erasure (data deletion)
- Data retention (auto-cleanup)

Optimized queries:
- Single export query with JOINs
- Batch deletion for efficiency
- Scheduled retention cleanup
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.plugin_models import Plugin, PluginTable, PluginField, PluginAPIKey
from core.audit_models import AuditLog
from services.plugin.security.audit import AuditService
from utils.logging import get_logger

logger = get_logger(__name__)


class GDPRService:
    """
    GDPR compliance operations.
    
    Implements:
    - Article 15: Right of access (export_user_data)
    - Article 17: Right to erasure (delete_user_data)
    - Article 5: Storage limitation (cleanup_expired_data)
    
    All operations are logged to audit trail.
    
    Usage:
        gdpr = GDPRService(db)
        data = await gdpr.export_user_data(user_id)
        await gdpr.delete_user_data(user_id)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
    
    async def export_user_data(
        self,
        user_id: int,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export all user data (Article 15 - Right of access).
        
        Returns:
            Dictionary with all user-related data, structured by category.
        
        Single query pattern with eager loading for plugins.
        """
        logger.info(f"Exporting data for user {user_id}")
        
        # Fetch all plugins with nested data (single query)
        plugins_result = await self.db.execute(
            select(Plugin)
            .options(
                selectinload(Plugin.tables).selectinload(PluginTable.fields),
                selectinload(Plugin.api_keys)
            )
            .where(Plugin.user_id == user_id)
        )
        plugins = list(plugins_result.scalars().all())
        
        # Fetch audit logs (separate query - different table)
        audit_result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(1000)  # Cap for performance
        )
        audit_logs = list(audit_result.scalars().all())
        
        # Structure export data
        export = {
            "export_date": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "plugins": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "database_type": p.database_type,
                    "is_active": p.is_active,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "tables": [
                        {
                            "name": t.table_name,
                            "fields": [
                                {
                                    "column": f.column_name,
                                    "type": f.column_type,
                                    "question": f.question_text,
                                    "is_pii": f.is_pii,
                                }
                                for f in t.fields
                            ]
                        }
                        for t in p.tables
                    ],
                    "api_keys": [
                        {
                            "prefix": k.key_prefix,
                            "name": k.name,
                            "is_active": k.is_active,
                            "created_at": k.created_at.isoformat() if k.created_at else None,
                            "last_used": k.last_used_at.isoformat() if k.last_used_at else None,
                        }
                        for k in p.api_keys
                    ]
                }
                for p in plugins
            ],
            "audit_logs": [
                {
                    "action": log.action,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                    "details": log.details,
                    "success": log.success,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in audit_logs
            ],
            "statistics": {
                "total_plugins": len(plugins),
                "active_plugins": sum(1 for p in plugins if p.is_active),
                "total_fields": sum(p.field_count for p in plugins),
                "total_api_keys": sum(len(p.api_keys) for p in plugins),
                "audit_log_entries": len(audit_logs),
            }
        }
        
        # Log the export (for compliance audit trail)
        await self.audit.log_data_exported(
            user_id=user_id,
            tables_exported=["plugins", "plugin_tables", "plugin_fields", "plugin_api_keys", "audit_logs"],
            record_count=export["statistics"]["total_plugins"],
            ip_address=ip_address
        )
        
        logger.info(f"Exported {export['statistics']['total_plugins']} plugins for user {user_id}")
        return export
    
    async def delete_user_data(
        self,
        user_id: int,
        ip_address: Optional[str] = None,
        keep_audit_logs: bool = True
    ) -> Dict[str, int]:
        """
        Delete all user data (Article 17 - Right to erasure).
        
        Args:
            user_id: User to delete data for
            ip_address: For audit logging
            keep_audit_logs: If True, audit logs are retained for compliance
        
        Returns:
            Dictionary with counts of deleted records by type.
        
        Uses CASCADE delete from Plugin -> Tables -> Fields/API Keys.
        """
        logger.info(f"Deleting data for user {user_id}")
        
        # Count before deletion for reporting
        count_result = await self.db.execute(
            select(
                func.count(Plugin.id).label("plugins"),
            )
            .where(Plugin.user_id == user_id)
        )
        counts_before = count_result.one()
        
        # Delete all plugins (CASCADE handles children)
        await self.db.execute(
            delete(Plugin).where(Plugin.user_id == user_id)
        )
        
        # Optionally delete audit logs
        audit_deleted = 0
        if not keep_audit_logs:
            result = await self.db.execute(
                delete(AuditLog).where(AuditLog.user_id == user_id)
            )
            audit_deleted = result.rowcount
        
        await self.db.commit()
        
        deletion_stats = {
            "plugins_deleted": counts_before.plugins,
            "audit_logs_deleted": audit_deleted,
        }
        
        # Log the deletion (even if audit logs are deleted, this one is created)
        await self.audit.log_data_deleted(
            user_id=user_id,
            tables_deleted=["plugins", "plugin_tables", "plugin_fields", "plugin_api_keys"],
            record_count=counts_before.plugins,
            ip_address=ip_address
        )
        
        logger.info(f"Deleted {counts_before.plugins} plugins for user {user_id}")
        return deletion_stats
    
    async def cleanup_expired_voice_recordings(self) -> Dict[str, int]:
        """
        Delete voice recordings past retention period.
        
        Runs as scheduled job. Each plugin has its own retention setting.
        
        Note: This is a placeholder for when voice recording storage is added.
        Currently returns empty stats.
        """
        # TODO: Implement when voice recording storage is added
        # This will query plugins by voice_retention_days and delete old recordings
        logger.info("Voice recording cleanup: no recordings table yet")
        return {"recordings_deleted": 0}
    
    async def cleanup_expired_sessions(self, default_retention_days: int = 7) -> int:
        """
        Delete expired plugin sessions.
        
        Note: This is a placeholder for when session storage is added.
        """
        # TODO: Implement when session storage is added
        logger.info("Session cleanup: no sessions table yet")
        return 0
    
    async def get_retention_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get retention status for user's data.
        
        Returns summary of what data exists and retention periods.
        """
        plugins_result = await self.db.execute(
            select(
                func.count(Plugin.id).label("count"),
                func.min(Plugin.voice_retention_days).label("min_retention"),
                func.max(Plugin.voice_retention_days).label("max_retention"),
            )
            .where(Plugin.user_id == user_id)
        )
        plugins_stats = plugins_result.one()
        
        return {
            "plugin_count": plugins_stats.count,
            "voice_retention_days": {
                "min": plugins_stats.min_retention,
                "max": plugins_stats.max_retention,
            },
            "audit_log_retention_days": 90,  # Fixed retention
        }
