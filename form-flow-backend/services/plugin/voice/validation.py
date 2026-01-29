"""
Plugin Validation Engine Module

Applies plugin-defined validation rules to extracted values.
Features:
- Built-in validators (required, min/max, regex, etc.)
- Custom validation rules from plugin config
- Aggregated validation results
- Human-readable error messages

Zero redundancy:
- Single validation interface for all types
- Reusable validator registry
"""

import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationError:
    """A single validation error."""
    field_name: str
    rule: str
    message: str
    value: Any = None


@dataclass
class ValidationResult:
    """Result of validating all fields."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": [
                {"field": e.field_name, "rule": e.rule, "message": e.message}
                for e in self.errors
            ],
            "warnings": [
                {"field": w.field_name, "rule": w.rule, "message": w.message}
                for w in self.warnings
            ],
        }


class Validator(ABC):
    """Base validator interface."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Validator name for config."""
        pass
    
    @abstractmethod
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        """
        Validate a value.
        
        Returns ValidationError if invalid, None if valid.
        """
        pass


class RequiredValidator(Validator):
    """Validates that a value is not empty."""
    
    @property
    def name(self) -> str:
        return "required"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationError(
                field_name=field_name,
                rule="required",
                message=f"{field_name} is required",
                value=value
            )
        return None


class MinLengthValidator(Validator):
    """Validates minimum string length."""
    
    @property
    def name(self) -> str:
        return "min_length"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None:
            return None
        
        min_len = params.get("min_length", 0)
        if len(str(value)) < min_len:
            return ValidationError(
                field_name=field_name,
                rule="min_length",
                message=f"{field_name} must be at least {min_len} characters",
                value=value
            )
        return None


class MaxLengthValidator(Validator):
    """Validates maximum string length."""
    
    @property
    def name(self) -> str:
        return "max_length"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None:
            return None
        
        max_len = params.get("max_length", float("inf"))
        if len(str(value)) > max_len:
            return ValidationError(
                field_name=field_name,
                rule="max_length",
                message=f"{field_name} must be at most {max_len} characters",
                value=value
            )
        return None


class MinValueValidator(Validator):
    """Validates minimum numeric value."""
    
    @property
    def name(self) -> str:
        return "min_value"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None:
            return None
        
        try:
            num_value = float(value)
            min_val = params.get("min_value", float("-inf"))
            if num_value < min_val:
                return ValidationError(
                    field_name=field_name,
                    rule="min_value",
                    message=f"{field_name} must be at least {min_val}",
                    value=value
                )
        except (ValueError, TypeError):
            return ValidationError(
                field_name=field_name,
                rule="min_value",
                message=f"{field_name} must be a number",
                value=value
            )
        return None


class MaxValueValidator(Validator):
    """Validates maximum numeric value."""
    
    @property
    def name(self) -> str:
        return "max_value"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None:
            return None
        
        try:
            num_value = float(value)
            max_val = params.get("max_value", float("inf"))
            if num_value > max_val:
                return ValidationError(
                    field_name=field_name,
                    rule="max_value",
                    message=f"{field_name} must be at most {max_val}",
                    value=value
                )
        except (ValueError, TypeError):
            pass
        return None


class RegexValidator(Validator):
    """Validates against a regex pattern."""
    
    @property
    def name(self) -> str:
        return "regex"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None:
            return None
        
        pattern = params.get("pattern")
        if not pattern:
            return None
        
        if not re.match(pattern, str(value)):
            message = params.get("message", f"{field_name} has invalid format")
            return ValidationError(
                field_name=field_name,
                rule="regex",
                message=message,
                value=value
            )
        return None


class EmailValidator(Validator):
    """Validates email format."""
    
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    @property
    def name(self) -> str:
        return "email"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None or value == "":
            return None
        
        if not re.match(self.EMAIL_PATTERN, str(value)):
            return ValidationError(
                field_name=field_name,
                rule="email",
                message=f"{field_name} must be a valid email address",
                value=value
            )
        return None


class PhoneValidator(Validator):
    """Validates phone number format."""
    
    @property
    def name(self) -> str:
        return "phone"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None or value == "":
            return None
        
        # Allow + and 7-15 digits
        cleaned = re.sub(r'[^\d+]', '', str(value))
        if not re.match(r'^\+?\d{7,15}$', cleaned):
            return ValidationError(
                field_name=field_name,
                rule="phone",
                message=f"{field_name} must be a valid phone number",
                value=value
            )
        return None


class EnumValidator(Validator):
    """Validates value is in allowed list."""
    
    @property
    def name(self) -> str:
        return "enum"
    
    def validate(
        self,
        value: Any,
        field_name: str,
        params: Dict[str, Any]
    ) -> Optional[ValidationError]:
        if value is None:
            return None
        
        allowed = params.get("allowed_values", [])
        if not allowed:
            return None
        
        if str(value).lower() not in [str(v).lower() for v in allowed]:
            return ValidationError(
                field_name=field_name,
                rule="enum",
                message=f"{field_name} must be one of: {', '.join(map(str, allowed))}",
                value=value
            )
        return None


class ValidationEngine:
    """
    Plugin validation engine.
    
    Manages validators and applies rules to extracted values.
    
    Usage:
        engine = ValidationEngine()
        result = engine.validate_all(extracted_values, field_configs)
    """
    
    def __init__(self):
        """Initialize with built-in validators."""
        self._validators: Dict[str, Validator] = {}
        self._register_builtins()
    
    def _register_builtins(self) -> None:
        """Register built-in validators."""
        builtins = [
            RequiredValidator(),
            MinLengthValidator(),
            MaxLengthValidator(),
            MinValueValidator(),
            MaxValueValidator(),
            RegexValidator(),
            EmailValidator(),
            PhoneValidator(),
            EnumValidator(),
        ]
        for v in builtins:
            self._validators[v.name] = v
    
    def register_validator(self, validator: Validator) -> None:
        """Register a custom validator."""
        self._validators[validator.name] = validator
    
    def validate_field(
        self,
        field_name: str,
        value: Any,
        field_config: Dict[str, Any]
    ) -> List[ValidationError]:
        """
        Validate a single field.
        
        Args:
            field_name: Field name
            value: Value to validate
            field_config: Field configuration with validation rules
            
        Returns:
            List of ValidationErrors (empty if valid)
        """
        errors = []
        
        # Check required
        if field_config.get("is_required"):
            result = self._validators["required"].validate(value, field_name, {})
            if result:
                errors.append(result)
                return errors  # No point checking other rules if empty
        
        # Get validation rules from config
        validation_rules = field_config.get("validation_rules", {})
        
        # Apply type-based validators
        column_type = field_config.get("column_type", "string")
        if column_type == "email":
            result = self._validators["email"].validate(value, field_name, {})
            if result:
                errors.append(result)
        elif column_type == "phone":
            result = self._validators["phone"].validate(value, field_name, {})
            if result:
                errors.append(result)
        
        # Apply explicit rules
        for rule_name, rule_params in validation_rules.items():
            if rule_name in self._validators:
                params = rule_params if isinstance(rule_params, dict) else {rule_name: rule_params}
                result = self._validators[rule_name].validate(value, field_name, params)
                if result:
                    errors.append(result)
        
        return errors
    
    def validate_all(
        self,
        extracted_values: Dict[str, Any],
        field_configs: List[Dict[str, Any]]
    ) -> ValidationResult:
        """
        Validate all extracted values against field configs.
        
        Args:
            extracted_values: Dict of field_name -> value
            field_configs: List of field configurations
            
        Returns:
            ValidationResult with all errors
        """
        all_errors = []
        
        for field_config in field_configs:
            field_name = field_config.get("column_name", "")
            value = extracted_values.get(field_name)
            
            errors = self.validate_field(field_name, value, field_config)
            all_errors.extend(errors)
        
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors
        )


# Singleton instance
_validation_engine: Optional[ValidationEngine] = None


def get_validation_engine() -> ValidationEngine:
    """Get singleton validation engine."""
    global _validation_engine
    if _validation_engine is None:
        _validation_engine = ValidationEngine()
    return _validation_engine
