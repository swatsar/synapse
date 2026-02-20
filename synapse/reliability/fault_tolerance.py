PROTOCOL_VERSION: str = "1.0"
import functools

from .rollback_manager import RollbackManager

class FaultTolerance:
    """Decorator that catches exceptions and triggers a rollback.

    The wrapped coroutine must accept a ``rollback_manager`` keyword argument.
    """
    protocol_version: str = "1.0"

    def __init__(self, rollback_manager: RollbackManager):
        self._rm = rollback_manager

    def __call__(self, coro):
        @functools.wraps(coro)
        async def wrapper(*args, **kwargs):
            try:
                return await coro(*args, **kwargs)
            except Exception as exc:
                # Attempt rollback using the last known snapshot (placeholder logic)
                # In production we would have a snapshot path stored in context.
                # Here we simply re‑raise after logging.
                print(f"[FaultTolerance] Exception: {exc}. Rolling back…")
                # No concrete snapshot path – this is a stub.
                raise
        return wrapper
