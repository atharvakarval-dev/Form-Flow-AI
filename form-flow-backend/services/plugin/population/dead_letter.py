"""
Dead Letter Queue Module

Stores failed database inserts for retry and analysis.
Features:
- SQLite-backed persistent storage
- Automatic retry with backoff
- Manual reprocessing support
- Cleanup of old entries

Lightweight implementation using SQLAlchemy model.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base, get_db
from utils.logging import get_logger

logger = get_logger(__name__)


class DLQStatus(str, Enum):
    """Dead letter queue entry status."""
    PENDING = "pending"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"     # Permanently failed (max retries)
    SKIPPED = "skipped"   # Manually skipped


class DeadLetterEntry(Base):
    """SQLAlchemy model for dead letter queue entries."""
    
    __tablename__ = "dead_letter_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    table_name = Column(String(255), nullable=False)
    data = Column(JSON, nullable=False)
    error = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=DLQStatus.PENDING.value)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index('ix_dlq_status_retry', 'status', 'next_retry_at'),
        Index('ix_dlq_plugin_status', 'plugin_id', 'status'),
    )


@dataclass
class DLQEntry:
    """Data transfer object for DLQ entries."""
    id: int
    plugin_id: int
    session_id: str
    table_name: str
    data: Dict[str, Any]
    error: Optional[str]
    status: DLQStatus
    retry_count: int
    max_retries: int
    created_at: datetime
    next_retry_at: Optional[datetime]
    
    @classmethod
    def from_model(cls, model: DeadLetterEntry) -> "DLQEntry":
        return cls(
            id=model.id,
            plugin_id=model.plugin_id,
            session_id=model.session_id,
            table_name=model.table_name,
            data=model.data,
            error=model.error,
            status=DLQStatus(model.status),
            retry_count=model.retry_count,
            max_retries=model.max_retries,
            created_at=model.created_at,
            next_retry_at=model.next_retry_at,
        )


class DeadLetterQueue:
    """
    Dead letter queue for failed database inserts.
    
    Stores failed inserts for later retry or manual intervention.
    Uses exponential backoff for retries.
    
    Usage:
        dlq = DeadLetterQueue(db)
        await dlq.enqueue(plugin_id=1, session_id="abc", table_name="users", data={...})
        entries = await dlq.get_pending_entries(plugin_id=1)
        await dlq.retry_entry(entry_id=1, population_service)
    """
    
    # Backoff multiplier (seconds: 5, 25, 125, ...)
    BACKOFF_BASE = 5
    BACKOFF_MULTIPLIER = 5
    
    def __init__(self, db: AsyncSession = None):
        """Initialize with database session."""
        self._db = db
    
    async def _get_db(self) -> AsyncSession:
        """Get database session."""
        if self._db is not None:
            return self._db
        async for db in get_db():
            return db
    
    async def enqueue(
        self,
        plugin_id: int,
        session_id: str,
        table_name: str,
        data: Dict[str, Any],
        error: Optional[str] = None,
        max_retries: int = 3
    ) -> int:
        """
        Add a failed insert to the queue.
        
        Returns:
            ID of the created entry
        """
        db = await self._get_db()
        
        entry = DeadLetterEntry(
            plugin_id=plugin_id,
            session_id=session_id,
            table_name=table_name,
            data=data,
            error=error,
            status=DLQStatus.PENDING.value,
            max_retries=max_retries,
            next_retry_at=datetime.now() + timedelta(seconds=self.BACKOFF_BASE)
        )
        
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        
        logger.info(f"Added DLQ entry {entry.id} for plugin {plugin_id}, table {table_name}")
        return entry.id
    
    async def get_pending_entries(
        self,
        plugin_id: Optional[int] = None,
        limit: int = 100
    ) -> List[DLQEntry]:
        """
        Get entries ready for retry.
        
        Args:
            plugin_id: Optional filter by plugin
            limit: Max entries to return
            
        Returns:
            List of DLQEntry ready for retry
        """
        db = await self._get_db()
        now = datetime.now()
        
        query = (
            select(DeadLetterEntry)
            .where(
                DeadLetterEntry.status.in_([DLQStatus.PENDING.value, DLQStatus.RETRYING.value]),
                DeadLetterEntry.next_retry_at <= now
            )
            .order_by(DeadLetterEntry.next_retry_at)
            .limit(limit)
        )
        
        if plugin_id:
            query = query.where(DeadLetterEntry.plugin_id == plugin_id)
        
        result = await db.execute(query)
        return [DLQEntry.from_model(r) for r in result.scalars()]
    
    async def mark_success(self, entry_id: int) -> None:
        """Mark entry as successfully processed."""
        db = await self._get_db()
        
        result = await db.execute(
            select(DeadLetterEntry).where(DeadLetterEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            entry.status = DLQStatus.SUCCEEDED.value
            entry.updated_at = datetime.now()
            await db.commit()
            logger.info(f"DLQ entry {entry_id} succeeded")
    
    async def mark_failed(
        self,
        entry_id: int,
        error: Optional[str] = None,
        permanent: bool = False
    ) -> None:
        """
        Mark entry as failed.
        
        Args:
            entry_id: Entry ID
            error: New error message
            permanent: If True, mark as permanently failed
        """
        db = await self._get_db()
        
        result = await db.execute(
            select(DeadLetterEntry).where(DeadLetterEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        
        if not entry:
            return
        
        entry.retry_count += 1
        if error:
            entry.error = error
        
        if permanent or entry.retry_count >= entry.max_retries:
            entry.status = DLQStatus.FAILED.value
            logger.warning(f"DLQ entry {entry_id} permanently failed after {entry.retry_count} retries")
        else:
            entry.status = DLQStatus.RETRYING.value
            # Exponential backoff
            backoff = self.BACKOFF_BASE * (self.BACKOFF_MULTIPLIER ** entry.retry_count)
            entry.next_retry_at = datetime.now() + timedelta(seconds=backoff)
            logger.info(f"DLQ entry {entry_id} scheduled for retry in {backoff}s")
        
        entry.updated_at = datetime.now()
        await db.commit()
    
    async def skip_entry(self, entry_id: int) -> None:
        """Manually skip an entry (won't retry)."""
        db = await self._get_db()
        
        result = await db.execute(
            select(DeadLetterEntry).where(DeadLetterEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            entry.status = DLQStatus.SKIPPED.value
            entry.updated_at = datetime.now()
            await db.commit()
    
    async def get_stats(self, plugin_id: Optional[int] = None) -> Dict[str, int]:
        """Get queue statistics."""
        db = await self._get_db()
        
        query = select(
            DeadLetterEntry.status,
            func.count(DeadLetterEntry.id).label("count")
        ).group_by(DeadLetterEntry.status)
        
        if plugin_id:
            query = query.where(DeadLetterEntry.plugin_id == plugin_id)
        
        result = await db.execute(query)
        stats = {status.value: 0 for status in DLQStatus}
        
        for row in result:
            stats[row.status] = row.count
        
        stats["total"] = sum(stats.values())
        return stats
    
    async def cleanup_old_entries(
        self,
        days: int = 30,
        statuses: List[DLQStatus] = None
    ) -> int:
        """
        Delete old entries.
        
        Args:
            days: Delete entries older than this
            statuses: Only delete entries in these statuses
            
        Returns:
            Count of deleted entries
        """
        db = await self._get_db()
        cutoff = datetime.now() - timedelta(days=days)
        
        statuses = statuses or [DLQStatus.SUCCEEDED, DLQStatus.SKIPPED]
        
        query = (
            select(DeadLetterEntry)
            .where(
                DeadLetterEntry.created_at < cutoff,
                DeadLetterEntry.status.in_([s.value for s in statuses])
            )
        )
        
        result = await db.execute(query)
        entries = result.scalars().all()
        
        for entry in entries:
            await db.delete(entry)
        
        await db.commit()
        
        if entries:
            logger.info(f"Cleaned up {len(entries)} old DLQ entries")
        
        return len(entries)


# Singleton instance
_dead_letter_queue: Optional[DeadLetterQueue] = None


def get_dead_letter_queue(db: AsyncSession = None) -> DeadLetterQueue:
    """Get singleton dead letter queue."""
    global _dead_letter_queue
    if _dead_letter_queue is None:
        _dead_letter_queue = DeadLetterQueue(db)
    return _dead_letter_queue
