"""Input Validation Tests for Synapse API.

Tests for Phase 4: Input Validation Layer
Protects against OWASP Top 10 vulnerabilities.
"""
import pytest
from synapse.api.validators import (
    InputValidator,
    ValidationError,
    ApprovalRequest,
    FileRequest,
    SearchRequest,
    MessageRequest,
)


class TestInputValidator:
    """Test InputValidator static methods."""

    def test_sql_injection_union_select(self):
        """Test SQL injection with UNION SELECT."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.check_sql_injection("1 UNION SELECT * FROM users")
        assert "SQL injection" in str(exc_info.value.message)

    def test_sql_injection_drop_table(self):
        """Test SQL injection with DROP TABLE."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.check_sql_injection("; DROP TABLE users--")
        assert "SQL injection" in str(exc_info.value.message)

    def test_xss_script_tag(self):
        """Test XSS with script tag."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.check_xss("<script>alert('XSS')</script>")
        assert "XSS" in str(exc_info.value.message)

    def test_xss_javascript_protocol(self):
        """Test XSS with javascript protocol."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.check_xss("javascript:alert(document.cookie)")
        assert "XSS" in str(exc_info.value.message)

    def test_command_injection_semicolon(self):
        """Test command injection with semicolon."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.check_command_injection("test; rm -rf /")
        assert "command injection" in str(exc_info.value.message)

    def test_path_traversal_basic(self):
        """Test path traversal with ../."""
        with pytest.raises(ValidationError) as exc_info:
            InputValidator.check_path_traversal("../../../etc/passwd")
        assert "path traversal" in str(exc_info.value.message)

    def test_valid_api_key(self):
        """Test valid API key format."""
        assert InputValidator.validate_api_key("sk_test_abc123def456ghi789jkl") is True
        assert InputValidator.validate_api_key("sk_live_abc123def456ghi789jkl") is True

    def test_invalid_api_key_wrong_prefix(self):
        """Test invalid API key with wrong prefix."""
        assert InputValidator.validate_api_key("test_abc123def456ghi789jkl") is False

    def test_no_false_positives(self):
        """Test that normal text doesn't trigger false positives."""
        normal_text = "Hello, this is a normal message!"
        InputValidator.check_sql_injection(normal_text)
        InputValidator.check_xss(normal_text)
        InputValidator.check_command_injection(normal_text)
        InputValidator.check_path_traversal(normal_text)


class TestApprovalRequest:
    """Test ApprovalRequest model validation."""

    def test_valid_approval_request(self):
        """Test valid approval request."""
        request = ApprovalRequest(
            action="deploy_to_production",
            risk_level=3,
            details={"environment": "prod"},
            reason="Scheduled deployment"
        )
        assert request.action == "deploy_to_production"
        assert request.risk_level == 3

    def test_approval_request_xss(self):
        """Test XSS blocked in reason field."""
        with pytest.raises(ValidationError):
            ApprovalRequest(
                action="test",
                risk_level=1,
                reason="<script>alert('XSS')</script>"
            )

    def test_approval_request_command_injection(self):
        """Test command injection blocked in action field."""
        with pytest.raises(ValidationError):
            ApprovalRequest(
                action="test; rm -rf /",
                risk_level=1
            )


class TestFileRequest:
    """Test FileRequest model validation."""

    def test_valid_file_request(self):
        """Test valid file request."""
        request = FileRequest(path="/workspace/project/file.txt")
        assert request.path == "/workspace/project/file.txt"

    def test_file_request_path_traversal(self):
        """Test path traversal blocked in file request."""
        with pytest.raises(ValidationError):
            FileRequest(path="/workspace/../../../etc/passwd")


class TestSearchRequest:
    """Test SearchRequest model validation."""

    def test_valid_search_request(self):
        """Test valid search request."""
        request = SearchRequest(query="python programming", limit=20)
        assert request.query == "python programming"
        assert request.limit == 20

    def test_search_request_union_select(self):
        """Test UNION SELECT blocked in search query."""
        with pytest.raises(ValidationError):
            SearchRequest(query="1 UNION SELECT * FROM users")

    def test_search_request_xss(self):
        """Test XSS blocked in search query."""
        with pytest.raises(ValidationError):
            SearchRequest(query="<script>alert(1)</script>")


class TestMessageRequest:
    """Test MessageRequest model validation."""

    def test_valid_message_request(self):
        """Test valid message request."""
        request = MessageRequest(
            content="Hello, this is a test message!",
            recipient="user@example.com"
        )
        assert request.content == "Hello, this is a test message!"

    def test_message_content_drop_table(self):
        """Test DROP TABLE blocked in message content."""
        with pytest.raises(ValidationError):
            MessageRequest(content="test; DROP TABLE users--")

    def test_message_content_xss(self):
        """Test XSS blocked in message content."""
        with pytest.raises(ValidationError):
            MessageRequest(content="<script>alert('XSS')</script>")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
