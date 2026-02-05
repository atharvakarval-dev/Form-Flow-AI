"""
Database Connector Infrastructure

Abstract base class and factory for external database connections.
Supports PostgreSQL and MySQL with:
- Connection pooling
- Circuit breaker protection
- Schema introspection
- Parameterized query execution (SQL injection safe)

DRY Design:
- Single base class with template methods
- Factory pattern for connector creation
- Reuses existing ResilientService for circuit breaker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
from contextlib import asynccontextmanager
import asyncio

from utils.circuit_breaker import ResilientService, get_circuit_breaker
from utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class DatabaseType(str, Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    # MONGODB = "mongodb"  # Future


@dataclass
class ConnectionConfig:
    """
    Database connection configuration.
    
    Decrypted from plugin's connection_config_encrypted.
    """
    host: str
    port: int
    database: str
    username: str
    password: str
    
    # Optional TLS settings
    ssl_enabled: bool = False
    ssl_ca_cert: Optional[str] = None
    
    # Pool settings (applied at factory level)
    pool_size: int = 5
    pool_max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600  # Recycle connections after 1 hour
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectionConfig":
        """Create from dictionary (decrypted config)."""
        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 5432),
            database=data.get("database", ""),
            username=data.get("username", ""),
            password=data.get("password", ""),
            ssl_enabled=data.get("ssl_enabled", False),
            ssl_ca_cert=data.get("ssl_ca_cert"),
            pool_size=data.get("pool_size", 5),
            pool_max_overflow=data.get("pool_max_overflow", 10),
            pool_timeout=data.get("pool_timeout", 30),
            pool_recycle=data.get("pool_recycle", 3600),
        )


@dataclass
class ColumnInfo:
    """Schema information for a database column."""
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    default_value: Optional[str] = None
    max_length: Optional[int] = None


@dataclass
class TableInfo:
    """Schema information for a database table."""
    name: str
    columns: List[ColumnInfo]
    
    def get_column(self, name: str) -> Optional[ColumnInfo]:
        """Get column by name (case-insensitive)."""
        name_lower = name.lower()
        return next((c for c in self.columns if c.name.lower() == name_lower), None)
    
    def has_column(self, name: str) -> bool:
        """Check if column exists."""
        return self.get_column(name) is not None


class DatabaseConnector(ABC, ResilientService):
    """
    Abstract base class for database connectors.
    
    Provides:
    - Connection pooling (via subclass implementation)
    - Circuit breaker protection (via ResilientService)
    - Schema introspection
    - Parameterized query execution
    
    Subclasses must implement:
    - _create_pool(): Create connection pool
    - _execute_query(): Execute SQL with params
    - _introspect_table(): Get table schema
    """
    
    def __init__(self, plugin_id: int, config: ConnectionConfig):
        """
        Initialize connector.
        
        Args:
            plugin_id: Plugin ID (for circuit breaker naming)
            config: Decrypted connection configuration
        """
        super().__init__(f"db_connector_{plugin_id}")
        self.plugin_id = plugin_id
        self.config = config
        self._pool = None
        self._pool_lock = asyncio.Lock()
    
    @property
    def db_type(self) -> DatabaseType:
        """Database type this connector handles."""
        raise NotImplementedError
    
    async def connect(self) -> None:
        """
        Initialize connection pool (lazy, thread-safe).
        
        Called automatically on first operation.
        """
        if self._pool is None:
            async with self._pool_lock:
                if self._pool is None:  # Double-check after lock
                    logger.info(f"Creating connection pool for plugin {self.plugin_id}")
                    self._pool = await self._create_pool()
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            async with self._pool_lock:
                if self._pool is not None:
                    logger.info(f"Closing connection pool for plugin {self.plugin_id}")
                    await self._close_pool()
                    self._pool = None
    
    @abstractmethod
    async def _create_pool(self) -> Any:
        """Create database connection pool. Implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _close_pool(self) -> None:
        """Close connection pool. Implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        fetch: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a query with parameters.
        
        Args:
            query: SQL query with parameter placeholders
            params: Parameter values
            fetch: If True, return results; if False, return None
            
        Returns:
            List of row dicts if fetch=True, else None
        """
        pass
    
    @abstractmethod
    async def _introspect_table(self, table_name: str) -> Optional[TableInfo]:
        """
        Get schema information for a table.
        
        Args:
            table_name: Table to introspect
            
        Returns:
            TableInfo or None if table doesn't exist
        """
        pass
    
    async def test_connection(self) -> bool:
        """
        Test database connectivity.
        
        Returns True if connection works, False otherwise.
        """
        try:
            await self.connect()
            await self._execute_query("SELECT 1")
            logger.info(f"Connection test passed for plugin {self.plugin_id}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed for plugin {self.plugin_id}: {e}")
            return False
    
    async def get_table_schema(self, table_name: str) -> Optional[TableInfo]:
        """
        Get table schema with circuit breaker protection.
        
        Returns TableInfo or None if table doesn't exist.
        """
        await self.connect()
        return await self.call_with_retry(
            self._introspect_table,
            table_name,
            max_retries=2
        )
    
    async def validate_schema(
        self,
        table_name: str,
        expected_columns: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that a table has expected columns.
        
        Args:
            table_name: Table to validate
            expected_columns: List of column names that must exist
            
        Returns:
            (is_valid, missing_columns)
        """
        table_info = await self.get_table_schema(table_name)
        
        if table_info is None:
            return False, [f"Table '{table_name}' does not exist"]
        
        missing = [col for col in expected_columns if not table_info.has_column(col)]
        return len(missing) == 0, missing
    
    async def insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> Optional[int]:
        """
        Insert a row with circuit breaker protection.
        
        Args:
            table: Target table
            data: Column-value pairs
            
        Returns:
            Inserted row ID (if driver supports) or None
            
        Uses parameterized queries to prevent SQL injection.
        """
        await self.connect()
        
        columns = list(data.keys())
        placeholders = self._get_placeholders(columns)
        
        query = f"INSERT INTO {self._quote_identifier(table)} ({', '.join(self._quote_identifier(c) for c in columns)}) VALUES ({placeholders})"
        
        return await self.call_with_retry(
            self._execute_insert,
            query,
            data,
            max_retries=2
        )
    
    @abstractmethod
    async def _execute_insert(
        self,
        query: str,
        params: Dict[str, Any]
    ) -> Optional[int]:
        """Execute insert and return inserted ID."""
        pass
    
    @abstractmethod
    def _get_placeholders(self, columns: List[str]) -> str:
        """Get placeholder string for insert query (DB-specific)."""
        pass
    
    @abstractmethod
    def _quote_identifier(self, name: str) -> str:
        """Quote identifier to prevent injection (DB-specific)."""
        pass
    
    async def insert_many(
        self,
        table: str,
        rows: List[Dict[str, Any]]
    ) -> int:
        """
        Insert multiple rows in a batch.
        
        Returns count of inserted rows.
        """
        if not rows:
            return 0
        
        await self.connect()
        
        # Use first row to determine columns
        columns = list(rows[0].keys())
        
        return await self.call_with_retry(
            self._execute_insert_many,
            table,
            columns,
            rows,
            max_retries=2
        )
    
    @abstractmethod
    async def _execute_insert_many(
        self,
        table: str,
        columns: List[str],
        rows: List[Dict[str, Any]]
    ) -> int:
        """Execute batch insert. Implemented by subclasses."""
        pass
    
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for transactions.
        
        Usage:
            async with connector.transaction():
                await connector.insert(...)
                await connector.insert(...)
        """
        await self.connect()
        async with self._get_transaction_context():
            yield
    
    @abstractmethod
    @asynccontextmanager
    async def _get_transaction_context(self):
        """Get DB-specific transaction context manager."""
        pass


class ConnectorFactory:
    """
    Factory for creating database connectors.
    
    Caches connectors by plugin_id for connection reuse.
    Thread-safe singleton pattern.
    """
    
    _instance: Optional["ConnectorFactory"] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._connectors: Dict[int, DatabaseConnector] = {}
        self._connector_lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(cls) -> "ConnectorFactory":
        """Get singleton factory instance."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def get_connector(
        self,
        plugin_id: int,
        db_type: DatabaseType,
        config: ConnectionConfig
    ) -> DatabaseConnector:
        """
        Get or create a connector for a plugin.
        
        Connectors are cached by plugin_id for connection reuse.
        """
        async with self._connector_lock:
            if plugin_id not in self._connectors:
                connector = self._create_connector(db_type, plugin_id, config)
                self._connectors[plugin_id] = connector
                logger.info(f"Created {db_type.value} connector for plugin {plugin_id}")
            
            return self._connectors[plugin_id]
    
    def _create_connector(
        self,
        db_type: DatabaseType,
        plugin_id: int,
        config: ConnectionConfig
    ) -> DatabaseConnector:
        """Create a connector based on database type."""
        if db_type == DatabaseType.POSTGRESQL:
            from services.plugin.database.postgresql import PostgreSQLConnector
            return PostgreSQLConnector(plugin_id, config)
        
        elif db_type == DatabaseType.MYSQL:
            from services.plugin.database.mysql import MySQLConnector
            return MySQLConnector(plugin_id, config)
        
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    async def close_connector(self, plugin_id: int) -> None:
        """Close and remove a connector."""
        async with self._connector_lock:
            if plugin_id in self._connectors:
                await self._connectors[plugin_id].disconnect()
                del self._connectors[plugin_id]
                logger.info(f"Closed connector for plugin {plugin_id}")
    
    async def close_all(self) -> None:
        """Close all connectors (shutdown)."""
        async with self._connector_lock:
            for plugin_id in list(self._connectors.keys()):
                await self._connectors[plugin_id].disconnect()
            self._connectors.clear()
            logger.info("Closed all database connectors")


async def get_connector_factory() -> ConnectorFactory:
    """Get the global connector factory instance."""
    return await ConnectorFactory.get_instance()
