"""Tests for web server."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestWebServer:
    """Test web server."""

    @pytest.fixture
    def web_server(self):
        """Create a web server for testing."""
        from synapse.ui.web.server import WebServer, WebServerConfig

        config = WebServerConfig(host="localhost", port=8080)
        return WebServer(config=config)

    def test_web_server_creation(self, web_server):
        """Test web server creation."""
        assert web_server is not None

    def test_protocol_version(self, web_server):
        """Test protocol version."""
        assert web_server.protocol_version == "1.0"

    def test_start_stop(self, web_server):
        """Test start and stop."""
        web_server.start()
        assert web_server.is_running() == True
        web_server.stop()
        assert web_server.is_running() == False

    def test_get_status(self, web_server):
        """Test get status."""
        status = web_server.get_status()
        assert "running" in status
        assert "host" in status
        assert "port" in status
        assert "protocol_version" in status
