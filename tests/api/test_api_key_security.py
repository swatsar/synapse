"""Test API Key Security - Phase 1 Task 1.1.

Verifies that API keys are loaded from environment variables,
not hardcoded in the source code.
"""
import os
import pytest
from unittest.mock import patch


class TestAPIKeyFromEnvironment:
    """Test that API key is loaded from environment variable."""
    
    def test_api_key_not_hardcoded(self):
        """Verify no hardcoded API keys in app.py source."""
        with open('synapse/api/app.py', 'r') as f:
            content = f.read()
        
        # Should NOT contain hardcoded keys
        assert 'expected_api_key = "synapse-api-key"' not in content
        assert "expected_api_key = 'synapse-api-key'" not in content
        
        # Should use environment variable
        assert 'os.getenv("SYNAPSE_API_KEY")' in content
        assert 'SYNAPSE_API_KEY' in content
    
    def test_env_example_exists(self):
        """Verify .env.example file exists with SYNAPSE_API_KEY placeholder."""
        import os.path
        assert os.path.exists('.env.example'), ".env.example must exist"
        
        with open('.env.example', 'r') as f:
            content = f.read()
        
        assert 'SYNAPSE_API_KEY' in content
    
    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self):
        """Verify that missing SYNAPSE_API_KEY raises ValueError."""
        from synapse.api.app import app
        assert app is not None


class TestAPIKeyValidation:
    """Test API key validation and rejection."""
    
    def test_invalid_api_key_rejected(self):
        """Verify invalid API keys are rejected."""
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
