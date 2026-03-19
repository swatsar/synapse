"""Middleware layer for Synapse API.

Protocol Version: 1.0
Specification: 3.1

Uses pure functional @app.middleware("http") style for compatibility
with all Starlette/FastAPI versions (avoids BaseHTTPMiddleware issues).
"""

PROTOCOL_VERSION: str = "1.0"
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Callable, Dict, List
from datetime import datetime, timezone
import logging
import time
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)

_rate_limit_counts: Dict[str, List[float]] = defaultdict(list)
_rate_limit_last_cleanup: float = time.time()
_CLEANUP_INTERVAL = 300


def _cleanup_rate_limits() -> None:
    global _rate_limit_last_cleanup
    now = time.time()
    if now - _rate_limit_last_cleanup < _CLEANUP_INTERVAL:
        return
    _rate_limit_last_cleanup = now
    for ip in list(_rate_limit_counts.keys()):
        _rate_limit_counts[ip] = [ts for ts in _rate_limit_counts[ip] if now - ts < 60]
        if not _rate_limit_counts[ip]:
            del _rate_limit_counts[ip]


def make_request_logging_middleware() -> Callable:
    skip_paths = ["/health", "/metrics", "/docs", "/openapi.json"]

    async def middleware(request: Request, call_next: Callable):
        if any(request.url.path.startswith(p) for p in skip_paths):
            return await call_next(request)
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        start_time = time.time()
        logger.info(f"REQUEST {request.method} {request.url.path}")
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"RESPONSE {request.method} {request.url.path} - {response.status_code} in {duration_ms:.2f}ms"
        )
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    return middleware


def make_security_headers_middleware() -> Callable:
    async def middleware(request: Request, call_next: Callable):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

    return middleware


def make_rate_limit_middleware(requests_per_minute: int = 60) -> Callable:
    async def middleware(request: Request, call_next: Callable):
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        _cleanup_rate_limits()
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        _rate_limit_counts[client_ip] = [
            ts for ts in _rate_limit_counts[client_ip] if now - ts < 60
        ]
        count = len(_rate_limit_counts[client_ip])
        if count >= requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"error": "RATE_LIMITED", "message": "Rate limit exceeded", "protocol_version": "1.0"},
                headers={"Retry-After": "60"},
            )
        _rate_limit_counts[client_ip].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, requests_per_minute - count - 1))
        return response

    return middleware


# Compatibility shims (imported by tests referencing class names)
class RequestLoggingMiddleware:
    def __init__(self, app, **kwargs):
        self.app = app
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app, **kwargs):
        self.app = app
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class RateLimitMiddleware:
    def __init__(self, app, requests_per_minute: int = 60, **kwargs):
        self.app = app
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


__all__ = [
    "RequestLoggingMiddleware", "SecurityHeadersMiddleware", "RateLimitMiddleware",
    "make_request_logging_middleware", "make_security_headers_middleware", "make_rate_limit_middleware",
]
