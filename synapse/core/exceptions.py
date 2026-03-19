"""Custom exception hierarchy for Synapse platform.

Protocol Version: 1.0
Specification: 3.1
"""

PROTOCOL_VERSION: str = "1.0"
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """Standard error codes for API responses."""
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    RATE_LIMITED = "RATE_LIMITED"
    CONFLICT = "CONFLICT"
    BAD_REQUEST = "BAD_REQUEST"


class SynapseError(Exception):
    """Base exception for Synapse platform."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        caused_by: Optional[Exception] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.caused_by = caused_by
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "error": self.error_code.value,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
            "protocol_version": "1.0"
        }


class AuthenticationError(SynapseError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.UNAUTHORIZED,
            status_code=401,
            details=details
        )


class AuthorizationError(SynapseError):
    """Raised when authorization fails."""

    def __init__(self, capability: str, details: Optional[Dict] = None):
        d = {"required_capability": capability}
        if details:
            d.update(details)
        super().__init__(
            message=f"Access denied: capability '{capability}' required",
            error_code=ErrorCode.CAPABILITY_DENIED,
            status_code=403,
            details=d
        )


class ValidationError(SynapseError):
    """Raised when input validation fails."""

    def __init__(self, field: str, reason: str, details: Optional[Dict] = None):
        d = {"field": field, "reason": reason}
        if details:
            d.update(details)
        super().__init__(
            message=f"Validation failed for '{field}': {reason}",
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
            details=d
        )


class NotFoundError(SynapseError):
    """Raised when a resource is not found."""

    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict] = None):
        d = {"resource_type": resource_type, "resource_id": resource_id}
        if details:
            d.update(details)
        super().__init__(
            message=f"{resource_type} '{resource_id}' not found",
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            details=d
        )


class SecurityViolationError(SynapseError):
    """Raised when a security violation is detected."""

    def __init__(self, violation: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"Security violation: {violation}",
            error_code=ErrorCode.SECURITY_VIOLATION,
            status_code=403,
            details=details
        )


class RateLimitError(SynapseError):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit: int, retry_after: int = 60, details: Optional[Dict] = None):
        d = {"limit": limit, "retry_after_seconds": retry_after}
        if details:
            d.update(details)
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per minute",
            error_code=ErrorCode.RATE_LIMITED,
            status_code=429,
            details=d
        )


class ResourceExhaustedError(SynapseError):
    """Raised when system resources are exhausted."""

    def __init__(self, resource: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"Resource exhausted: {resource}",
            error_code=ErrorCode.RESOURCE_EXHAUSTED,
            status_code=503,
            details=details or {"resource": resource}
        )


class TimeoutError(SynapseError):
    """Raised when an operation times out."""

    def __init__(self, operation: str, timeout_ms: int, details: Optional[Dict] = None):
        super().__init__(
            message=f"Operation '{operation}' timed out after {timeout_ms}ms",
            error_code=ErrorCode.TIMEOUT,
            status_code=504,
            details=details or {"operation": operation, "timeout_ms": timeout_ms}
        )


class ConflictError(SynapseError):
    """Raised when there's a conflict."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONFLICT,
            status_code=409,
            details=details
        )


class BadRequestError(SynapseError):
    """Raised when request is malformed."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            details=details
        )


from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


async def synapse_error_handler(request: Request, exc: SynapseError) -> JSONResponse:
    """Handle SynapseError exceptions."""
    logger.error(f"SynapseError: {exc.error_code.value} - {exc.message}")
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    error = SynapseError(message="Internal server error", error_code=ErrorCode.INTERNAL_ERROR, status_code=500)
    return JSONResponse(status_code=error.status_code, content=error.to_dict())


__all__ = [
    "ErrorCode", "SynapseError", "AuthenticationError", "AuthorizationError",
    "ValidationError", "NotFoundError", "SecurityViolationError", "RateLimitError",
    "ResourceExhaustedError", "TimeoutError", "ConflictError", "BadRequestError",
    "synapse_error_handler", "generic_error_handler"
]