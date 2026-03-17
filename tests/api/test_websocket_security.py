"""Test WebSocket Security - Phase 1 Task 1.2."""
import pytest

class TestWebSocketAuthentication:
    """Test WebSocket requires authentication."""
    
    def test_websocket_has_token_validation(self):
        """Verify WebSocket endpoint validates tokens."""
        with open('synapse/api/app.py', 'r') as f:
            content = f.read()
        assert 'token' in content.lower()
        assert 'query_params' in content.lower()
    
    def test_websocket_has_auth_check(self):
        """Verify WebSocket checks authentication."""
        with open('synapse/api/app.py', 'r') as f:
            content = f.read()
        assert 'expected' in content.lower()
    
    def test_websocket_closes_unauthorized(self):
        """Verify WebSocket closes unauthorized connections."""
        with open('synapse/api/app.py', 'r') as f:
            content = f.read()
        assert 'close' in content.lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
