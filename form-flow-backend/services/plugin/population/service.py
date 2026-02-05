"""
Database Population Service Module

Handles inserting extracted data into external plugin databases.
Features:
- Transaction management with rollback
- Partial success tracking
- Dead letter queue for failures
- Batched inserts for efficiency

Reuses database connectors from services.plugin.database.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from services.plugin.database import (
    DatabaseConnector, DatabaseType, ConnectionConfig,
    get_connector_factory
)
from services.plugin.security.encryption import get_encryption_service
from services.plugin.population.dead_letter import DeadLetterQueue
from utils.logging import get_logger

logger = get_logger(__name__)


class InsertStatus(str, Enum):
    """Status of an insert operation."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some rows succeeded, some failed
    PENDING = "pending"
    RETRYING = "retrying"


@dataclass
class InsertResult:
    """Result of inserting a single row."""
    table_name: str
    status: InsertStatus
    row_id: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class PopulationResult:
    """Result of a complete population operation."""
    session_id: str
    plugin_id: int
    overall_status: InsertStatus
    inserted_rows: List[InsertResult] = field(default_factory=list)
    failed_rows: List[InsertResult] = field(default_factory=list)
    total_tables: int = 0
    successful_tables: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "plugin_id": self.plugin_id,
            "overall_status": self.overall_status.value,
            "total_tables": self.total_tables,
            "successful_tables": self.successful_tables,
            "inserted_count": len(self.inserted_rows),
            "failed_count": len(self.failed_rows),
            "duration_ms": self.duration_ms,
            "inserted_rows": [
                {"table": r.table_name, "row_id": r.row_id}
                for r in self.inserted_rows
            ],
            "failed_rows": [
                {"table": r.table_name, "error": r.error, "data": r.data}
                for r in self.failed_rows
            ],
        }


class PopulationService:
    """
    Database population service.
    
    Inserts extracted data into external plugin databases with:
    - Transaction management (all-or-nothing per table)
    - Partial success tracking (record what succeeded)
    - Dead letter queue for failed inserts
    
    Usage:
        service = PopulationService()
        result = await service.populate(
            plugin_id=1,
            session_id="abc123",
            table_configs=[...],
            extracted_values={"name": "John", "email": "john@example.com"}
        )
    """
    
    def __init__(self, dead_letter_queue: Optional[DeadLetterQueue] = None):
        """
        Initialize population service.
        
        Args:
            dead_letter_queue: Optional DLQ for failed inserts
        """
        self._dlq = dead_letter_queue
        self._encryption = get_encryption_service()
    
    async def populate(
        self,
        plugin_id: int,
        session_id: str,
        connection_config_encrypted: str,
        db_type: DatabaseType,
        table_configs: List[Dict[str, Any]],
        extracted_values: Dict[str, Any],
        use_transaction: bool = True
    ) -> PopulationResult:
        """
        Populate external database with extracted values.
        
        Args:
            plugin_id: Plugin ID
            session_id: Session ID for tracking
            connection_config_encrypted: Encrypted connection config
            db_type: Database type (postgresql, mysql)
            table_configs: List of table configurations with field mappings
            extracted_values: Dict of column_name -> value
            use_transaction: If True, use transaction per table
            
        Returns:
            PopulationResult with success/failure details
        """
        result = PopulationResult(
            session_id=session_id,
            plugin_id=plugin_id,
            overall_status=InsertStatus.PENDING,
            total_tables=len(table_configs),
            start_time=datetime.now()
        )
        
        # Decrypt connection config
        config_dict = self._encryption.decrypt(connection_config_encrypted)
        config = ConnectionConfig.from_dict(config_dict)
        
        # Get connector
        factory = await get_connector_factory()
        connector = await factory.get_connector(plugin_id, db_type, config)
        
        # Process each table
        for table_config in table_configs:
            table_result = await self._populate_table(
                connector=connector,
                table_config=table_config,
                extracted_values=extracted_values,
                use_transaction=use_transaction
            )
            
            if table_result.status == InsertStatus.SUCCESS:
                result.inserted_rows.append(table_result)
                result.successful_tables += 1
            else:
                result.failed_rows.append(table_result)
                
                # Add to DLQ if available
                if self._dlq:
                    await self._dlq.enqueue(
                        plugin_id=plugin_id,
                        session_id=session_id,
                        table_name=table_result.table_name,
                        data=table_result.data,
                        error=table_result.error
                    )
        
        # Determine overall status
        result.end_time = datetime.now()
        
        if result.successful_tables == result.total_tables:
            result.overall_status = InsertStatus.SUCCESS
        elif result.successful_tables == 0:
            result.overall_status = InsertStatus.FAILED
        else:
            result.overall_status = InsertStatus.PARTIAL
        
        logger.info(
            f"Population complete for session {session_id}: "
            f"{result.successful_tables}/{result.total_tables} tables, "
            f"{result.duration_ms}ms"
        )
        
        return result
    
    async def _populate_table(
        self,
        connector: DatabaseConnector,
        table_config: Dict[str, Any],
        extracted_values: Dict[str, Any],
        use_transaction: bool
    ) -> InsertResult:
        """
        Populate a single table.
        
        Args:
            connector: Database connector
            table_config: Table configuration with fields
            extracted_values: Extracted values
            use_transaction: Use transaction
            
        Returns:
            InsertResult for this table
        """
        table_name = table_config.get("table_name", "")
        fields = table_config.get("fields", [])
        
        # Build row data from field mappings
        row_data = {}
        for field_config in fields:
            column_name = field_config.get("column_name", "")
            if column_name in extracted_values:
                row_data[column_name] = extracted_values[column_name]
            elif field_config.get("default_value") is not None:
                row_data[column_name] = field_config["default_value"]
        
        if not row_data:
            return InsertResult(
                table_name=table_name,
                status=InsertStatus.FAILED,
                data=row_data,
                error="No data to insert"
            )
        
        try:
            if use_transaction:
                async with connector.transaction():
                    row_id = await connector.insert(table_name, row_data)
            else:
                row_id = await connector.insert(table_name, row_data)
            
            logger.debug(f"Inserted row {row_id} into {table_name}")
            
            return InsertResult(
                table_name=table_name,
                status=InsertStatus.SUCCESS,
                row_id=row_id,
                data=row_data
            )
        
        except Exception as e:
            logger.error(f"Failed to insert into {table_name}: {e}")
            return InsertResult(
                table_name=table_name,
                status=InsertStatus.FAILED,
                data=row_data,
                error=str(e)
            )
    
    async def populate_batch(
        self,
        plugin_id: int,
        session_id: str,
        connection_config_encrypted: str,
        db_type: DatabaseType,
        table_name: str,
        rows: List[Dict[str, Any]]
    ) -> Tuple[int, List[InsertResult]]:
        """
        Batch insert multiple rows into a single table.
        
        Args:
            plugin_id: Plugin ID
            session_id: Session ID
            connection_config_encrypted: Encrypted connection config
            db_type: Database type
            table_name: Target table
            rows: List of row data dicts
            
        Returns:
            (insert_count, failed_results)
        """
        if not rows:
            return 0, []
        
        # Decrypt and get connector
        config_dict = self._encryption.decrypt(connection_config_encrypted)
        config = ConnectionConfig.from_dict(config_dict)
        
        factory = await get_connector_factory()
        connector = await factory.get_connector(plugin_id, db_type, config)
        
        try:
            count = await connector.insert_many(table_name, rows)
            logger.info(f"Batch inserted {count} rows into {table_name}")
            return count, []
        
        except Exception as e:
            logger.error(f"Batch insert failed for {table_name}: {e}")
            
            # Return all rows as failed
            failed = [
                InsertResult(
                    table_name=table_name,
                    status=InsertStatus.FAILED,
                    data=row,
                    error=str(e)
                )
                for row in rows
            ]
            return 0, failed


# Singleton instance
_population_service: Optional[PopulationService] = None


def get_population_service(
    dead_letter_queue: Optional[DeadLetterQueue] = None
) -> PopulationService:
    """Get singleton population service."""
    global _population_service
    if _population_service is None:
        _population_service = PopulationService(dead_letter_queue)
    return _population_service
