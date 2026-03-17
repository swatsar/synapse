"""Middleware layer for Synapse API.

Protocol Version: 1.0
Specification: 3.1
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Callable, Dict, List
from datetime import datetime, timezone
import logging
import time
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Log all requests with correlation ID."""

    def __init__(self, app):
        self.app = app
        self.skip_paths = ["/health", "/metrics", "/docs", "/openapi.json"]

    async def __call__(self, request: Request, call_next: Callable) -> JSONResponse:
        if any(request.url.path.startswith(p) for p in self.skip_paths):
            return await call_next(request)

        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        start_time = time.time()

        logger.info(
            f"REQUEST {request.method} {request.url.path}",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"RESPONSE {request.method} {request.url.path} - {response.status_code} in {duration_ms:.2f}ms",
            extra={
                "correlation_id": correlation_id,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
        )

        return response


class SecurityHeadersMiddleware:
    """Add security headers to all responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next: Callable) -> JSONResponse:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)
        return response


class RateLimitMiddleware:
    """Rate limiting by client IP."""

    def __init__(self, app, requests_per_minute: int = 60):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self._request_counts: Dict[str, List[float]] = defaultdict(list)
        self._cleanup_interval = 300
        self._last_cleanup = time.time()

    async def __call__(self, request: Request, call_next: Callable) -> JSONResponse:
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries()

        if client_ip in self._request_counts:
            self._request_counts[client_ip] = [
                ts for ts in self._request_counts[client_ip] if now - ts < 60
            ]

        request_count = len(self._request_counts.get(client_ip, []))

        if request_count >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"error": "RATE_LIMITED", "message": "Rate limit exceeded", "protocol_version": "1.0"},
                headers={"Retry-After": "60"}
            )

        self._request_counts[client_ip].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.requests_per_minute - request_count - 1))
        return response

    def _cleanup_old_entries(self):
        now = time.time()
        self._last_cleanup = now
        for ip in list(self._request_counts.keys()):
            self._request_counts[ip] = [ts for ts in self._request_counts[ip] if now - ts < 60]
            if not self._request_counts[ip]:
                del self._request_counts[ip]


__all__ = ["RequestLoggingMiddleware", "SecurityHeadersMiddleware", "RateLimitMiddleware"]
