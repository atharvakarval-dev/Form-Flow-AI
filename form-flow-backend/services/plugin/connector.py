"""
Plugin Connector Module

Handles connections to external databases configured in plugins.
Supports PostgreSQL and MySQL database types.

Features:
- Secure credential handling (decrypts connection config)
- Connection pooling
- Data insertion from collected form data
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
import asyncpg

from core.plugin_models import Plugin
from services.plugin.security.encryption import get_encryption_service
from utils.logging import get_logger

logger = get_logger(__name__)


class PluginConnector:
    """
    Connector for external databases configured in plugins.
    
    Handles secure connection and data insertion to user's
    PostgreSQL or MySQL databases.
    """
    
    def __init__(self, plugin: Plugin, db: AsyncSession):
        """
        Initialize connector with a plugin and database session.
        
        Args:
            plugin: The plugin containing connection config
            db: The FormFlow database session (for decryption key lookup)
        """
        self.plugin = plugin
        self.db = db
        self._connection = None
    
    async def _get_connection_config(self) -> Dict[str, Any]:
        """
        Get and decrypt the connection configuration.
        
        Returns:
            Decrypted connection config dictionary
        """
        # Get the encrypted connection config
        encrypted_config = self.plugin.connection_config_encrypted
        if not encrypted_config:
            raise ValueError("Plugin has no connection configuration")
        
        # Decrypt using the encryption service
        encryption_service = get_encryption_service()
        config = encryption_service.decrypt(encrypted_config)
        return config
    
    async def _connect_postgres(self, config: Dict[str, Any]) -> asyncpg.Connection:
        """
        Establish a PostgreSQL connection.
        
        Args:
            config: Decrypted connection config
            
        Returns:
            asyncpg connection
        """
        return await asyncpg.connect(
            host=config.get("host", "localhost"),
            port=config.get("port", 5432),
            user=config.get("username"),
            password=config.get("password"),
            database=config.get("database"),
            timeout=10
        )
    
    async def connect(self) -> Any:
        """
        Establish connection to the external database.
        
        Returns:
            Database connection
        """
        config = await self._get_connection_config()
        
        if self.plugin.database_type == "postgresql":
            self._connection = await self._connect_postgres(config)
        elif self.plugin.database_type == "mysql":
            # MySQL support (future)
            raise NotImplementedError("MySQL support coming soon")
        else:
            raise ValueError(f"Unsupported database type: {self.plugin.database_type}")
        
        logger.info(f"Connected to {self.plugin.database_type} database for plugin {self.plugin.id}")
        return self._connection
    
    async def disconnect(self):
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info(f"Disconnected from external database for plugin {self.plugin.id}")
    
    def _parse_field_value(self, value: str, column_type: str) -> Any:
        """
        Parse a string value to the appropriate Python type.
        
        Args:
            value: String value to parse
            column_type: The column type (text, integer, boolean, etc.)
            
        Returns:
            Parsed value in appropriate type
        """
        if value is None or value == "":
            return None
        
        try:
            if column_type == "integer":
                return int(value)
            elif column_type == "decimal":
                return float(value)
            elif column_type == "boolean":
                return value.lower() in ("true", "yes", "1", "y")
            elif column_type == "date":
                # Try common date formats
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                    try:
                        return datetime.strptime(value, fmt).date()
                    except ValueError:
                        continue
                return value  # Return as string if can't parse
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)
    
    async def insert_collected_data(
        self,
        extracted_fields: Dict[str, Any],
        form_schema: List[Dict[str, Any]]
    ) -> int:
        """
        Insert collected data into the external database.
        
        Args:
            extracted_fields: Dict of field_name -> value collected from user
            form_schema: The form schema with table/field definitions
            
        Returns:
            Number of records created
        """
        if not extracted_fields:
            logger.warning("No data to insert")
            return 0
        
        connection = await self.connect()
        records_created = 0
        
        try:
            # Group fields by table
            tables_data: Dict[str, Dict[str, Any]] = {}
            
            for field_name, value in extracted_fields.items():
                # Field names are in format "table_name.column_name"
                if "." in field_name:
                    table_name, column_name = field_name.split(".", 1)
                else:
                    # Use first table as default
                    table_name = form_schema[0]["table"] if form_schema else "data"
                    column_name = field_name
                
                if table_name not in tables_data:
                    tables_data[table_name] = {}
                
                # Find column type from schema
                column_type = "text"
                for table_schema in form_schema:
                    if table_schema.get("table") == table_name:
                        for field in table_schema.get("fields", []):
                            if field.get("name", "").endswith(column_name):
                                column_type = field.get("type", "text")
                                break
                
                # Parse and store
                tables_data[table_name][column_name] = self._parse_field_value(value, column_type)
            
            # Insert into each table
            for table_name, row_data in tables_data.items():
                if not row_data:
                    continue
                
                # Build INSERT query
                columns = list(row_data.keys())
                placeholders = [f"${i+1}" for i in range(len(columns))]
                values = list(row_data.values())
                
                query = f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                """
                
                logger.info(f"Inserting into {table_name}: {columns}")
                
                await connection.execute(query, *values)
                records_created += 1
            
            logger.info(f"Created {records_created} records for plugin {self.plugin.id}")
            
        except Exception as e:
            logger.error(f"Failed to insert data: {e}")
            raise
        finally:
            await self.disconnect()
        
        return records_created
    
    async def test_connection(self) -> Tuple[bool, str]:
        """
        Test the connection to the external database.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            connection = await self.connect()
            
            # Simple test query
            if self.plugin.database_type == "postgresql":
                result = await connection.fetchval("SELECT 1")
                
            await self.disconnect()
            
            return True, "Connection successful"
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False, str(e)
