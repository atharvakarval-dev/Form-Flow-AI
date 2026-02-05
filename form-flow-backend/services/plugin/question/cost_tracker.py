"""
LLM Cost Tracking Service

Tracks LLM usage and costs per plugin for billing and analytics.
Features:
- Async fire-and-forget logging (never blocks main flow)
- Aggregation by plugin, day, operation type
- Batch writes for efficiency
- Budget alerts (optional)

Uses existing AuditLog infrastructure where appropriate.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, date
from collections import defaultdict
import asyncio

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Index, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

from core.database import Base, get_db
from utils.logging import get_logger

logger = get_logger(__name__)


class LLMUsageLog(Base):
    """SQLAlchemy model for LLM usage tracking."""
    
    __tablename__ = "llm_usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(Integer, nullable=False, index=True)
    operation = Column(String(50), nullable=False)  # e.g., "question_consolidation", "extraction"
    model = Column(String(50), nullable=False)
    tokens = Column(Integer, nullable=False, default=0)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    usage_date = Column(Date, nullable=False, index=True)  # For daily aggregation
    
    # Composite indexes for efficient querying
    __table_args__ = (
        Index('ix_llm_usage_plugin_date', 'plugin_id', 'usage_date'),
        Index('ix_llm_usage_plugin_operation', 'plugin_id', 'operation'),
    )


@dataclass
class UsageSummary:
    """Summary of LLM usage for a period."""
    total_tokens: int
    total_cost: float
    operation_breakdown: Dict[str, float]
    daily_breakdown: Dict[str, float]


@dataclass
class BudgetAlert:
    """Budget alert configuration."""
    daily_limit: float = 1.0  # $1 per day default
    monthly_limit: float = 25.0  # $25 per month default
    alert_threshold: float = 0.8  # Alert at 80% usage


class CostTracker:
    """
    LLM cost tracking service.
    
    Tracks usage per plugin with:
    - Fire-and-forget async logging
    - Batched writes for efficiency
    - Aggregation queries for billing
    
    Usage:
        tracker = CostTracker(db)
        await tracker.track_usage(plugin_id=1, operation="consolidation", tokens=100)
        summary = await tracker.get_usage_summary(plugin_id=1)
    """
    
    def __init__(self, db: AsyncSession = None):
        """Initialize tracker with optional db session."""
        self._db = db
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._buffer_size = 10  # Flush after 10 entries
    
    async def _get_db(self) -> AsyncSession:
        """Get database session."""
        if self._db is not None:
            return self._db
        
        # Get from dependency injection
        async for db in get_db():
            return db
    
    async def track_usage(
        self,
        plugin_id: int,
        operation: str,
        tokens: int,
        estimated_cost: float,
        model: str = "gemini-2.5-flash-lite"
    ) -> None:
        """
        Track LLM usage (fire-and-forget).
        
        Buffers writes and flushes periodically for efficiency.
        """
        entry = {
            "plugin_id": plugin_id,
            "operation": operation,
            "model": model,
            "tokens": tokens,
            "estimated_cost": estimated_cost,
            "usage_date": date.today(),
        }
        
        async with self._buffer_lock:
            self._buffer.append(entry)
            
            if len(self._buffer) >= self._buffer_size:
                await self._flush_buffer()
    
    async def _flush_buffer(self) -> None:
        """Flush buffer to database."""
        if not self._buffer:
            return
        
        try:
            db = await self._get_db()
            
            # Batch insert
            logs = [LLMUsageLog(**entry) for entry in self._buffer]
            db.add_all(logs)
            await db.commit()
            
            logger.debug(f"Flushed {len(self._buffer)} LLM usage entries")
            self._buffer.clear()
        except Exception as e:
            logger.warning(f"Failed to flush LLM usage buffer: {e}")
    
    async def flush(self) -> None:
        """Force flush the buffer (call on shutdown)."""
        async with self._buffer_lock:
            await self._flush_buffer()
    
    async def get_plugin_usage(
        self,
        plugin_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> UsageSummary:
        """
        Get usage summary for a plugin.
        
        Args:
            plugin_id: Plugin ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            UsageSummary with breakdowns
        """
        db = await self._get_db()
        
        # Build query
        query = select(
            func.sum(LLMUsageLog.tokens).label("total_tokens"),
            func.sum(LLMUsageLog.estimated_cost).label("total_cost"),
        ).where(LLMUsageLog.plugin_id == plugin_id)
        
        if start_date:
            query = query.where(LLMUsageLog.usage_date >= start_date)
        if end_date:
            query = query.where(LLMUsageLog.usage_date <= end_date)
        
        result = await db.execute(query)
        row = result.one()
        
        total_tokens = row.total_tokens or 0
        total_cost = row.total_cost or 0.0
        
        # Get operation breakdown
        op_query = (
            select(
                LLMUsageLog.operation,
                func.sum(LLMUsageLog.estimated_cost).label("cost")
            )
            .where(LLMUsageLog.plugin_id == plugin_id)
            .group_by(LLMUsageLog.operation)
        )
        
        if start_date:
            op_query = op_query.where(LLMUsageLog.usage_date >= start_date)
        if end_date:
            op_query = op_query.where(LLMUsageLog.usage_date <= end_date)
        
        op_result = await db.execute(op_query)
        operation_breakdown = {row.operation: row.cost for row in op_result}
        
        # Get daily breakdown
        daily_query = (
            select(
                LLMUsageLog.usage_date,
                func.sum(LLMUsageLog.estimated_cost).label("cost")
            )
            .where(LLMUsageLog.plugin_id == plugin_id)
            .group_by(LLMUsageLog.usage_date)
            .order_by(LLMUsageLog.usage_date.desc())
            .limit(30)  # Last 30 days
        )
        
        daily_result = await db.execute(daily_query)
        daily_breakdown = {
            str(row.usage_date): row.cost for row in daily_result
        }
        
        return UsageSummary(
            total_tokens=total_tokens,
            total_cost=total_cost,
            operation_breakdown=operation_breakdown,
            daily_breakdown=daily_breakdown
        )
    
    async def get_user_total_usage(
        self,
        user_id: int,
        plugin_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Get total usage across all user's plugins.
        
        Single query for efficiency.
        """
        if not plugin_ids:
            return {"total_tokens": 0, "total_cost": 0.0, "plugins": {}}
        
        db = await self._get_db()
        
        # Single query with grouping
        query = (
            select(
                LLMUsageLog.plugin_id,
                func.sum(LLMUsageLog.tokens).label("tokens"),
                func.sum(LLMUsageLog.estimated_cost).label("cost")
            )
            .where(LLMUsageLog.plugin_id.in_(plugin_ids))
            .group_by(LLMUsageLog.plugin_id)
        )
        
        result = await db.execute(query)
        
        plugins = {}
        total_tokens = 0
        total_cost = 0.0
        
        for row in result:
            plugins[row.plugin_id] = {
                "tokens": row.tokens or 0,
                "cost": row.cost or 0.0
            }
            total_tokens += row.tokens or 0
            total_cost += row.cost or 0.0
        
        return {
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "plugins": plugins
        }
    
    async def check_budget(
        self,
        plugin_id: int,
        budget: BudgetAlert = None
    ) -> Dict[str, Any]:
        """
        Check if plugin is within budget limits.
        
        Returns budget status and alerts.
        """
        budget = budget or BudgetAlert()
        today = date.today()
        
        # Get today's usage
        db = await self._get_db()
        
        daily_query = (
            select(func.sum(LLMUsageLog.estimated_cost).label("cost"))
            .where(
                LLMUsageLog.plugin_id == plugin_id,
                LLMUsageLog.usage_date == today
            )
        )
        
        result = await db.execute(daily_query)
        daily_cost = result.scalar() or 0.0
        
        # Calculate month-to-date
        month_start = today.replace(day=1)
        monthly_query = (
            select(func.sum(LLMUsageLog.estimated_cost).label("cost"))
            .where(
                LLMUsageLog.plugin_id == plugin_id,
                LLMUsageLog.usage_date >= month_start
            )
        )
        
        result = await db.execute(monthly_query)
        monthly_cost = result.scalar() or 0.0
        
        alerts = []
        
        if daily_cost >= budget.daily_limit:
            alerts.append("daily_limit_exceeded")
        elif daily_cost >= budget.daily_limit * budget.alert_threshold:
            alerts.append("daily_limit_warning")
        
        if monthly_cost >= budget.monthly_limit:
            alerts.append("monthly_limit_exceeded")
        elif monthly_cost >= budget.monthly_limit * budget.alert_threshold:
            alerts.append("monthly_limit_warning")
        
        return {
            "daily_cost": round(daily_cost, 4),
            "daily_limit": budget.daily_limit,
            "daily_percent": round(daily_cost / budget.daily_limit * 100, 1),
            "monthly_cost": round(monthly_cost, 4),
            "monthly_limit": budget.monthly_limit,
            "monthly_percent": round(monthly_cost / budget.monthly_limit * 100, 1),
            "alerts": alerts,
            "within_budget": len([a for a in alerts if "exceeded" in a]) == 0
        }


# Singleton instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker(db: AsyncSession = None) -> CostTracker:
    """Get singleton cost tracker."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker(db)
    return _cost_tracker
