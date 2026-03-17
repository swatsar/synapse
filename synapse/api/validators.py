"""Input Validation Layer for Synapse API.

Provides Pydantic models with built-in protection against:
- SQL Injection
- Cross-Site Scripting (XSS)
- Command Injection
- Path Traversal
- Other OWASP Top 10 vulnerabilities
"""
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# SQL Injection patterns
SQL_INJECTION_PATTERNS = [
    r"(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+",
    r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)",
    r"--\s*$",
    r"\bUNION\b.*\bSELECT\b",
    r"\bSELECT\b.*\bFROM\b",
]

# XSS patterns
XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
]

# Command injection patterns
CMD_INJECTION_PATTERNS = [
    r"[;&|]",
    r"\$\(.*\)",
    r"`.*`",
    r"\|\|",
    r"&&",
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.\\",
    r"%2e%2e%2f",
]


class ValidationError(Exception):
    """Custom validation error."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class InputValidator:
    """Static validation methods for input sanitization."""

    @staticmethod
    def check_sql_injection(value: str, field_name: str = "input") -> None:
        """Check for SQL injection patterns."""
        if not value:
            return
        value_lower = value.lower()
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError(field_name, f"Potential SQL injection detected in {field_name}")

    @staticmethod
    def check_xss(value: str, field_name: str = "input") -> None:
        """Check for XSS patterns."""
        if not value:
            return
        value_lower = value.lower()
        for pattern in XSS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError(field_name, f"Potential XSS attack detected in {field_name}")

    @staticmethod
    def check_command_injection(value: str, field_name: str = "input") -> None:
        """Check for command injection patterns."""
        if not value:
            return
        for pattern in CMD_INJECTION_PATTERNS:
            if re.search(pattern, value):
                raise ValidationError(field_name, f"Potential command injection detected in {field_name}")

    @staticmethod
    def check_path_traversal(value: str, field_name: str = "input") -> None:
        """Check for path traversal patterns."""
        if not value:
            return
        value_lower = value.lower()
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError(field_name, f"Potential path traversal detected in {field_name}")

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """Validate API key format."""
        if not api_key:
            return False
        if not re.match(r'^sk_(test|live)_[a-zA-Z0-9]+$', api_key):
            return False
        if len(api_key) < 20:
            return False
        return True


class ApprovalRequest(BaseModel):
    """Request model for approval actions with input validation."""

    action: str = Field(..., min_length=1, max_length=256)
    risk_level: int = Field(..., ge=1, le=5)
    details: Optional[Dict[str, Any]] = Field(default=None)
    reason: Optional[str] = Field(default=None, max_length=1024)

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action field for injection attacks."""
        InputValidator.check_sql_injection(v, "action")
        InputValidator.check_xss(v, "action")
        InputValidator.check_command_injection(v, "action")
        return v

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        """Validate reason field for injection attacks."""
        if v:
            InputValidator.check_sql_injection(v, "reason")
            InputValidator.check_xss(v, "reason")
            InputValidator.check_command_injection(v, "reason")
        return v

    @field_validator('details')
    @classmethod
    def validate_details(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate details field for injection attacks."""
        if v:
            for key, value in v.items():
                if isinstance(value, str):
                    InputValidator.check_sql_injection(value, f"details.{key}")
                    InputValidator.check_xss(value, f"details.{key}")
                    InputValidator.check_command_injection(value, f"details.{key}")
        return v

    @model_validator(mode='after')
    def validate_risk_level(self):
        """Validate risk level is appropriate."""
        if self.risk_level < 1 or self.risk_level > 5:
            raise ValidationError("risk_level", "Must be between 1 and 5")
        return self


class APIKeyRequest(BaseModel):
    """Request model for API key operations."""

    api_key: str = Field(..., min_length=20, max_length=256)

    @field_validator('api_key')
    @classmethod
    def validate_api_key_format(cls, v: str) -> str:
        """Validate API key format and check for injection."""
        if not InputValidator.validate_api_key(v):
            raise ValidationError("api_key", "Invalid API key format")
        InputValidator.check_sql_injection(v, "api_key")
        InputValidator.check_xss(v, "api_key")
        InputValidator.check_command_injection(v, "api_key")
        return v


class FileRequest(BaseModel):
    """Request model for file operations with path validation."""

    path: str = Field(..., min_length=1, max_length=1024)

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate file path for traversal attacks."""
        InputValidator.check_path_traversal(v, "path")
        InputValidator.check_command_injection(v, "path")
        if not v.startswith('/workspace/'):
            raise ValidationError("path", "Path must start with /workspace/")
        return v


class SearchRequest(BaseModel):
    """Request model for search operations."""

    query: str = Field(..., min_length=1, max_length=512)
    limit: int = Field(default=10, ge=1, le=100)

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate search query for injection attacks."""
        InputValidator.check_sql_injection(v, "query")
        InputValidator.check_xss(v, "query")
        InputValidator.check_command_injection(v, "query")
        return v


class MessageRequest(BaseModel):
    """Request model for message operations."""

    content: str = Field(..., min_length=1, max_length=10000)
    recipient: Optional[str] = Field(default=None, max_length=256)

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate message content for injection attacks."""
        InputValidator.check_sql_injection(v, "content")
        InputValidator.check_xss(v, "content")
        InputValidator.check_command_injection(v, "content")
        return v

    @field_validator('recipient')
    @classmethod
    def validate_recipient(cls, v: Optional[str]) -> Optional[str]:
        """Validate recipient for injection attacks."""
        if v:
            InputValidator.check_sql_injection(v, "recipient")
            InputValidator.check_xss(v, "recipient")
        return v


__all__ = [
    'InputValidator',
    'ValidationError',
    'ApprovalRequest',
    'APIKeyRequest',
    'FileRequest',
    'SearchRequest',
    'MessageRequest',
]
