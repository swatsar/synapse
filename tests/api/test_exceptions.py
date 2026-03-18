"""Test Phase 2 Exception Hierarchy."""
import pytest
from synapse.core.exceptions import (
    SynapseError,
    ErrorCode,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    NotFoundError,
    SecurityViolationError,
    RateLimitError,
    ResourceExhaustedError,
    TimeoutError,
    ConflictError,
    BadRequestError,
)


class TestSynapseError:
    """Test base SynapseError."""

    def test_base_error_creation(self):
        """Test creating base error."""
        error = SynapseError(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
        )
        assert error.message == "Test error"
        assert error.status_code == 500

    def test_error_to_dict(self):
        """Test error serialization."""
        error = SynapseError(
            message="Test",
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            details={"key": "value"},
        )
        data = error.to_dict()
        assert data["error"] == "INTERNAL_ERROR"
        assert data["message"] == "Test"
        assert data["status_code"] == 500
        assert data["details"]["key"] == "value"
        assert data["protocol_version"] == "1.0"


class TestAuthenticationError:
    """Test AuthenticationError."""

    def test_auth_error_defaults(self):
        error = AuthenticationError()
        assert error.status_code == 401
        assert error.error_code == ErrorCode.UNAUTHORIZED

    def test_auth_error_custom_message(self):
        error = AuthenticationError(message="Invalid credentials")
        assert error.message == "Invalid credentials"
        assert error.status_code == 401


class TestAuthorizationError:
    """Test AuthorizationError."""

    def test_authz_error_creation(self):
        error = AuthorizationError("fs:read:/workspace/**")
        assert error.status_code == 403
        assert error.error_code == ErrorCode.CAPABILITY_DENIED
        assert "fs:read:/workspace/**" in error.message


class TestValidationError:
    """Test ValidationError."""

    def test_validation_error_creation(self):
        error = ValidationError("action", "too long")
        assert error.status_code == 422
        assert error.error_code == ErrorCode.VALIDATION_ERROR
        assert "action" in error.message
        assert "too long" in error.message


class TestNotFoundError:
    """Test NotFoundError."""

    def test_not_found_error_creation(self):
        error = NotFoundError("Agent", "agent_123")
        assert error.status_code == 404
        assert error.error_code == ErrorCode.NOT_FOUND
        assert "Agent" in error.message
        assert "agent_123" in error.message


class TestSecurityViolationError:
    """Test SecurityViolationError."""

    def test_security_error_creation(self):
        error = SecurityViolationError("SQL injection attempt")
        assert error.status_code == 403
        assert error.error_code == ErrorCode.SECURITY_VIOLATION
        assert "SQL injection" in error.message


class TestRateLimitError:
    """Test RateLimitError."""

    def test_rate_limit_error_creation(self):
        error = RateLimitError(limit=60, retry_after=60)
        assert error.status_code == 429
        assert error.error_code == ErrorCode.RATE_LIMITED
        assert "60" in error.message


class TestResourceExhaustedError:
    """Test ResourceExhaustedError."""

    def test_resource_error_creation(self):
        error = ResourceExhaustedError("database_connections")
        assert error.status_code == 503
        assert error.error_code == ErrorCode.RESOURCE_EXHAUSTED


class TestTimeoutError:
    """Test TimeoutError."""

    def test_timeout_error_creation(self):
        error = TimeoutError("database_query", 5000)
        assert error.status_code == 504
        assert error.error_code == ErrorCode.TIMEOUT
        assert "database_query" in error.message
        assert "5000" in error.message


class TestConflictError:
    """Test ConflictError."""

    def test_conflict_error_creation(self):
        error = ConflictError("Resource already exists")
        assert error.status_code == 409
        assert error.error_code == ErrorCode.CONFLICT


class TestBadRequestError:
    """Test BadRequestError."""

    def test_bad_request_error_creation(self):
        error = BadRequestError("Invalid JSON")
        assert error.status_code == 400
        assert error.error_code == ErrorCode.BAD_REQUEST


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
