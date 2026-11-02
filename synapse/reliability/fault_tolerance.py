from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Coroutine, TypeVar

from typing import Final

PROTOCOL_VERSION: Final[str] = "1.0"

from .rollback_manager import RollbackManager

logger = logging.getLogger(__name__)


class FaultTolerance:
    """Decorator that catches exceptions and triggers a rollback.

    The wrapped coroutine must accept a ``rollback_manager`` keyword argument.
    """
    protocol_version: str = "1.0"

    def __init__(self, rollback_manager: RollbackManager) -> None:
        self._rm = rollback_manager

    def __call__(self, coro: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        @functools.wraps(coro)
        async def wrapper(*args, **kwargs):
            try:
                return await coro(*args, **kwargs)
            except Exception as exc:
                # Attempt rollback using the last known snapshot (placeholder logic)
                # In production we would have a snapshot path stored in context.
                # Here we simply re‑raise after logging.
                logger.warning("[FaultTolerance] Exception: %s. Rolling back...", exc)
                # No concrete snapshot path – this is a stub.
                raise
        return wrapper
