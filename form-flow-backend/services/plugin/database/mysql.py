"""
MySQL Connector Module

MySQL database connector using aiomysql.
Features:
- Connection pooling with configurable size
- Circuit breaker protection (via base class)
- Schema introspection
- Parameterized queries (SQL injection safe)
- LAST_INSERT_ID for insert IDs
"""

from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from services.plugin.database.base import (
    DatabaseConnector, DatabaseType, ConnectionConfig,
    TableInfo, ColumnInfo
)
from utils.logging import get_logger

logger = get_logger(__name__)


class MySQLConnector(DatabaseConnector):
    """
    MySQL connector using aiomysql.
    
    Uses MySQL format placeholders (%s) with dict params.
    Connection pool is created lazily on first operation.
    """
    
    @property
    def db_type(self) -> DatabaseType:
        return DatabaseType.MYSQL
    
    async def _create_pool(self) -> Any:
        """Create aiomysql connection pool."""
        import aiomysql
        
        # SSL configuration
        ssl_context = None
        if self.config.ssl_enabled:
            import ssl
            ssl_context = ssl.create_default_context()
            if self.config.ssl_ca_cert:
                ssl_context.load_verify_locations(self.config.ssl_ca_cert)
        
        pool = await aiomysql.create_pool(
            host=self.config.host,
            port=self.config.port,
            user=self.config.username,
            password=self.config.password,
            db=self.config.database,
            minsize=1,
            maxsize=self.config.pool_size,
            pool_recycle=self.config.pool_recycle,
            connect_timeout=self.config.pool_timeout,
            ssl=ssl_context if self.config.ssl_enabled else None,
            autocommit=True  # Use explicit transactions when needed
        )
        
        logger.info(f"MySQL pool created for plugin {self.plugin_id}")
        return pool
    
    async def _close_pool(self) -> None:
        """Close aiomysql pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info(f"MySQL pool closed for plugin {self.plugin_id}")
    
    async def _execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        fetch: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute query with aiomysql."""
        param_values = tuple(params.values()) if params else ()
        
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, param_values)
                if fetch:
                    rows = await cur.fetchall()
                    return list(rows)
                return None
    
    async def _introspect_table(self, table_name: str) -> Optional[TableInfo]:
        """
        Get MySQL table schema.
        
        Uses information_schema for portability.
        """
        import aiomysql
        
        query = """
            SELECT 
                COLUMN_NAME as column_name,
                DATA_TYPE as data_type,
                IS_NULLABLE = 'YES' as is_nullable,
                COLUMN_DEFAULT as column_default,
                CHARACTER_MAXIMUM_LENGTH as max_length,
                COLUMN_KEY = 'PRI' as is_primary_key
            FROM information_schema.COLUMNS
            WHERE TABLE_NAME = %s
            AND TABLE_SCHEMA = DATABASE()
            ORDER BY ORDINAL_POSITION
        """
        
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, (table_name,))
                rows = await cur.fetchall()
        
        if not rows:
            return None
        
        columns = [
            ColumnInfo(
                name=row['column_name'],
                data_type=row['data_type'],
                is_nullable=bool(row['is_nullable']),
                is_primary_key=bool(row['is_primary_key']),
                default_value=row['column_default'],
                max_length=row['max_length']
            )
            for row in rows
        ]
        
        return TableInfo(name=table_name, columns=columns)
    
    async def _execute_insert(
        self,
        query: str,
        params: Dict[str, Any]
    ) -> Optional[int]:
        """Execute insert and get LAST_INSERT_ID."""
        import aiomysql
        
        param_values = tuple(params.values())
        
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, param_values)
                await cur.execute("SELECT LAST_INSERT_ID() as id")
                row = await cur.fetchone()
                return row['id'] if row else None
    
    def _get_placeholders(self, columns: List[str]) -> str:
        """MySQL uses %s placeholders."""
        return ", ".join("%s" for _ in columns)
    
    def _quote_identifier(self, name: str) -> str:
        """Quote identifier with backticks (MySQL)."""
        # Escape any backticks in the name
        escaped = name.replace('`', '``')
        return f'`{escaped}`'
    
    async def _execute_insert_many(
        self,
        table: str,
        columns: List[str],
        rows: List[Dict[str, Any]]
    ) -> int:
        """Batch insert using executemany."""
        import aiomysql
        
        placeholders = self._get_placeholders(columns)
        quoted_columns = ", ".join(self._quote_identifier(c) for c in columns)
        query = f"INSERT INTO {self._quote_identifier(table)} ({quoted_columns}) VALUES ({placeholders})"
        
        # Convert rows to list of tuples
        values = [tuple(row.get(c) for c in columns) for row in rows]
        
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.executemany(query, values)
                return cur.rowcount
    
    @asynccontextmanager
    async def _get_transaction_context(self):
        """MySQL transaction context."""
        import aiomysql
        
        async with self._pool.acquire() as conn:
            await conn.begin()
            # Create a wrapper pool for this transaction
            original_pool = self._pool
            self._pool = _MySQLSingleConnectionPool(conn)
            try:
                yield
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
            finally:
                self._pool = original_pool


class _MySQLSingleConnectionPool:
    """
    Wrapper to use a single connection as a 'pool'.
    
    Used during transactions to ensure all queries use the same connection.
    """
    
    def __init__(self, conn):
        self._conn = conn
    
    @asynccontextmanager
    async def acquire(self):
        yield self._conn
