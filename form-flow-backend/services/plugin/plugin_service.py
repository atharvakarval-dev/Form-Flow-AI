"""
Plugin Service Module

Core business logic for plugin CRUD operations.
Optimized for minimal database queries:
- Single query with eager loading for full plugin retrieval
- Bulk operations for batch creates/updates
- Reuses SQLAlchemy session for transaction coherence

Security:
- Encrypts database credentials before storage
- Verifies user ownership on all operations
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.plugin_models import Plugin, PluginTable, PluginField, PluginAPIKey
from core.plugin_schemas import (
    PluginCreate, PluginUpdate, PluginTableCreate, PluginFieldCreate,
    APIKeyCreate, DatabaseConnectionConfig
)
from services.plugin.exceptions import (
    PluginNotFoundError, APIKeyInvalidError
)
from services.plugin.security.encryption import get_encryption_service
from config.settings import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class PluginService:
    """
    Service for plugin CRUD operations.
    
    All methods are optimized for minimal queries:
    - Use selectinload for eager loading of relationships
    - Single query patterns where possible
    - Bulk inserts for nested creates
    
    Usage:
        service = PluginService(db)
        plugin = await service.create_plugin(user_id, data)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._encryption = get_encryption_service()
    
    def _encrypt_credentials(self, config: DatabaseConnectionConfig) -> str:
        """Encrypt database credentials."""
        return self._encryption.encrypt(config.model_dump())
    
    def _decrypt_credentials(self, encrypted: str) -> dict:
        """Decrypt database credentials."""
        return self._encryption.decrypt(encrypted)
    
    # =========================================================================
    # Plugin CRUD
    # =========================================================================
    
    async def create_plugin(
        self,
        user_id: int,
        data: PluginCreate
    ) -> Plugin:
        """
        Create a new plugin with tables and fields.
        
        Single transaction, bulk inserts for efficiency.
        """
        logger.info(f"Creating plugin '{data.name}' for user {user_id}")
        
        # Create plugin
        plugin = Plugin(
            user_id=user_id,
            name=data.name,
            description=data.description,
            database_type=data.database_type,
            connection_config_encrypted=self._encrypt_credentials(data.connection_config),
            max_concurrent_sessions=data.max_concurrent_sessions,
            llm_call_limit_per_day=data.llm_call_limit_per_day,
            db_pool_size=data.db_pool_size,
            session_timeout_seconds=data.session_timeout_seconds,
            voice_retention_days=data.voice_retention_days,
            gdpr_compliant=data.gdpr_compliant,
            webhook_url=data.webhook_url,
            webhook_secret=data.webhook_secret,
        )
        self.db.add(plugin)
        await self.db.flush()  # Get plugin.id before creating children
        
        # Create tables and fields in bulk
        for table_data in data.tables:
            table = PluginTable(
                plugin_id=plugin.id,
                table_name=table_data.table_name,
                description=table_data.description,
            )
            self.db.add(table)
            await self.db.flush()
            
            for i, field_data in enumerate(table_data.fields):
                field = PluginField(
                    table_id=table.id,
                    column_name=field_data.column_name,
                    column_type=field_data.column_type,
                    is_required=field_data.is_required,
                    default_value=field_data.default_value,
                    question_text=field_data.question_text,
                    question_group=field_data.question_group,
                    display_order=field_data.display_order or i,
                    validation_rules=field_data.validation_rules.model_dump() if field_data.validation_rules else None,
                    is_pii=field_data.is_pii,
                )
                self.db.add(field)
        
        await self.db.commit()
        await self.db.refresh(plugin)
        
        logger.info(f"Created plugin {plugin.id} with {plugin.field_count} fields")
        return plugin
    
    async def get_plugin(
        self,
        plugin_id: int,
        user_id: int,
        include_inactive: bool = False
    ) -> Plugin:
        """
        Get plugin by ID with ownership check.
        
        Single query with eager loading of tables, fields, and API keys.
        """
        query = (
            select(Plugin)
            .options(
                selectinload(Plugin.tables).selectinload(PluginTable.fields),
                selectinload(Plugin.api_keys)
            )
            .where(Plugin.id == plugin_id, Plugin.user_id == user_id)
        )
        
        if not include_inactive:
            query = query.where(Plugin.is_active == True)
        
        result = await self.db.execute(query)
        plugin = result.scalar_one_or_none()
        
        if not plugin:
            raise PluginNotFoundError(plugin_id, user_id)
        
        return plugin
    
    async def get_user_plugins(
        self,
        user_id: int,
        include_inactive: bool = False
    ) -> List[Plugin]:
        """
        Get all plugins for a user.
        
        Lightweight query - relationships loaded only when accessed.
        """
        query = (
            select(Plugin)
            .options(selectinload(Plugin.tables).selectinload(PluginTable.fields))
            .where(Plugin.user_id == user_id)
            .order_by(Plugin.created_at.desc())
        )
        
        if not include_inactive:
            query = query.where(Plugin.is_active == True)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_plugin(
        self,
        plugin_id: int,
        user_id: int,
        data: PluginUpdate
    ) -> Plugin:
        """Update plugin (non-null fields only)."""
        plugin = await self.get_plugin(plugin_id, user_id, include_inactive=True)
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(plugin, key, value)
        
        await self.db.commit()
        await self.db.refresh(plugin)
        
        logger.info(f"Updated plugin {plugin_id}")
        return plugin
    
    async def delete_plugin(self, plugin_id: int, user_id: int) -> bool:
        """Soft delete plugin (set is_active=False)."""
        plugin = await self.get_plugin(plugin_id, user_id, include_inactive=True)
        plugin.is_active = False
        await self.db.commit()
        
        logger.info(f"Soft deleted plugin {plugin_id}")
        return True
    
    # =========================================================================
    # API Key Management
    # =========================================================================
    
    async def create_api_key(
        self,
        plugin_id: int,
        user_id: int,
        data: APIKeyCreate
    ) -> Tuple[PluginAPIKey, str]:
        """
        Create a new API key for a plugin.
        
        Returns (key_record, plain_key). Plain key shown only once!
        """
        # Verify ownership
        await self.get_plugin(plugin_id, user_id)
        
        # Generate key: ffp_ prefix + 48 random chars
        raw_key = secrets.token_urlsafe(36)
        plain_key = f"ffp_{raw_key}"
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        key_prefix = plain_key[:12]
        
        # Calculate expiry
        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)
        
        api_key = PluginAPIKey(
            plugin_id=plugin_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=data.name,
            rate_limit=data.rate_limit,
            expires_at=expires_at,
        )
        
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.info(f"Created API key {key_prefix} for plugin {plugin_id}")
        return api_key, plain_key
    
    async def validate_api_key(self, api_key: str) -> Tuple[PluginAPIKey, Plugin]:
        """
        Validate an API key and return key + plugin.
        
        Single optimized query joining key -> plugin.
        Updates last_used_at timestamp.
        """
        if not api_key or not api_key.startswith("ffp_"):
            raise APIKeyInvalidError("Invalid API key format")
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        query = (
            select(PluginAPIKey)
            .options(
                selectinload(PluginAPIKey.plugin)
                .selectinload(Plugin.tables)
                .selectinload(PluginTable.fields)
            )
            .where(PluginAPIKey.key_hash == key_hash)
        )
        
        result = await self.db.execute(query)
        key_record = result.scalar_one_or_none()
        
        if not key_record:
            raise APIKeyInvalidError("API key not found")
        
        if not key_record.is_valid:
            if not key_record.is_active:
                raise APIKeyInvalidError("API key has been revoked")
            if key_record.is_expired:
                raise APIKeyInvalidError("API key has expired")
        
        if not key_record.plugin.is_active:
            raise APIKeyInvalidError("Plugin is inactive")
        
        # Update last used (fire and forget)
        key_record.last_used_at = datetime.utcnow()
        await self.db.commit()
        
        return key_record, key_record.plugin
    
    async def list_api_keys(
        self,
        plugin_id: int,
        user_id: int
    ) -> List[PluginAPIKey]:
        """Get all API keys for a plugin."""
        await self.get_plugin(plugin_id, user_id)
        
        query = (
            select(PluginAPIKey)
            .where(PluginAPIKey.plugin_id == plugin_id)
            .order_by(PluginAPIKey.created_at.desc())
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def revoke_api_key(
        self,
        plugin_id: int,
        key_id: int,
        user_id: int
    ) -> bool:
        """Revoke an API key."""
        await self.get_plugin(plugin_id, user_id)
        
        query = (
            select(PluginAPIKey)
            .where(PluginAPIKey.id == key_id, PluginAPIKey.plugin_id == plugin_id)
        )
        
        result = await self.db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise APIKeyInvalidError("API key not found")
        
        api_key.is_active = False
        await self.db.commit()
        
        logger.info(f"Revoked API key {api_key.key_prefix}")
        return True
    
    async def rotate_api_key(
        self,
        plugin_id: int,
        key_id: int,
        user_id: int
    ) -> Tuple[PluginAPIKey, str]:
        """
        Rotate an API key (revoke old, create new with same config).
        
        Returns (new_key_record, new_plain_key).
        Old key is immediately invalidated.
        """
        # Verify ownership
        await self.get_plugin(plugin_id, user_id)
        
        # Get old key
        query = (
            select(PluginAPIKey)
            .where(PluginAPIKey.id == key_id, PluginAPIKey.plugin_id == plugin_id)
        )
        result = await self.db.execute(query)
        old_key = result.scalar_one_or_none()
        
        if not old_key:
            raise APIKeyInvalidError("API key not found")
        
        # Revoke old key
        old_prefix = old_key.key_prefix
        old_key.is_active = False
        
        # Generate new key with same config
        raw_key = secrets.token_urlsafe(36)
        plain_key = f"ffp_{raw_key}"
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        key_prefix = plain_key[:12]
        
        new_key = PluginAPIKey(
            plugin_id=plugin_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=old_key.name,
            rate_limit=old_key.rate_limit,
            expires_at=old_key.expires_at,  # Keep same expiry
        )
        
        self.db.add(new_key)
        await self.db.commit()
        await self.db.refresh(new_key)
        
        logger.info(f"Rotated API key {old_prefix} -> {key_prefix} for plugin {plugin_id}")
        return new_key, plain_key
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    async def get_plugin_stats(self, user_id: int) -> dict:
        """Get aggregate stats for user's plugins."""
        result = await self.db.execute(
            select(
                func.count(Plugin.id).label("total_plugins"),
                func.count(Plugin.id).filter(Plugin.is_active == True).label("active_plugins"),
            )
            .where(Plugin.user_id == user_id)
        )
        
        row = result.one()
        return {
            "total_plugins": row.total_plugins,
            "active_plugins": row.active_plugins,
        }
