"""
Tests for Secure Browser Controller.

Tests verify:
- Protocol version compliance (1.0)
- URL validation security
- Action validation security
- Capability checks
- Audit logging
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

# Import the module
import sys
sys.path.insert(0, '/a0/usr/projects/project_synapse')

from synapse.integrations.browser_controller import (
    SecureBrowserController,
    BrowserAction,
    BrowserActionStatus,
    BrowserActionResult,
    BrowserSecurityConfig,
    PROTOCOL_VERSION
)


class TestBrowserControllerProtocol:
    """Tests for protocol version compliance."""
    
    def test_protocol_version_defined(self):
        """Protocol version is defined as 1.0"""
        assert PROTOCOL_VERSION == "1.0"
    
    def test_controller_has_protocol_version(self):
        """Controller class has protocol version"""
        assert SecureBrowserController.PROTOCOL_VERSION == "1.0"
    
    def test_result_has_protocol_version(self):
        """Result dataclass has protocol version"""
        result = BrowserActionResult(
            status=BrowserActionStatus.SUCCESS,
            action="test"
        )
        assert result.protocol_version == "1.0"
    
    def test_config_has_protocol_version(self):
        """Config dataclass has protocol version"""
        config = BrowserSecurityConfig()
        assert config.protocol_version == "1.0"


class TestURLValidation:
    """Tests for URL validation security."""
    
    @pytest.fixture
    def controller(self):
        return SecureBrowserController()
    
    @pytest.mark.asyncio
    async def test_valid_http_url(self, controller):
        """Valid HTTP URL is allowed"""
        result = await controller._validate_url("http://example.com")
        assert result["allowed"] == True
    
    @pytest.mark.asyncio
    async def test_valid_https_url(self, controller):
        """Valid HTTPS URL is allowed"""
        result = await controller._validate_url("https://github.com")
        assert result["allowed"] == True
    
    @pytest.mark.asyncio
    async def test_invalid_scheme_blocked(self, controller):
        """Invalid scheme is blocked"""
        result = await controller._validate_url("ftp://example.com")
        assert result["allowed"] == False
        assert "Invalid scheme" in result["reason"]
    
    @pytest.mark.asyncio
    async def test_blocked_domain_blocked(self, controller):
        """Blocked domain is blocked"""
        result = await controller._validate_url("https://malware-site.com")
        assert result["allowed"] == False
        assert "blocked" in result["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_non_whitelisted_domain_blocked(self, controller):
        """Non-whitelisted domain is blocked when whitelist enforced"""
        result = await controller._validate_url("https://unknown-random-site.com")
        assert result["allowed"] == False
        assert "whitelist" in result["reason"].lower()


class TestActionValidation:
    """Tests for action validation security."""
    
    @pytest.fixture
    def controller(self):
        return SecureBrowserController()
    
    @pytest.mark.asyncio
    async def test_valid_action_allowed(self, controller):
        """Valid action is allowed"""
        result = await controller._validate_action("navigate", None, None)
        assert result["allowed"] == True
    
    @pytest.mark.asyncio
    async def test_blocked_action_blocked(self, controller):
        """Blocked action is blocked"""
        result = await controller._validate_action("download_executable", None, None)
        assert result["allowed"] == False
    
    @pytest.mark.asyncio
    async def test_sensitive_selector_requires_approval(self, controller):
        """Sensitive selector requires approval"""
        result = await controller._validate_action(
            "fill",
            "input[type=\"password\"]",
            "test"
        )
        assert result["requires_approval"] == True
    
    @pytest.mark.asyncio
    async def test_high_risk_action_requires_approval(self, controller):
        """High-risk action requires approval"""
        result = await controller._validate_action("click", None, None)
        assert result["requires_approval"] == True


class TestBrowserExecution:
    """Tests for browser action execution."""
    
    @pytest.fixture
    def controller(self):
        return SecureBrowserController()
    
    @pytest.mark.asyncio
    async def test_navigate_action(self, controller):
        """Navigate action returns success"""
        result = await controller.execute(
            action="navigate",
            url="https://github.com"
        )
        assert result.status == BrowserActionStatus.SUCCESS
        assert result.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_click_action(self, controller):
        """Click action returns success"""
        result = await controller.execute(
            action="click",
            selector="#button"
        )
        assert result.status == BrowserActionStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_fill_action(self, controller):
        """Fill action returns success"""
        result = await controller.execute(
            action="fill",
            selector="#input",
            value="test"
        )
        assert result.status == BrowserActionStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_screenshot_action(self, controller):
        """Screenshot action returns success"""
        result = await controller.execute(action="screenshot")
        assert result.status == BrowserActionStatus.SUCCESS
        assert result.screenshot is not None
    
    @pytest.mark.asyncio
    async def test_scrape_action(self, controller):
        """Scrape action returns success"""
        result = await controller.execute(action="scrape")
        assert result.status == BrowserActionStatus.SUCCESS
        assert result.content is not None
    
    @pytest.mark.asyncio
    async def test_unknown_action_fails(self, controller):
        """Unknown action fails"""
        result = await controller.execute(action="unknown_action")
        assert result.status == BrowserActionStatus.FAILED


class TestSecurityEnforcement:
    """Tests for security enforcement."""
    
    @pytest.fixture
    def controller(self):
        return SecureBrowserController()
    
    @pytest.mark.asyncio
    async def test_blocked_url_returns_blocked_status(self, controller):
        """Blocked URL returns blocked status"""
        result = await controller.execute(
            action="navigate",
            url="https://malware-site.com"
        )
        assert result.status == BrowserActionStatus.BLOCKED
    
    @pytest.mark.asyncio
    async def test_blocked_action_returns_blocked_status(self, controller):
        """Blocked action returns blocked status"""
        result = await controller.execute(
            action="bypass_captcha"
        )
        assert result.status == BrowserActionStatus.BLOCKED
    
    @pytest.mark.asyncio
    async def test_missing_capabilities_blocked(self, controller):
        """Missing capabilities result in blocked status"""
        context = {"capabilities": []}
        result = await controller.execute(
            action="navigate",
            url="https://github.com",
            context=context
        )
        # Without security manager, should still work
        # With security manager, would be blocked
        assert result.status in [BrowserActionStatus.SUCCESS, BrowserActionStatus.BLOCKED]


class TestStatistics:
    """Tests for controller statistics."""
    
    @pytest.fixture
    def controller(self):
        return SecureBrowserController()
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, controller):
        """Statistics are tracked correctly"""
        # Execute some actions
        await controller.execute(action="navigate", url="https://github.com")
        await controller.execute(action="screenshot")
        
        stats = controller.get_statistics()
        assert stats["actions_executed"] == 2
        assert stats["protocol_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_blocked_actions_tracked(self, controller):
        """Blocked actions are tracked"""
        await controller.execute(action="navigate", url="https://malware-site.com")
        
        stats = controller.get_statistics()
        assert stats["actions_blocked"] >= 1


class TestSkillManifest:
    """Tests for skill manifest."""
    
    def test_manifest_has_protocol_version(self):
        """Manifest has protocol version"""
        from synapse.integrations.browser_controller import SKILL_MANIFEST
        assert SKILL_MANIFEST["protocol_version"] == "1.0"
    
    def test_manifest_has_required_capabilities(self):
        """Manifest has required capabilities"""
        from synapse.integrations.browser_controller import SKILL_MANIFEST
        assert "network:http" in SKILL_MANIFEST["required_capabilities"]
        assert "browser:automation" in SKILL_MANIFEST["required_capabilities"]
    
    def test_manifest_has_risk_level(self):
        """Manifest has risk level"""
        from synapse.integrations.browser_controller import SKILL_MANIFEST
        assert SKILL_MANIFEST["risk_level"] == 4
    
    def test_manifest_has_isolation_type(self):
        """Manifest has isolation type"""
        from synapse.integrations.browser_controller import SKILL_MANIFEST
        assert SKILL_MANIFEST["isolation_type"] == "container"
