"""
Plugin Session Manager Module

Manages plugin data collection sessions with:
- Redis-backed persistence with TTL
- Automatic timeout and cleanup
- Session state machine (active, paused, completed, expired)
- Progress tracking

Extends patterns from services.ai.session_manager for plugin-specific needs.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
import json

from utils.logging import get_logger
from utils.cache import get_redis_client

logger = get_logger(__name__)


class SessionState(str, Enum):
    """Plugin session states."""
    ACTIVE = "active"            # Session in progress
    PAUSED = "paused"            # User paused, can resume
    COMPLETED = "completed"      # All fields collected
    EXPIRED = "expired"          # Timed out
    CANCELLED = "cancelled"      # User cancelled


@dataclass
class PluginSessionData:
    """
    Plugin session data container.
    
    Stores all state for a plugin data collection session.
    """
    session_id: str
    plugin_id: int
    user_id: Optional[int]
    api_key_prefix: Optional[str]  # For API key-authenticated sessions
    
    # Session state
    state: SessionState = SessionState.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # Data collection state
    extracted_values: Dict[str, Any] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    pending_fields: List[str] = field(default_factory=list)
    completed_fields: List[str] = field(default_factory=list)
    skipped_fields: List[str] = field(default_factory=list)
    
    # Current conversation
    current_question: Optional[str] = None
    current_fields: List[str] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    turn_count: int = 0
    
    # Idempotency tracking
    idempotency_key: Optional[str] = None
    processed_requests: List[str] = field(default_factory=list)  # Request IDs already processed
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """Check if session has expired."""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return datetime.now() - self.last_activity > timedelta(minutes=ttl_minutes)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get session progress info."""
        total = len(self.pending_fields) + len(self.completed_fields) + len(self.skipped_fields)
        completed = len(self.completed_fields)
        
        return {
            "total_fields": total,
            "completed": completed,
            "skipped": len(self.skipped_fields),
            "pending": len(self.pending_fields),
            "percentage": round(completed / total * 100, 1) if total > 0 else 0,
            "turn_count": self.turn_count,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "session_id": self.session_id,
            "plugin_id": self.plugin_id,
            "user_id": self.user_id,
            "api_key_prefix": self.api_key_prefix,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "extracted_values": self.extracted_values,
            "confidence_scores": self.confidence_scores,
            "pending_fields": self.pending_fields,
            "completed_fields": self.completed_fields,
            "skipped_fields": self.skipped_fields,
            "current_question": self.current_question,
            "current_fields": self.current_fields,
            "conversation_history": self.conversation_history,
            "turn_count": self.turn_count,
            "idempotency_key": self.idempotency_key,
            "processed_requests": self.processed_requests,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginSessionData":
        """Deserialize from storage."""
        return cls(
            session_id=data["session_id"],
            plugin_id=data["plugin_id"],
            user_id=data.get("user_id"),
            api_key_prefix=data.get("api_key_prefix"),
            state=SessionState(data.get("state", "active")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            last_activity=datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else datetime.now(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            extracted_values=data.get("extracted_values", {}),
            confidence_scores=data.get("confidence_scores", {}),
            pending_fields=data.get("pending_fields", []),
            completed_fields=data.get("completed_fields", []),
            skipped_fields=data.get("skipped_fields", []),
            current_question=data.get("current_question"),
            current_fields=data.get("current_fields", []),
            conversation_history=data.get("conversation_history", []),
            turn_count=data.get("turn_count", 0),
            idempotency_key=data.get("idempotency_key"),
            processed_requests=data.get("processed_requests", []),
        )


class PluginSessionManager:
    """
    Redis-backed session manager for plugin data collection.
    
    Features:
    - Automatic TTL expiry
    - Session state machine
    - Cleanup background task
    - Falls back to in-memory if Redis unavailable
    
    Usage:
        manager = PluginSessionManager()
        session = await manager.create_session(plugin_id=1, fields=["name", "email"])
        session = await manager.get_session(session_id)
        await manager.update_session(session)
    """
    
    SESSION_TTL_MINUTES = 30
    SESSION_PREFIX = "plugin_session:"
    CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes
    MAX_PROCESSED_REQUESTS = 100  # Keep last N for idempotency checking
    
    def __init__(self, redis_client=None):
        """Initialize session manager."""
        self._redis = redis_client
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._use_redis = True
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def _get_redis(self):
        """Get Redis client, falling back to local cache if unavailable."""
        if self._redis is None:
            try:
                self._redis = await get_redis_client()
            except Exception as e:
                logger.warning(f"Redis unavailable, using local cache: {e}")
                self._use_redis = False
        return self._redis
    
    async def create_session(
        self,
        session_id: str,
        plugin_id: int,
        fields: List[str],
        user_id: Optional[int] = None,
        api_key_prefix: Optional[str] = None,
        ttl_minutes: int = None,
        idempotency_key: Optional[str] = None
    ) -> PluginSessionData:
        """
        Create a new plugin session.
        
        Args:
            session_id: Unique session ID
            plugin_id: Plugin ID
            fields: List of field names to collect
            user_id: Optional user ID
            api_key_prefix: Optional API key prefix
            ttl_minutes: Custom TTL (defaults to SESSION_TTL_MINUTES)
            idempotency_key: Optional key for idempotent operations
            
        Returns:
            New PluginSessionData
        """
        ttl = ttl_minutes or self.SESSION_TTL_MINUTES
        
        session = PluginSessionData(
            session_id=session_id,
            plugin_id=plugin_id,
            user_id=user_id,
            api_key_prefix=api_key_prefix,
            pending_fields=fields.copy(),
            expires_at=datetime.now() + timedelta(minutes=ttl),
            idempotency_key=idempotency_key,
        )
        
        await self._save_session(session)
        logger.info(f"Created plugin session {session_id} for plugin {plugin_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[PluginSessionData]:
        """
        Retrieve a session by ID.
        
        Returns None if not found or expired.
        """
        if self._use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    key = f"{self.SESSION_PREFIX}{session_id}"
                    data = await redis.get(key)
                    if data:
                        session = PluginSessionData.from_dict(json.loads(data))
                        
                        # Check expiry
                        if session.is_expired():
                            session.state = SessionState.EXPIRED
                            await self._save_session(session)
                            return None
                        
                        return session
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                self._use_redis = False
        
        # Check local cache
        cached = self._local_cache.get(session_id)
        if cached:
            # Check cache entry expiry (TTL)
            if cached.get("expires_at", datetime.min) <= datetime.now():
                del self._local_cache[session_id]
                return None
                
            session = PluginSessionData.from_dict(cached["data"])
            
            # Check session logic expiry
            if session.is_expired():
                # We don't save state change here for local cache to keep it simple,
                # just return None as if it doesn't exist/expired.
                # Ideally we would update status to EXPIRED and keep it, but for now:
                return None
            
            return session
        
        return None
    
    async def update_session(self, session: PluginSessionData) -> bool:
        """Update session data."""
        session.update_activity()
        return await self._save_session(session)
    
    async def _save_session(self, session: PluginSessionData) -> bool:
        """Save session to storage."""
        data = session.to_dict()
        
        if self._use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    key = f"{self.SESSION_PREFIX}{session.session_id}"
                    ttl = timedelta(minutes=self.SESSION_TTL_MINUTES)
                    await redis.setex(key, ttl, json.dumps(data))
                    return True
            except Exception as e:
                logger.warning(f"Redis save failed: {e}")
                self._use_redis = False
        
        # Fallback to local cache
        self._local_cache[session.session_id] = {
            "data": data,
            "expires_at": datetime.now() + timedelta(minutes=self.SESSION_TTL_MINUTES)
        }
        return True
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if self._use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    key = f"{self.SESSION_PREFIX}{session_id}"
                    await redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        
        if session_id in self._local_cache:
            del self._local_cache[session_id]
        
        return True
    
    async def complete_session(self, session: PluginSessionData) -> Dict[str, Any]:
        """
        Mark session as completed and return final data.
        
        Returns the extracted values for database insertion.
        """
        session.state = SessionState.COMPLETED
        await self.update_session(session)
        
        logger.info(f"Completed plugin session {session.session_id}")
        
        return {
            "session_id": session.session_id,
            "plugin_id": session.plugin_id,
            "extracted_values": session.extracted_values,
            "confidence_scores": session.confidence_scores,
            "completed_fields": session.completed_fields,
            "skipped_fields": session.skipped_fields,
            "turn_count": session.turn_count,
        }
    
    async def extend_session(self, session_id: str, minutes: int = None) -> bool:
        """Extend session TTL."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        minutes = minutes or self.SESSION_TTL_MINUTES
        session.expires_at = datetime.now() + timedelta(minutes=minutes)
        await self._save_session(session)
        return True
    
    async def check_idempotency(
        self,
        session: PluginSessionData,
        request_id: str
    ) -> bool:
        """
        Check if request has already been processed.
        
        Returns True if already processed (should skip), False if new.
        """
        if request_id in session.processed_requests:
            logger.info(f"Skipping duplicate request {request_id} for session {session.session_id}")
            return True
        return False
    
    async def mark_request_processed(
        self,
        session: PluginSessionData,
        request_id: str
    ) -> None:
        """Mark a request as processed for idempotency."""
        session.processed_requests.append(request_id)
        
        # Keep only last N requests
        if len(session.processed_requests) > self.MAX_PROCESSED_REQUESTS:
            session.processed_requests = session.processed_requests[-self.MAX_PROCESSED_REQUESTS:]
        
        await self._save_session(session)
    
    async def cleanup_expired(self) -> int:
        """
        Cleanup expired sessions from local cache.
        
        Redis handles TTL automatically, this is for local fallback.
        Returns count of cleaned sessions.
        """
        now = datetime.now()
        expired = [
            sid for sid, data in self._local_cache.items()
            if data.get("expires_at", datetime.min) <= now
        ]
        
        for sid in expired:
            del self._local_cache[sid]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired plugin sessions")
        
        return len(expired)
    
    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started plugin session cleanup task")
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped plugin session cleanup task")
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Plugin session cleanup error: {e}")


# Singleton instance
_plugin_session_manager: Optional[PluginSessionManager] = None


async def get_plugin_session_manager() -> PluginSessionManager:
    """Get singleton plugin session manager."""
    global _plugin_session_manager
    if _plugin_session_manager is None:
        _plugin_session_manager = PluginSessionManager()
    return _plugin_session_manager
