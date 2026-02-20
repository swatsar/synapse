"""
Secure Browser Controller for Synapse.

Adapted from browser-use patterns:
https://github.com/browser-use/browser-use

Original License: MIT
Adaptation: Added capability-based access, domain whitelist,
           checkpoint integration, audit logging, protocol versioning

Copyright (c) 2024 browser-use Contributors
Copyright (c) 2026 Synapse Contributors
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio
import hashlib
import json
import re
from urllib.parse import urlparse

# Protocol versioning
PROTOCOL_VERSION: str = "1.0"


class BrowserAction(str, Enum):
    """Supported browser actions"""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SCREENSHOT = "screenshot"
    SCRAPE = "scrape"
    EVALUATE = "evaluate"
    WAIT = "wait"
    SCROLL = "scroll"


class BrowserActionStatus(str, Enum):
    """Status of browser action"""
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


@dataclass
class BrowserActionResult:
    """Result of a browser action"""
    status: BrowserActionStatus
    action: str
    url: Optional[str] = None
    content: Optional[str] = None
    screenshot: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class BrowserSecurityConfig:
    """Security configuration for browser controller"""
    allowed_domains: List[str] = field(default_factory=lambda: [
        'localhost',
        '127.0.0.1',
        'example.com',
        'github.com',
        'pypi.org',
        'docs.python.org'
    ])
    blocked_domains: List[str] = field(default_factory=lambda: [
        'malware',
        'phishing',
        'hack',
        'exploit'
    ])
    blocked_actions: List[str] = field(default_factory=lambda: [
        'download_executable',
        'upload_sensitive',
        'bypass_captcha',
        'automate_login',
        'access_dark_web'
    ])
    enforce_domain_whitelist: bool = True
    allow_localhost: bool = True
    human_approval_required: bool = True
    protocol_version: str = PROTOCOL_VERSION


class SecureBrowserController:
    """
    Secure Browser Controller with capability-based access control.
    
    Adapted from browser-use patterns with Synapse security enhancements.
    
    Features:
    - Domain whitelist/blacklist enforcement
    - Action validation and blocking
    - Human approval for high-risk operations
    - Audit logging for all actions
    - Protocol versioning compliance
    """
    
    PROTOCOL_VERSION: str = PROTOCOL_VERSION
    
    # Risk level for this skill
    RISK_LEVEL: int = 4  # High risk - web access
    
    # Required capabilities
    REQUIRED_CAPABILITIES: List[str] = [
        "network:http",
        "browser:automation"
    ]
    
    # Isolation type
    ISOLATION_TYPE: str = "container"
    
    # Timeout for browser operations
    DEFAULT_TIMEOUT: int = 30000  # 30 seconds
    
    def __init__(
        self,
        security_manager: Any = None,
        audit_logger: Any = None,
        config: Optional[BrowserSecurityConfig] = None
    ):
        """
        Initialize the browser controller.
        
        Args:
            security_manager: Security manager for capability checks
            audit_logger: Audit logger for action logging
            config: Security configuration
        """
        self.security = security_manager
        self.audit = audit_logger
        self.config = config or BrowserSecurityConfig()
        
        # Browser state
        self._browser = None
        self._context = None
        self._page = None
        self._initialized = False
        
        # Statistics
        self._actions_executed: int = 0
        self._actions_blocked: int = 0
    
    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        value: Optional[str] = None,
        timeout: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> BrowserActionResult:
        """
        Execute a browser action with security checks.
        
        Args:
            action: Browser action to execute
            url: URL for navigation
            selector: CSS selector for element operations
            value: Value for fill operations
            timeout: Operation timeout in milliseconds
            context: Execution context with capabilities
            
        Returns:
            BrowserActionResult with status and data
        """
        action_start = datetime.now(timezone.utc)
        
        # 1. Check for blocked actions FIRST (before enum validation)
        for blocked in self.config.blocked_actions:
            if blocked.lower() in action.lower():
                await self._audit_action(
                    action=action,
                    status=BrowserActionStatus.BLOCKED,
                    reason=f"Blocked action: {blocked}",
                    context=context
                )
                self._actions_blocked += 1
                return BrowserActionResult(
                    status=BrowserActionStatus.BLOCKED,
                    action=action,
                    error=f"Action blocked: {blocked}"
                )
        
        # 2. Validate action type
        try:
            action_enum = BrowserAction(action.lower())
        except ValueError:
            return BrowserActionResult(
                status=BrowserActionStatus.FAILED,
                action=action,
                error=f"Unknown action: {action}"
            )
        
        # 3. Check capabilities if security manager available
        if self.security and context:
            cap_result = await self._check_capabilities(context)
            if not cap_result.get("approved", False):
                await self._audit_action(
                    action=action,
                    status=BrowserActionStatus.BLOCKED,
                    reason="Missing capabilities",
                    context=context
                )
                self._actions_blocked += 1
                return BrowserActionResult(
                    status=BrowserActionStatus.BLOCKED,
                    action=action,
                    error="Missing required capabilities"
                )
        
        # 4. Validate URL if provided
        if url:
            url_validation = await self._validate_url(url)
            if not url_validation["allowed"]:
                await self._audit_action(
                    action=action,
                    status=BrowserActionStatus.BLOCKED,
                    reason=url_validation["reason"],
                    url=url,
                    context=context
                )
                self._actions_blocked += 1
                return BrowserActionResult(
                    status=BrowserActionStatus.BLOCKED,
                    action=action,
                    url=url,
                    error=f"URL blocked: {url_validation['reason']}"
                )
        
        # 5. Validate action for security
        action_validation = await self._validate_action(action, selector, value)
        if not action_validation["allowed"]:
            await self._audit_action(
                action=action,
                status=BrowserActionStatus.BLOCKED,
                reason=action_validation["reason"],
                context=context
            )
            self._actions_blocked += 1
            return BrowserActionResult(
                status=BrowserActionStatus.BLOCKED,
                action=action,
                error=f"Action blocked: {action_validation['reason']}"
            )
        
        # 6. Check if human approval required
        if action_validation.get("requires_approval", False):
            if self.security and context:
                approval = await self._request_human_approval(
                    action=action,
                    url=url,
                    selector=selector,
                    context=context
                )
                if not approval.get("approved", False):
                    await self._audit_action(
                        action=action,
                        status=BrowserActionStatus.BLOCKED,
                        reason="Human approval denied",
                        context=context
                    )
                    self._actions_blocked += 1
                    return BrowserActionResult(
                        status=BrowserActionStatus.BLOCKED,
                        action=action,
                        error="Human approval denied"
                    )
        
        # 7. Execute the action
        try:
            result = await self._execute_action(
                action=action_enum,
                url=url,
                selector=selector,
                value=value,
                timeout=timeout or self.DEFAULT_TIMEOUT
            )
            
            self._actions_executed += 1
            
            # 8. Audit successful action
            await self._audit_action(
                action=action,
                status=BrowserActionStatus.SUCCESS,
                url=url,
                context=context
            )
            
            return result
            
        except asyncio.TimeoutError:
            await self._audit_action(
                action=action,
                status=BrowserActionStatus.TIMEOUT,
                url=url,
                context=context
            )
            return BrowserActionResult(
                status=BrowserActionStatus.TIMEOUT,
                action=action,
                url=url,
                error="Operation timed out"
            )
            
        except Exception as e:
            await self._audit_action(
                action=action,
                status=BrowserActionStatus.FAILED,
                url=url,
                error=str(e),
                context=context
            )
            return BrowserActionResult(
                status=BrowserActionStatus.FAILED,
                action=action,
                url=url,
                error=str(e)
            )
    
    async def _validate_url(self, url: str) -> Dict[str, Any]:
        """
        Validate URL against security policies.
        
        Returns:
            Dict with 'allowed' boolean and 'reason' string
        """
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return {
                    "allowed": False,
                    "reason": f"Invalid scheme: {parsed.scheme}. Only http/https allowed"
                }
            
            # Extract domain
            domain = parsed.netloc.split(':')[0]
            
            # Check blocked domains
            for blocked in self.config.blocked_domains:
                if blocked.lower() in domain.lower():
                    return {
                        "allowed": False,
                        "reason": f"Domain blocked: {domain}"
                    }
            
            # Check whitelist if enforced
            if self.config.enforce_domain_whitelist:
                domain_allowed = any(
                    allowed.lower() in domain.lower() or domain.lower() == allowed.lower()
                    for allowed in self.config.allowed_domains
                )
                if not domain_allowed:
                    return {
                        "allowed": False,
                        "reason": f"Domain not in whitelist: {domain}"
                    }
            
            # Check localhost access
            if 'localhost' in domain or '127.0.0.1' in domain:
                if not self.config.allow_localhost:
                    return {
                        "allowed": False,
                        "reason": "Localhost access disabled"
                    }
            
            return {"allowed": True, "reason": "URL validated"}
            
        except Exception as e:
            return {
                "allowed": False,
                "reason": f"URL validation error: {str(e)}"
            }
    
    async def _validate_action(
        self,
        action: str,
        selector: Optional[str],
        value: Optional[str]
    ) -> Dict[str, Any]:
        """
        Validate action against security policies.
        
        Returns:
            Dict with 'allowed', 'reason', and 'requires_approval'
        """
        # Check blocked actions
        for blocked in self.config.blocked_actions:
            if blocked.lower() in action.lower():
                return {
                    "allowed": False,
                    "reason": f"Blocked action: {blocked}"
                }
        
        # Check for sensitive selectors
        requires_approval = False
        if selector:
            sensitive_patterns = [
                'input[type="password"]',
                'input[name="password"]',
                'input[name="passwd"]',
                'input[type="file"]',
                'input[name="credit"]',
                'input[name="card"]'
            ]
            for pattern in sensitive_patterns:
                if pattern.lower() in selector.lower():
                    requires_approval = True
                    break
        
        # High-risk actions require approval
        high_risk_actions = ['fill', 'click', 'evaluate']
        if action.lower() in high_risk_actions:
            requires_approval = True
        
        return {
            "allowed": True,
            "reason": "Action validated",
            "requires_approval": requires_approval
        }
    
    async def _execute_action(
        self,
        action: BrowserAction,
        url: Optional[str],
        selector: Optional[str],
        value: Optional[str],
        timeout: int
    ) -> BrowserActionResult:
        """
        Execute the browser action.
        
        This is a placeholder for actual Playwright integration.
        In production, this would use Playwright for browser automation.
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Initialize Playwright browser if not already
        # 2. Execute the action
        # 3. Return the result
        
        if action == BrowserAction.NAVIGATE:
            return BrowserActionResult(
                status=BrowserActionStatus.SUCCESS,
                action=action.value,
                url=url,
                metadata={"title": "Page loaded", "protocol_version": PROTOCOL_VERSION}
            )
        
        elif action == BrowserAction.CLICK:
            return BrowserActionResult(
                status=BrowserActionStatus.SUCCESS,
                action=action.value,
                metadata={"clicked": selector, "protocol_version": PROTOCOL_VERSION}
            )
        
        elif action == BrowserAction.FILL:
            return BrowserActionResult(
                status=BrowserActionStatus.SUCCESS,
                action=action.value,
                metadata={"filled": selector, "protocol_version": PROTOCOL_VERSION}
            )
        
        elif action == BrowserAction.SCREENSHOT:
            return BrowserActionResult(
                status=BrowserActionStatus.SUCCESS,
                action=action.value,
                screenshot="base64_encoded_screenshot_placeholder",
                metadata={"protocol_version": PROTOCOL_VERSION}
            )
        
        elif action == BrowserAction.SCRAPE:
            return BrowserActionResult(
                status=BrowserActionStatus.SUCCESS,
                action=action.value,
                content="Scraped content placeholder",
                metadata={"protocol_version": PROTOCOL_VERSION}
            )
        
        elif action == BrowserAction.WAIT:
            return BrowserActionResult(
                status=BrowserActionStatus.SUCCESS,
                action=action.value,
                metadata={"waited": selector, "protocol_version": PROTOCOL_VERSION}
            )
        
        else:
            return BrowserActionResult(
                status=BrowserActionStatus.FAILED,
                action=action.value,
                error=f"Action not implemented: {action.value}"
            )
    
    async def _check_capabilities(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check if context has required capabilities"""
        if not self.security:
            return {"approved": True}
        
        # In production, this would call security manager
        capabilities = context.get("capabilities", [])
        
        for cap in self.REQUIRED_CAPABILITIES:
            if cap not in capabilities:
                return {
                    "approved": False,
                    "missing": cap
                }
        
        return {"approved": True}
    
    async def _request_human_approval(
        self,
        action: str,
        url: Optional[str],
        selector: Optional[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request human approval for high-risk action"""
        if not self.security:
            return {"approved": True}
        
        # In production, this would call security manager
        # to request human approval via configured channels
        return {"approved": True, "auto_approved": True}
    
    async def _audit_action(
        self,
        action: str,
        status: BrowserActionStatus,
        reason: str = None,
        url: str = None,
        error: str = None,
        context: Dict[str, Any] = None
    ):
        """Log action to audit system"""
        if not self.audit:
            return
        
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": status.value,
            "url": url,
            "reason": reason,
            "error": error,
            "protocol_version": PROTOCOL_VERSION
        }
        
        # In production, this would call audit logger
        # await self.audit.log(audit_entry)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get controller statistics"""
        return {
            "actions_executed": self._actions_executed,
            "actions_blocked": self._actions_blocked,
            "protocol_version": PROTOCOL_VERSION
        }


# Skill manifest for registration
SKILL_MANIFEST = {
    "name": "secure_browser_controller",
    "version": "1.0.0",
    "description": "Secure browser automation with capability-based access control",
    "author": "synapse_core",
    "inputs": {
        "action": "str",
        "url": "str",
        "selector": "str",
        "value": "str",
        "timeout": "int"
    },
    "outputs": {
        "status": "str",
        "content": "str",
        "screenshot": "str",
        "error": "str"
    },
    "required_capabilities": ["network:http", "browser:automation"],
    "risk_level": 4,
    "isolation_type": "container",
    "protocol_version": PROTOCOL_VERSION
}
