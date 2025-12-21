"""
Session Manager Service

Redis-backed session storage for conversation persistence.
Handles session creation, retrieval, and cleanup with TTL.

Usage:
    from services.ai.session_manager import SessionManager
    
    manager = SessionManager()
    session_data = await manager.save_session(session)
    session = await manager.get_session(session_id)
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

from utils.logging import get_logger
from utils.cache import get_redis_client

logger = get_logger(__name__)


class SessionManager:
    """
    Redis-backed session manager for conversation persistence.
    
    Provides async session storage with automatic TTL expiry.
    Falls back to in-memory storage if Redis is unavailable.
    """
    
    SESSION_TTL_MINUTES = 30
    SESSION_PREFIX = "formflow:session:"
    
    def __init__(self, redis_client=None):
        """
        Initialize session manager.
        
        Args:
            redis_client: Optional Redis client. Will attempt to get one if not provided.
        """
        self._redis = redis_client
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._use_redis = True
        
    async def _get_redis(self):
        """Get Redis client, falling back to local cache if unavailable."""
        if self._redis is None:
            try:
                self._redis = await get_redis_client()
            except Exception as e:
                logger.warning(f"Redis unavailable, using local cache: {e}")
                self._use_redis = False
        return self._redis
    
    async def save_session(self, session_data: Dict[str, Any]) -> bool:
        """
        Save session data.
        
        Args:
            session_data: Session data dictionary with 'id' key
            
        Returns:
            bool: True if saved successfully
        """
        session_id = session_data.get('id')
        if not session_id:
            logger.error("Cannot save session without ID")
            return False
        
        # Serialize datetime objects
        serialized = self._serialize_session(session_data)
        
        if self._use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    key = f"{self.SESSION_PREFIX}{session_id}"
                    await redis.setex(
                        key,
                        timedelta(minutes=self.SESSION_TTL_MINUTES),
                        json.dumps(serialized)
                    )
                    logger.debug(f"Saved session {session_id} to Redis")
                    return True
            except Exception as e:
                logger.warning(f"Redis save failed, using local cache: {e}")
                self._use_redis = False
        
        # Fallback to local cache
        self._local_cache[session_id] = {
            'data': serialized,
            'expires_at': datetime.now() + timedelta(minutes=self.SESSION_TTL_MINUTES)
        }
        logger.debug(f"Saved session {session_id} to local cache")
        return True
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session data dictionary or None if not found/expired
        """
        if self._use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    key = f"{self.SESSION_PREFIX}{session_id}"
                    data = await redis.get(key)
                    if data:
                        session = json.loads(data)
                        return self._deserialize_session(session)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                self._use_redis = False
        
        # Check local cache
        cached = self._local_cache.get(session_id)
        if cached:
            if cached['expires_at'] > datetime.now():
                return self._deserialize_session(cached['data'])
            else:
                del self._local_cache[session_id]
        
        return None
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if self._use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    key = f"{self.SESSION_PREFIX}{session_id}"
                    await redis.delete(key)
                    logger.debug(f"Deleted session {session_id} from Redis")
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        
        # Also remove from local cache
        if session_id in self._local_cache:
            del self._local_cache[session_id]
        
        return True
    
    async def extend_session(self, session_id: str) -> bool:
        """Extend session TTL by the standard amount."""
        if self._use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    key = f"{self.SESSION_PREFIX}{session_id}"
                    await redis.expire(key, timedelta(minutes=self.SESSION_TTL_MINUTES))
                    return True
            except Exception as e:
                logger.warning(f"Redis expire failed: {e}")
        
        # Extend local cache
        if session_id in self._local_cache:
            self._local_cache[session_id]['expires_at'] = (
                datetime.now() + timedelta(minutes=self.SESSION_TTL_MINUTES)
            )
            return True
        
        return False
    
    async def cleanup_local_cache(self) -> int:
        """Remove expired sessions from local cache. Returns count removed."""
        now = datetime.now()
        expired = [
            sid for sid, data in self._local_cache.items()
            if data['expires_at'] <= now
        ]
        
        for sid in expired:
            del self._local_cache[sid]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired local sessions")
        
        return len(expired)
    
    def _serialize_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize session data for storage."""
        serialized = {}
        for key, value in session.items():
            if isinstance(value, datetime):
                serialized[key] = {'__datetime__': value.isoformat()}
            elif hasattr(value, '__dict__'):
                # Handle dataclass objects
                serialized[key] = self._serialize_session(value.__dict__)
            else:
                serialized[key] = value
        return serialized
    
    def _deserialize_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize session data from storage."""
        deserialized = {}
        for key, value in data.items():
            if isinstance(value, dict):
                if '__datetime__' in value:
                    deserialized[key] = datetime.fromisoformat(value['__datetime__'])
                else:
                    deserialized[key] = self._deserialize_session(value)
            else:
                deserialized[key] = value
        return deserialized


# Singleton instance
_session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """Get or create the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
