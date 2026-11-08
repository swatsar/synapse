"""
Circuit Breaker and Retry Utilities for LLM Providers.

Implements standard stability patterns:
- Circuit Breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Exponential Backoff with Jitter for transient network faults
- Health state inspection

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.llm.providers.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"        # Normal operation: traffic flows freely
    OPEN = "open"            # Tripped: traffic is blocked immediately to prevent cascading failure
    HALF_OPEN = "half_open"  # Probing: test request allowed to verify recovery


class CircuitBreakerOpenError(RuntimeError):
    """Raised when request is rejected because the circuit breaker is OPEN."""

    def __init__(self, provider: str, retry_after_sec: float):
        super().__init__(f"Circuit breaker for provider '{provider}' is OPEN. Retry in {retry_after_sec:.1f}s")
        self.provider = provider
        self.retry_after_sec = retry_after_sec


@dataclass
class CircuitBreakerStats:
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[float]
    last_success_time: Optional[float]
    tripped_count: int
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "tripped_count": self.tripped_count,
            "protocol_version": self.protocol_version,
        }


class CircuitBreaker:
    """Circuit breaker guarding external provider connections against cascaded failures."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 30.0,
        half_open_max_trials: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.half_open_max_trials = half_open_max_trials

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_trials = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._tripped_count = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        now = time.monotonic()
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if now - self._last_failure_time >= self.recovery_timeout_sec:
                self._state = CircuitState.HALF_OPEN
                self._half_open_trials = 0
                logger.info("Circuit breaker for %s transitioned from OPEN to HALF_OPEN", self.name)
        return self._state

    def allow_request(self) -> bool:
        """Check whether a request is permitted to proceed."""
        current_state = self.state
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.HALF_OPEN:
            return self._half_open_trials < self.half_open_max_trials
        return False

    def time_until_retry(self) -> float:
        """Seconds remaining before circuit breaker tests recovery."""
        if self._state != CircuitState.OPEN or not self._last_failure_time:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        return max(0.0, self.recovery_timeout_sec - elapsed)

    def record_success(self) -> None:
        """Record successful execution and reset failure state."""
        self._last_success_time = time.monotonic()
        self._success_count += 1
        if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            logger.info("Circuit breaker for %s successfully recovered -> CLOSED", self.name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_trials = 0

    def record_failure(self, error: Optional[Exception | str] = None) -> None:
        """Record failure and trip circuit breaker if threshold is exceeded."""
        now = time.monotonic()
        self._last_failure_time = now
        self._failure_count += 1

        if self._state == CircuitState.HALF_OPEN:
            # Immediately trip back to OPEN
            self._state = CircuitState.OPEN
            self._tripped_count += 1
            logger.warning("Circuit breaker for %s failed during HALF_OPEN trial -> OPEN: %s", self.name, error)
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._tripped_count += 1
                logger.warning(
                    "Circuit breaker for %s tripped OPEN (%d consecutive failures, threshold %d): %s",
                    self.name,
                    self._failure_count,
                    self.failure_threshold,
                    error,
                )

    def get_stats(self) -> CircuitBreakerStats:
        return CircuitBreakerStats(
            state=self.state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            last_success_time=self._last_success_time,
            tripped_count=self._tripped_count,
        )


def calculate_backoff(
    attempt: int,
    base_delay_sec: float = 0.5,
    max_delay_sec: float = 10.0,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff with full jitter to avoid thundering herds."""
    delay = min(max_delay_sec, base_delay_sec * (2 ** max(0, attempt - 1)))
    if jitter:
        delay = random.uniform(0.0, delay)
    return delay
