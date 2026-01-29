"""
Plugin Models Module

SQLAlchemy ORM models for the plugin system.
Optimized for minimal queries with:
- Eager loading via selectin for relationships
- Composite indexes for common query patterns
- JSON columns for flexible configuration

Models:
    - Plugin: Main plugin configuration with DB connection
    - PluginTable: Table structure within a plugin
    - PluginField: Field mapping with questions and validation
    - PluginAPIKey: API keys for external integration
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean, 
    Index, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.database import Base


# =============================================================================
# Plugin Model
# =============================================================================

class Plugin(Base):
    """
    Main plugin configuration.
    
    Stores database connection info, limits, and privacy settings.
    Connection credentials are stored encrypted (see plugin_service.py).
    
    Indexes:
        - user_id: Fast lookup of user's plugins
        - (user_id, is_active): Common filter pattern
    """
    
    __tablename__ = "plugins"
    __table_args__ = (
        Index("ix_plugins_user_active", "user_id", "is_active"),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key - Owner
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Basic Info
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Database Connection (credentials encrypted)
    database_type = Column(String(20), nullable=False)  # postgresql, mysql
    connection_config_encrypted = Column(Text, nullable=False)
    
    # Limits & Controls
    max_concurrent_sessions = Column(Integer, default=10, nullable=False)
    llm_call_limit_per_day = Column(Integer, default=1000, nullable=False)
    db_pool_size = Column(Integer, default=5, nullable=False)
    session_timeout_seconds = Column(Integer, default=300, nullable=False)
    
    # Privacy (GDPR)
    voice_retention_days = Column(Integer, default=30, nullable=False)
    gdpr_compliant = Column(Boolean, default=True, nullable=False)
    
    # Webhooks
    webhook_url = Column(String(2048), nullable=True)
    webhook_secret = Column(String(64), nullable=True)
    
    # Versioning
    schema_version = Column(String(20), default="1.0.0", nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships - Eager load to minimize queries
    tables = relationship(
        "PluginTable",
        back_populates="plugin",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PluginTable.id"
    )
    api_keys = relationship(
        "PluginAPIKey",
        back_populates="plugin",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Plugin(id={self.id}, name='{self.name}', type='{self.database_type}')>"
    
    @property
    def field_count(self) -> int:
        """Total fields across all tables."""
        return sum(len(t.fields) for t in self.tables)
    
    @property
    def active_api_keys_count(self) -> int:
        """Count of active API keys."""
        return sum(1 for k in self.api_keys if k.is_active)


# =============================================================================
# Plugin Table Model
# =============================================================================

class PluginTable(Base):
    """
    Database table structure within a plugin.
    
    Represents one target table in the external database.
    """
    
    __tablename__ = "plugin_tables"
    __table_args__ = (
        UniqueConstraint("plugin_id", "table_name", name="uq_plugin_table"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    plugin_id = Column(
        Integer,
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    table_name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Relationships - Eager load fields
    plugin = relationship("Plugin", back_populates="tables")
    fields = relationship(
        "PluginField",
        back_populates="table",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PluginField.display_order"
    )
    
    def __repr__(self) -> str:
        return f"<PluginTable(id={self.id}, name='{self.table_name}')>"


# =============================================================================
# Plugin Field Model
# =============================================================================

class PluginField(Base):
    """
    Field mapping between questions and database columns.
    
    Each field defines:
    - Which column to populate
    - What question to ask
    - Validation rules to apply
    - Whether it's PII (for GDPR)
    
    Indexes:
        - table_id: Fast field lookup by table
        - question_group: Group similar fields for batching
    """
    
    __tablename__ = "plugin_fields"
    __table_args__ = (
        Index("ix_plugin_fields_table_group", "table_id", "question_group"),
        UniqueConstraint("table_id", "column_name", name="uq_table_column"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    table_id = Column(
        Integer,
        ForeignKey("plugin_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Column mapping
    column_name = Column(String(100), nullable=False)
    column_type = Column(String(50), nullable=False)  # text, integer, email, phone, date
    is_required = Column(Boolean, default=False, nullable=False)
    default_value = Column(String(500), nullable=True)
    
    # Question configuration
    question_text = Column(String(500), nullable=False)
    question_group = Column(String(50), default="other", nullable=False)  # identity, contact, etc.
    display_order = Column(Integer, default=0, nullable=False)
    
    # Validation (stored as JSON for flexibility)
    validation_rules = Column(JSON, nullable=True)
    # Example: {"min_length": 2, "max_length": 100, "pattern": "^[a-zA-Z]+$"}
    
    # Privacy
    is_pii = Column(Boolean, default=False, nullable=False)
    
    # Relationship
    table = relationship("PluginTable", back_populates="fields")
    
    def __repr__(self) -> str:
        return f"<PluginField(id={self.id}, column='{self.column_name}', group='{self.question_group}')>"


# =============================================================================
# Plugin API Key Model
# =============================================================================

class PluginAPIKey(Base):
    """
    API keys for external integration.
    
    Security notes:
    - Only hash is stored (SHA-256)
    - Prefix stored for identification ("ffp_abc1...")
    - Key shown only once at creation
    
    Indexes:
        - key_prefix: Fast prefix lookup
        - plugin_id: Find all keys for a plugin
    """
    
    __tablename__ = "plugin_api_keys"
    __table_args__ = (
        Index("ix_api_keys_prefix", "key_prefix"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    
    plugin_id = Column(
        Integer,
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Key storage (never store plaintext!)
    key_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 = 64 hex chars
    key_prefix = Column(String(12), nullable=False)  # "ffp_" + first 8 chars
    
    # Metadata
    name = Column(String(100), nullable=False)  # "Production", "Testing"
    
    # Limits
    rate_limit = Column(Integer, default=100, nullable=False)  # requests per minute
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    plugin = relationship("Plugin", back_populates="api_keys")
    
    def __repr__(self) -> str:
        return f"<PluginAPIKey(id={self.id}, prefix='{self.key_prefix}', active={self.is_active})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if key is usable."""
        return self.is_active and not self.is_expired
