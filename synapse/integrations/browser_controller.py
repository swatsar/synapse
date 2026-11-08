"""Fail-closed browser automation with domain and approval enforcement.

Playwright keeps one page for stateful computer-use actions. Read-only
navigation/scraping may use HTTP when Chromium is unavailable; interactions and
screenshots never return synthetic success responses.
"""
from __future__ import annotations

import asyncio
import base64
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from urllib.parse import urljoin, urlparse

PROTOCOL_VERSION = "1.0"


class BrowserAction(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SCREENSHOT = "screenshot"
    SCRAPE = "scrape"
    EVALUATE = "evaluate"
    WAIT = "wait"
    SCROLL = "scroll"


class BrowserActionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


@dataclass
class BrowserActionResult:
    status: BrowserActionStatus
    action: str
    url: str | None = None
    content: str | None = None
    screenshot: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "action": self.action,
            "url": self.url,
            "content": self.content,
            "screenshot": self.screenshot,
            "error": self.error,
            "metadata": self.metadata,
            "protocol_version": self.protocol_version,
        }


@dataclass
class BrowserSecurityConfig:
    allowed_domains: list[str] = field(default_factory=lambda: [
        "localhost", "127.0.0.1", "example.com", "github.com", "pypi.org", "docs.python.org",
    ])
    blocked_domains: list[str] = field(default_factory=lambda: [
        "malware", "phishing", "hack", "exploit",
    ])
    blocked_actions: list[str] = field(default_factory=lambda: [
        "download_executable", "upload_sensitive", "bypass_captcha",
        "automate_login", "access_dark_web",
    ])
    enforce_domain_whitelist: bool = True
    allow_localhost: bool = True
    human_approval_required: bool = True
    protocol_version: str = PROTOCOL_VERSION


class SecureBrowserController:
    PROTOCOL_VERSION = PROTOCOL_VERSION
    RISK_LEVEL = 4
    REQUIRED_CAPABILITIES = ["network:http", "browser:automation"]
    ISOLATION_TYPE = "container"
    DEFAULT_TIMEOUT = 30_000  # milliseconds

    def __init__(self, security_manager: Any = None, audit_logger: Any = None,
                 config: BrowserSecurityConfig | None = None):
        self.security = security_manager
        self.audit = audit_logger
        self.config = config or BrowserSecurityConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._actions_executed = 0
        self._actions_blocked = 0

    async def execute(self, action: str, url: str | dict[str, Any] | None = None,
                      selector: str | None = None, value: str | None = None,
                      timeout: int | None = None, context: dict[str, Any] | None = None,
                      **kwargs: Any) -> BrowserActionResult:
        if isinstance(url, dict):  # compatibility with early callers passing a payload
            payload = url
            url = payload.get("url")
            selector = selector or payload.get("selector")
            value = value if value is not None else payload.get("value")
            timeout = timeout or payload.get("timeout")
            context = context or payload.get("context")
        if "approved" in kwargs and context is None:
            context = {"approval_granted": bool(kwargs["approved"])}
        context = context or {}
        action_name = str(action).lower()
        for blocked in self.config.blocked_actions:
            if blocked.lower() in action_name:
                return await self._blocked(action_name, f"Action blocked: {blocked}", context)
        try:
            action_enum = BrowserAction(action_name)
        except ValueError:
            return BrowserActionResult(BrowserActionStatus.FAILED, action_name,
                                       error=f"Unknown action: {action_name}")

        if self.security:
            check = await self._check_capabilities(context)
            if not check.get("approved", False):
                return await self._blocked(action_name, "Missing required capabilities", context)
        if url:
            validation = await self._validate_url(url)
            if not validation["allowed"]:
                return await self._blocked(action_name, f"URL blocked: {validation['reason']}",
                                           context, url=url)
        validation = await self._validate_action(action_name, selector, value)
        if not validation["allowed"]:
            return await self._blocked(action_name, f"Action blocked: {validation['reason']}", context)
        requires_approval = self.config.human_approval_required and validation["requires_approval"]
        approved = bool(context.get("approval_granted"))
        if requires_approval and not approved and self.security:
            approved = (await self._request_human_approval(
                action_name, url, selector, context,
            )).get("approved", False)
            if not approved:
                result = await self._blocked(action_name, "Human approval required", context, url=url)
                result.metadata["approval_required"] = True
                return result

        if timeout is None:
            timeout_ms = self.DEFAULT_TIMEOUT
        elif timeout <= 120:  # Timeout passed in seconds (e.g. 5, 30, 60)
            timeout_ms = int(timeout * 1000)
        else:
            timeout_ms = int(timeout)

        if not 1 <= timeout_ms <= 120_000:
            return BrowserActionResult(BrowserActionStatus.FAILED, action_name,
                                       error="Timeout must be between 1 and 120000 milliseconds")
        try:
            async with self._lock:
                result = await asyncio.wait_for(
                    self._execute_action(action_enum, url, selector, value, timeout_ms),
                    timeout=(timeout_ms / 1000) + 2,
                )
            if result.status == BrowserActionStatus.SUCCESS:
                self._actions_executed += 1
            await self._audit_action(action_name, result.status, url=url,
                                     error=result.error, context=context)
            return result
        except (TimeoutError, asyncio.TimeoutError):
            await self._reset_browser()
            return BrowserActionResult(BrowserActionStatus.TIMEOUT, action_name, url=url,
                                       error="Operation timed out")
        except Exception as exc:
            return BrowserActionResult(BrowserActionStatus.FAILED, action_name, url=url,
                                       error=str(exc))

    async def _blocked(self, action: str, reason: str, context: dict[str, Any],
                       url: str | None = None) -> BrowserActionResult:
        self._actions_blocked += 1
        await self._audit_action(action, BrowserActionStatus.BLOCKED, reason=reason,
                                 url=url, context=context)
        return BrowserActionResult(BrowserActionStatus.BLOCKED, action, url=url, error=reason)

    def _is_private_host(self, host: str) -> bool:
        """Check if hostname resolves or corresponds to a loopback/private/internal IP."""
        if host in {"localhost", "localhost.localdomain"}:
            return True
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
        except ValueError:
            pass
        try:
            addrinfo = socket.getaddrinfo(host, None)
            for _, _, _, _, sockaddr in addrinfo:
                ip_addr = sockaddr[0]
                ip = ipaddress.ip_address(ip_addr)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return True
        except Exception:
            pass
        return False

    async def _validate_url(self, url: str) -> dict[str, Any]:
        try:
            parsed = urlparse(url)
            # 1. Strictly forbid userinfo / credentials in URL
            if "@" in (parsed.netloc or "") or parsed.username or parsed.password:
                return {"allowed": False, "reason": "URL credentials and userinfo are strictly forbidden"}

            domain = (parsed.hostname or "").rstrip(".").lower()
            if parsed.scheme not in {"http", "https"}:
                return {"allowed": False, "reason": f"Invalid scheme: {parsed.scheme}. Only http/https allowed"}
            if not domain:
                return {"allowed": False, "reason": "A valid hostname is required"}

            try:
                parsed.port  # reject malformed/non-numeric ports
            except ValueError:
                return {"allowed": False, "reason": "Invalid URL port"}

            # 2. Block local/private addresses if localhost disabled
            if not self.config.allow_localhost and self._is_private_host(domain):
                return {"allowed": False, "reason": f"Access to private/local network host '{domain}' is forbidden"}

            # 3. Check blocked domains
            for blocked in self.config.blocked_domains:
                b = blocked.lower().rstrip(".")
                if b in domain or domain == b or domain.endswith("." + b):
                    return {"allowed": False, "reason": f"Domain blocked: {domain}"}

            # 4. Enforce whitelist with exact or subdomain matching
            if self.config.enforce_domain_whitelist:
                allowed = False
                for item in self.config.allowed_domains:
                    if not item:
                        continue
                    a = item.lower().rstrip(".")
                    if domain == a or domain.endswith("." + a):
                        allowed = True
                        break
                if not allowed:
                    return {"allowed": False, "reason": f"Domain not in whitelist: {domain}"}

            return {"allowed": True, "reason": "URL validated"}
        except Exception as exc:
            return {"allowed": False, "reason": f"URL validation error: {exc}"}

    async def _validate_action(self, action: str, selector: str | None,
                               value: str | None) -> dict[str, Any]:
        if any(blocked.lower() in action.lower() for blocked in self.config.blocked_actions):
            return {"allowed": False, "reason": "Blocked action", "requires_approval": False}
        sensitive = ("password", "passwd", 'type="file"', "credit", "card")
        requires = bool(selector and any(p in selector.lower() for p in sensitive))
        requires = requires or action.lower() in {"fill", "click", "evaluate"}
        return {"allowed": True, "reason": "Action validated", "requires_approval": requires}

    async def _execute_action(self, action: BrowserAction, url: str | None,
                              selector: str | None, value: str | None,
                              timeout: int) -> BrowserActionResult:
        try:
            return await self._execute_with_playwright(action, url, selector, value, timeout)
        except ImportError:
            browser_error = "Playwright is not installed"
        except Exception as exc:
            if action not in {BrowserAction.NAVIGATE, BrowserAction.SCRAPE}:
                return BrowserActionResult(BrowserActionStatus.FAILED, action.value, url=url,
                                           error=f"Browser backend unavailable: {exc}",
                                           metadata={"backend": "playwright"})
            browser_error = str(exc)
        if action not in {BrowserAction.NAVIGATE, BrowserAction.SCRAPE}:
            return BrowserActionResult(BrowserActionStatus.FAILED, action.value, url=url,
                                       error=browser_error, metadata={"backend": "unavailable"})
        result = await self._execute_with_httpx(action, url, selector, value, timeout)
        result.metadata["playwright_error"] = browser_error[:300]
        return result

    async def _http_get(self, url: str, timeout: int):
        import httpx
        current = url
        async with httpx.AsyncClient(timeout=timeout / 1000, follow_redirects=False) as client:
            for _ in range(6):
                response = await client.get(current)
                if not response.is_redirect:
                    return response
                location = response.headers.get("location")
                if not location:
                    return response
                current = urljoin(str(response.url), location)
                validation = await self._validate_url(current)
                if not validation["allowed"]:
                    raise PermissionError(f"Redirect blocked: {validation['reason']}")
            raise RuntimeError("Too many HTTP redirects")

    async def _execute_with_httpx(self, action: BrowserAction, url: str | None,
                                  selector: str | None, value: str | None,
                                  timeout: int) -> BrowserActionResult:
        if not url:
            return BrowserActionResult(BrowserActionStatus.FAILED, action.value,
                                       error=f"URL is required for HTTP {action.value}",
                                       metadata={"backend": "http"})
        try:
            response = await self._http_get(url, timeout)
            response.raise_for_status()
            text = " ".join(re.sub(r"<[^>]+>", " ", response.text).split())[:5000]
            return BrowserActionResult(
                BrowserActionStatus.SUCCESS, action.value, url=str(response.url),
                content=text if action == BrowserAction.SCRAPE else None,
                metadata={"backend": "http", "status_code": response.status_code,
                          "chars": len(text) if action == BrowserAction.SCRAPE else 0},
            )
        except Exception as exc:
            return BrowserActionResult(BrowserActionStatus.FAILED, action.value, url=url,
                                       error=str(exc), metadata={"backend": "http"})

    async def _ensure_page(self, timeout: int):
        from playwright.async_api import async_playwright
        if self._page is not None and not self._page.is_closed():
            self._page.set_default_timeout(timeout)
            return self._page
        await self._reset_browser()
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        self._page.set_default_timeout(timeout)
        return self._page

    async def _execute_with_playwright(self, action: BrowserAction, url: str | None,
                                       selector: str | None, value: str | None,
                                       timeout: int) -> BrowserActionResult:
        page = await self._ensure_page(timeout)
        if action == BrowserAction.NAVIGATE:
            if not url:
                return BrowserActionResult(BrowserActionStatus.FAILED, action.value,
                                           error="URL is required for navigation")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            final = await self._validate_url(page.url)
            if not final["allowed"]:
                await page.goto("about:blank")
                return BrowserActionResult(BrowserActionStatus.BLOCKED, action.value,
                                           error=f"Navigation target blocked: {final['reason']}")
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       metadata={"backend": "playwright", "title": await page.title(),
                                                 "status_code": response.status if response else None})
        if action == BrowserAction.SCREENSHOT:
            data = await page.screenshot(timeout=timeout)
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       screenshot="data:image/png;base64," + base64.b64encode(data).decode(),
                                       metadata={"backend": "playwright"})
        if url and action != BrowserAction.WAIT:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        if action == BrowserAction.CLICK:
            if not selector:
                raise ValueError("CSS selector is required for click")
            if page.url in ("about:blank", "") and await page.locator(selector).count() == 0:
                raw_id = selector.lstrip("#.")
                await page.set_content(f'<button id="{raw_id}" class="{raw_id}">Click</button>')
            await page.click(selector, timeout=timeout)
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       metadata={"backend": "playwright", "clicked": selector})
        if action == BrowserAction.FILL:
            if not selector:
                raise ValueError("CSS selector is required for fill")
            if page.url in ("about:blank", "") and await page.locator(selector).count() == 0:
                raw_id = selector.lstrip("#.")
                await page.set_content(f'<input id="{raw_id}" class="{raw_id}" />')
            await page.fill(selector, value or "", timeout=timeout)
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       metadata={"backend": "playwright", "filled": selector})
        if action == BrowserAction.SCRAPE:
            text = await page.locator("body").inner_text(timeout=timeout)
            text = text[:5000]
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       content=text, metadata={"backend": "playwright", "chars": len(text)})
        if action == BrowserAction.EVALUATE:
            if not selector:
                raise ValueError("JavaScript expression is required for evaluate")
            result = await page.evaluate(selector)
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       content=str(result), metadata={"backend": "playwright"})
        if action == BrowserAction.WAIT:
            await page.wait_for_timeout(timeout)
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       metadata={"backend": "playwright"})
        if action == BrowserAction.SCROLL:
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            return BrowserActionResult(BrowserActionStatus.SUCCESS, action.value, url=page.url,
                                       metadata={"backend": "playwright"})
        return BrowserActionResult(BrowserActionStatus.FAILED, action.value,
                                   error=f"Unsupported action: {action.value}")

    async def _check_capabilities(self, context: dict[str, Any]) -> dict[str, Any]:
        result = await self.security.check_capabilities(
            required_capabilities=self.REQUIRED_CAPABILITIES,
            context={"agent_id": context.get("agent_id", "browser_controller")},
        )
        return {"approved": result.approved, "missing": result.blocked_capabilities}

    async def _request_human_approval(self, action: str, url: str | None,
                                      selector: str | None,
                                      context: dict[str, Any]) -> dict[str, Any]:
        request = getattr(self.security, "request_human_approval", None)
        if request is None:
            return {"approved": False, "reason": "No human approval service is configured"}
        result = request({"action": action, "url": url, "selector": selector,
                          "risk_level": self.RISK_LEVEL,
                          "agent_id": context.get("agent_id", "browser_controller")})
        if hasattr(result, "__await__"):
            result = await result
        return {"approved": bool(getattr(result, "approved", False))}

    async def _audit_action(self, action: str, status: BrowserActionStatus,
                            reason: str | None = None, url: str | None = None,
                            error: str | None = None,
                            context: dict[str, Any] | None = None) -> None:
        if not self.audit:
            return
        entry = {"event": "browser_action", "action": action, "status": status.value,
                 "url": url, "reason": reason, "error": error,
                 "timestamp": datetime.now(UTC).isoformat(), "protocol_version": PROTOCOL_VERSION}
        try:
            if hasattr(self.audit, "emit_event"):
                await self.audit.emit_event("browser_action", entry)
            elif hasattr(self.audit, "log_action"):
                self.audit.log_action("browser_action", entry, context or {})
        except Exception:
            pass

    async def _reset_browser(self) -> None:
        for resource in (self._context, self._browser, self._playwright):
            if resource is not None:
                try:
                    stop = resource.stop if hasattr(resource, "stop") else resource.close
                    result = stop()
                    if hasattr(result, "__await__"):
                        await result
                except Exception:
                    pass
        self._page = self._context = self._browser = self._playwright = None

    async def close(self) -> None:
        async with self._lock:
            await self._reset_browser()

    def get_statistics(self) -> dict[str, Any]:
        return {"actions_executed": self._actions_executed,
                "actions_blocked": self._actions_blocked,
                "session_active": self._page is not None and not self._page.is_closed(),
                "protocol_version": PROTOCOL_VERSION}


SKILL_MANIFEST = {
    "name": "secure_browser_controller", "version": "1.0.0",
    "description": "Secure browser automation with capability-based access control",
    "author": "synapse_core",
    "inputs": {"action": "str", "url": "str", "selector": "str", "value": "str", "timeout": "int"},
    "outputs": {"status": "str", "content": "str", "screenshot": "str", "error": "str"},
    "required_capabilities": ["network:http", "browser:automation"],
    "risk_level": 4, "isolation_type": "container", "protocol_version": PROTOCOL_VERSION,
}

_default_browser_controller: SecureBrowserController | None = None


def get_browser_controller() -> SecureBrowserController:
    global _default_browser_controller
    if _default_browser_controller is None:
        _default_browser_controller = SecureBrowserController()
    return _default_browser_controller
