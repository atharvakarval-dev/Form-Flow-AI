"""
PostgreSQL Connector Module

PostgreSQL database connector using asyncpg.
Features:
- Connection pooling with configurable size
- Circuit breaker protection (via base class)
- Schema introspection
- Parameterized queries (SQL injection safe)
- RETURNING clause for insert IDs
"""

from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from services.plugin.database.base import (
    DatabaseConnector, DatabaseType, ConnectionConfig,
    TableInfo, ColumnInfo
)
from utils.logging import get_logger

logger = get_logger(__name__)


class PostgreSQLConnector(DatabaseConnector):
    """
    PostgreSQL connector using asyncpg.
    
    Uses native PostgreSQL parameterized queries ($1, $2, ...).
    Connection pool is created lazily on first operation.
    """
    
    @property
    def db_type(self) -> DatabaseType:
        return DatabaseType.POSTGRESQL
    
    async def _create_pool(self) -> Any:
        """Create asyncpg connection pool."""
        import asyncpg
        
        # Build connection string
        dsn = (
            f"postgresql://{self.config.username}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{self.config.database}"
        )
        
        # SSL configuration
        ssl_context = None
        if self.config.ssl_enabled:
            import ssl
            ssl_context = ssl.create_default_context()
            if self.config.ssl_ca_cert:
                ssl_context.load_verify_locations(self.config.ssl_ca_cert)
        
        pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=self.config.pool_size,
            max_inactive_connection_lifetime=self.config.pool_recycle,
            command_timeout=self.config.pool_timeout,
            ssl=ssl_context if self.config.ssl_enabled else None
        )
        
        logger.info(f"PostgreSQL pool created for plugin {self.plugin_id}")
        return pool
    
    async def _close_pool(self) -> None:
        """Close asyncpg pool."""
        if self._pool:
            await self._pool.close()
            logger.info(f"PostgreSQL pool closed for plugin {self.plugin_id}")
    
    async def _execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        fetch: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute query with asyncpg."""
        # Convert dict params to positional (asyncpg uses $1, $2, ...)
        param_values = list(params.values()) if params else []
        
        async with self._pool.acquire() as conn:
            if fetch:
                rows = await conn.fetch(query, *param_values)
                return [dict(row) for row in rows]
            else:
                await conn.execute(query, *param_values)
                return None
    
    async def _introspect_table(self, table_name: str) -> Optional[TableInfo]:
        """
        Get PostgreSQL table schema.
        
        Uses information_schema for portability.
        """
        query = """
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable = 'YES' as is_nullable,
                c.column_default,
                c.character_maximum_length,
                COALESCE(
                    (SELECT true FROM information_schema.table_constraints tc
                     JOIN information_schema.key_column_usage kcu 
                     ON tc.constraint_name = kcu.constraint_name
                     WHERE tc.constraint_type = 'PRIMARY KEY' 
                     AND tc.table_name = c.table_name
                     AND kcu.column_name = c.column_name
                     LIMIT 1),
                    false
                ) as is_primary_key
            FROM information_schema.columns c
            WHERE c.table_name = $1
            AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, table_name)
        
        if not rows:
            return None
        
        columns = [
            ColumnInfo(
                name=row['column_name'],
                data_type=row['data_type'],
                is_nullable=row['is_nullable'],
                is_primary_key=row['is_primary_key'],
                default_value=row['column_default'],
                max_length=row['character_maximum_length']
            )
            for row in rows
        ]
        
        return TableInfo(name=table_name, columns=columns)
    
    async def _execute_insert(
        self,
        query: str,
        params: Dict[str, Any]
    ) -> Optional[int]:
        """Execute insert with RETURNING id."""
        # Add RETURNING clause for PostgreSQL
        if "RETURNING" not in query.upper():
            query = f"{query} RETURNING id"
        
        param_values = list(params.values())
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *param_values)
            return row['id'] if row and 'id' in row else None
    
    def _get_placeholders(self, columns: List[str]) -> str:
        """PostgreSQL uses $1, $2, ... placeholders."""
        return ", ".join(f"${i+1}" for i in range(len(columns)))
    
    def _quote_identifier(self, name: str) -> str:
        """Quote identifier with double quotes (PostgreSQL)."""
        # Escape any double quotes in the name
        escaped = name.replace('"', '""')
        return f'"{escaped}"'
    
    async def _execute_insert_many(
        self,
        table: str,
        columns: List[str],
        rows: List[Dict[str, Any]]
    ) -> int:
        """Batch insert using executemany."""
        placeholders = self._get_placeholders(columns)
        quoted_columns = ", ".join(self._quote_identifier(c) for c in columns)
        query = f"INSERT INTO {self._quote_identifier(table)} ({quoted_columns}) VALUES ({placeholders})"
        
        # Convert rows to list of tuples
        values = [tuple(row.get(c) for c in columns) for row in rows]
        
        async with self._pool.acquire() as conn:
            result = await conn.executemany(query, values)
        
        # executemany returns status string like 'INSERT 0 5'
        # Parse to get row count
        try:
            count = int(result.split()[-1])
        except (ValueError, IndexError):
            count = len(rows)  # Fallback
        
        return count
    
    @asynccontextmanager
    async def _get_transaction_context(self):
        """PostgreSQL transaction context."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Temporarily replace pool with transaction connection
                original_pool = self._pool
                self._pool = _SingleConnectionPool(conn)
                try:
                    yield
                finally:
                    self._pool = original_pool


class _SingleConnectionPool:
    """
    Wrapper to use a single connection as a 'pool'.
    
    Used during transactions to ensure all queries use the same connection.
    """
    
    def __init__(self, conn):
        self._conn = conn
    
    @asynccontextmanager
    async def acquire(self):
        yield self._conn
