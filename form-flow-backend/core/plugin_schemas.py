"""
Plugin Schemas Module

Pydantic models for API request/response validation.
Zero redundancy through:
- Inheritance for shared fields
- Mixin classes for common patterns
- Computed fields for derived data

Schemas follow the pattern:
- Base: Core fields (shared)
- Create: For POST requests
- Update: For PATCH requests (all optional)
- Response: For API responses (includes id, timestamps)
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# =============================================================================
# Validation Rules Schema (Reusable)
# =============================================================================

class ValidationRules(BaseModel):
    """Field validation configuration."""
    required: bool = False
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=1)
    pattern: Optional[str] = None  # Regex pattern
    allowed_values: Optional[List[str]] = None
    
    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Plugin Field Schemas
# =============================================================================

class PluginFieldBase(BaseModel):
    """Base field schema with shared fields."""
    column_name: str = Field(..., min_length=1, max_length=100)
    column_type: Literal["text", "integer", "email", "phone", "date", "boolean", "decimal"] = "text"
    is_required: bool = False
    default_value: Optional[str] = Field(None, max_length=500)
    question_text: str = Field(..., min_length=1, max_length=500)
    question_group: str = Field("other", max_length=50)
    display_order: int = Field(0, ge=0)
    validation_rules: Optional[ValidationRules] = None
    is_pii: bool = False


class PluginFieldCreate(PluginFieldBase):
    """Schema for creating a field."""
    pass


class PluginFieldUpdate(BaseModel):
    """Schema for updating a field (all optional)."""
    column_name: Optional[str] = Field(None, min_length=1, max_length=100)
    column_type: Optional[Literal["text", "integer", "email", "phone", "date", "boolean", "decimal"]] = None
    is_required: Optional[bool] = None
    default_value: Optional[str] = None
    question_text: Optional[str] = Field(None, min_length=1, max_length=500)
    question_group: Optional[str] = None
    display_order: Optional[int] = None
    validation_rules: Optional[ValidationRules] = None
    is_pii: Optional[bool] = None
    
    model_config = ConfigDict(extra="forbid")


class PluginFieldResponse(PluginFieldBase):
    """Schema for field in API responses."""
    id: int
    table_id: int
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Plugin Table Schemas
# =============================================================================

class PluginTableBase(BaseModel):
    """Base table schema."""
    table_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class PluginTableCreate(PluginTableBase):
    """Schema for creating a table with fields."""
    fields: List[PluginFieldCreate] = Field(..., min_length=1)


class PluginTableUpdate(BaseModel):
    """Schema for updating a table."""
    table_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    
    model_config = ConfigDict(extra="forbid")


class PluginTableResponse(PluginTableBase):
    """Schema for table in API responses."""
    id: int
    plugin_id: int
    fields: List[PluginFieldResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Database Connection Schemas
# =============================================================================

class DatabaseConnectionConfig(BaseModel):
    """Database connection configuration (sensitive!)."""
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    database: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    ssl_mode: Optional[Literal["disable", "require", "verify-ca", "verify-full"]] = "require"
    
    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Plugin Schemas
# =============================================================================

class PluginBase(BaseModel):
    """Base plugin schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    database_type: Literal["postgresql", "mysql"] = "postgresql"
    
    # Limits
    max_concurrent_sessions: int = Field(10, ge=1, le=100)
    llm_call_limit_per_day: int = Field(1000, ge=10, le=100000)
    db_pool_size: int = Field(5, ge=1, le=20)
    session_timeout_seconds: int = Field(300, ge=60, le=3600)
    
    # Privacy
    voice_retention_days: int = Field(30, ge=1, le=365)
    gdpr_compliant: bool = True
    
    # Webhooks
    webhook_url: Optional[str] = Field(None, max_length=2048)
    webhook_secret: Optional[str] = Field(None, max_length=64)


class PluginCreate(PluginBase):
    """Schema for creating a plugin."""
    connection_config: DatabaseConnectionConfig
    tables: List[PluginTableCreate] = Field(..., min_length=1)
    
    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v


class PluginUpdate(BaseModel):
    """Schema for updating a plugin (all optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    max_concurrent_sessions: Optional[int] = Field(None, ge=1, le=100)
    llm_call_limit_per_day: Optional[int] = None
    session_timeout_seconds: Optional[int] = None
    voice_retention_days: Optional[int] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    is_active: Optional[bool] = None
    
    model_config = ConfigDict(extra="forbid")


class PluginResponse(PluginBase):
    """Schema for plugin in API responses."""
    id: int
    user_id: int
    is_active: bool
    schema_version: str
    created_at: datetime
    updated_at: datetime
    tables: List[PluginTableResponse] = []
    field_count: int = 0
    active_api_keys_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class PluginSummary(BaseModel):
    """Lightweight plugin summary for list endpoints."""
    id: int
    name: str
    database_type: str
    is_active: bool
    field_count: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# API Key Schemas
# =============================================================================

class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    rate_limit: int = Field(100, ge=1, le=10000)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """Schema for API key in responses (no full key!)."""
    id: int
    plugin_id: int
    key_prefix: str
    name: str
    rate_limit: int
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class APIKeyCreated(APIKeyResponse):
    """Schema returned when API key is created (includes full key ONCE)."""
    api_key: str = Field(..., description="Full API key - shown only once!")


# =============================================================================
# Session & Webhook Schemas
# =============================================================================

class PluginSessionStart(BaseModel):
    """Request to start a voice collection session."""
    source_url: Optional[str] = Field(None, description="URL where widget is embedded")


class PluginSessionResponse(BaseModel):
    """Response when session is started."""
    session_id: str
    plugin_id: int
    questions: List[Dict[str, Any]]
    total_fields: int
    current_question: Optional[str] = None


class PluginSessionInput(BaseModel):
    """Request to submit user input to a session."""
    input: str = Field(..., min_length=1, description="User's voice transcription or text input")
    request_id: Optional[str] = Field(None, description="Client-generated request ID for deduplication")


class PluginSessionInputResponse(BaseModel):
    """Response after processing user input."""
    session_id: str
    extracted_values: Dict[str, Any] = {}
    next_question: Optional[str] = None
    progress: float = 0  # 0-100
    is_complete: bool = False
    remaining_fields: int = 0


class PluginSessionCompleteResponse(BaseModel):
    """Response when session is completed."""
    session_id: str
    plugin_id: int
    success: bool
    records_created: int = 0
    message: str = ""


class PluginSessionStatus(BaseModel):
    """Current status of a session."""
    session_id: str
    plugin_id: int
    status: Literal["active", "completed", "expired", "failed"]
    progress: float = 0
    extracted_fields: Dict[str, Any] = {}
    remaining_fields: int = 0
    created_at: datetime
    last_activity: datetime


class WebhookPayload(BaseModel):
    """Payload sent to customer's webhook."""
    event: Literal["session_started", "data_collected", "session_completed", "session_failed"]
    plugin_id: int
    session_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime


# =============================================================================
# Error Responses
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
