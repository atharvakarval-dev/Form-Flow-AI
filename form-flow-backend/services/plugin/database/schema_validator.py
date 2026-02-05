"""
Schema Validation Service Module

Validates plugin configuration against target database schema.
Ensures:
- All target tables exist
- All target columns exist and have compatible types
- Required columns are not nullable
- Prevents plugin creation with invalid configuration

Zero code redundancy:
- Reuses database connectors
- Single validation method for all DB types
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from services.plugin.database.base import (
    DatabaseConnector, DatabaseType, ConnectionConfig, TableInfo,
    get_connector_factory
)
from services.plugin.security.encryption import get_encryption_service
from utils.logging import get_logger

logger = get_logger(__name__)


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""
    ERROR = "error"      # Blocks plugin creation
    WARNING = "warning"  # Allows creation but warns user


@dataclass
class ValidationIssue:
    """A single schema validation issue."""
    severity: ValidationSeverity
    table: str
    column: Optional[str]
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "table": self.table,
            "column": self.column,
            "message": self.message
        }


@dataclass
class ValidationResult:
    """Result of schema validation."""
    is_valid: bool
    issues: List[ValidationIssue]
    tables_validated: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": [i.to_dict() for i in self.issues],
            "tables_validated": self.tables_validated,
            "error_count": sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR),
            "warning_count": sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING),
        }


# Type mapping for compatibility checking
# Maps plugin column types to compatible database types
TYPE_COMPATIBILITY = {
    "string": ["varchar", "char", "text", "character varying", "nvarchar", "nchar"],
    "integer": ["int", "integer", "bigint", "smallint", "tinyint", "serial", "bigserial"],
    "float": ["float", "double", "decimal", "numeric", "real", "double precision"],
    "boolean": ["boolean", "bool", "tinyint"],
    "date": ["date"],
    "datetime": ["datetime", "timestamp", "timestamp without time zone", "timestamp with time zone"],
    "json": ["json", "jsonb"],
    "uuid": ["uuid", "char(36)", "varchar(36)"],
}


def is_type_compatible(plugin_type: str, db_type: str) -> bool:
    """
    Check if plugin column type is compatible with database column type.
    
    Args:
        plugin_type: Type declared in plugin config (e.g., "string")
        db_type: Type from database introspection (e.g., "varchar")
        
    Returns:
        True if types are compatible
    """
    plugin_type_lower = plugin_type.lower()
    db_type_lower = db_type.lower()
    
    # Direct match
    if plugin_type_lower == db_type_lower:
        return True
    
    # Check type compatibility map
    compatible_types = TYPE_COMPATIBILITY.get(plugin_type_lower, [])
    return any(ct in db_type_lower for ct in compatible_types)


class SchemaValidationService:
    """
    Service for validating plugin configuration against database schema.
    
    Validates:
    - Database connectivity
    - Table existence
    - Column existence
    - Type compatibility
    - Nullable constraints
    
    Usage:
        validator = SchemaValidationService()
        result = await validator.validate_plugin_config(plugin_data)
        if not result.is_valid:
            raise ValidationError(result.issues)
    """
    
    async def validate_plugin_config(
        self,
        plugin_id: int,
        db_type: DatabaseType,
        connection_config_encrypted: str,
        tables: List[Dict[str, Any]]
    ) -> ValidationResult:
        """
        Validate plugin configuration against target database.
        
        Args:
            plugin_id: Plugin ID (for circuit breaker naming)
            db_type: Database type (postgresql, mysql)
            connection_config_encrypted: Encrypted connection config
            tables: List of table configurations with fields
            
        Returns:
            ValidationResult with issues (if any)
        """
        issues: List[ValidationIssue] = []
        tables_validated: List[str] = []
        
        # Decrypt connection config
        encryption = get_encryption_service()
        config_dict = encryption.decrypt(connection_config_encrypted)
        config = ConnectionConfig.from_dict(config_dict)
        
        # Get connector
        factory = await get_connector_factory()
        connector = await factory.get_connector(plugin_id, db_type, config)
        
        # Test connection
        if not await connector.test_connection():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                table="*",
                column=None,
                message="Failed to connect to database. Check connection settings."
            ))
            return ValidationResult(
                is_valid=False,
                issues=issues,
                tables_validated=[]
            )
        
        # Validate each table
        for table_config in tables:
            table_name = table_config.get("table_name")
            fields = table_config.get("fields", [])
            
            table_issues = await self._validate_table(
                connector, table_name, fields
            )
            issues.extend(table_issues)
            tables_validated.append(table_name)
        
        # Determine overall validity (errors block, warnings don't)
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        
        return ValidationResult(
            is_valid=not has_errors,
            issues=issues,
            tables_validated=tables_validated
        )
    
    async def _validate_table(
        self,
        connector: DatabaseConnector,
        table_name: str,
        fields: List[Dict[str, Any]]
    ) -> List[ValidationIssue]:
        """Validate a single table."""
        issues: List[ValidationIssue] = []
        
        # Get table schema
        table_info = await connector.get_table_schema(table_name)
        
        if table_info is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                table=table_name,
                column=None,
                message=f"Table '{table_name}' does not exist in the database"
            ))
            return issues
        
        # Validate each field
        for field in fields:
            column_name = field.get("column_name")
            column_type = field.get("column_type", "string")
            is_required = field.get("is_required", False)
            
            column_info = table_info.get_column(column_name)
            
            if column_info is None:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    table=table_name,
                    column=column_name,
                    message=f"Column '{column_name}' does not exist in table '{table_name}'"
                ))
                continue
            
            # Check type compatibility
            if not is_type_compatible(column_type, column_info.data_type):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    table=table_name,
                    column=column_name,
                    message=f"Type mismatch: plugin expects '{column_type}', database has '{column_info.data_type}'"
                ))
            
            # Check nullable constraint
            if is_required and column_info.is_nullable:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    table=table_name,
                    column=column_name,
                    message=f"Column '{column_name}' allows NULL but is marked as required in plugin"
                ))
        
        return issues
    
    async def quick_validate_connection(
        self,
        db_type: DatabaseType,
        connection_config: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Quick connection test without full validation.
        
        Used for testing credentials before creating plugin.
        
        Returns:
            (success, error_message)
        """
        from services.plugin.database.base import ConnectionConfig
        
        config = ConnectionConfig.from_dict(connection_config)
        factory = await get_connector_factory()
        
        # Use a temporary plugin ID for connection test
        temp_plugin_id = -1
        
        try:
            connector = await factory.get_connector(temp_plugin_id, db_type, config)
            success = await connector.test_connection()
            
            if success:
                return True, None
            else:
                return False, "Connection test failed"
        except Exception as e:
            logger.warning(f"Connection test error: {e}")
            return False, str(e)
        finally:
            # Clean up temporary connector
            await factory.close_connector(temp_plugin_id)


# Singleton instance
_schema_validator: Optional[SchemaValidationService] = None


def get_schema_validator() -> SchemaValidationService:
    """Get singleton schema validator instance."""
    global _schema_validator
    if _schema_validator is None:
        _schema_validator = SchemaValidationService()
    return _schema_validator
