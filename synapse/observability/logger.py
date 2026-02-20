"""Observability logging module."""
"""Observability logging module.
PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone

logger = logging.getLogger("synapse.observability")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

_metrics: Dict[str, int] = {}
_audit_log: list = []

def record_metric(name: str, value: int = 1) -> None:
    _metrics[name] = _metrics.get(name, 0) + value

def get_metric(name: str) -> int:
    return _metrics.get(name, 0)

def audit(event: Union[Dict[str, Any], str] = None, **kwargs) -> None:
    """Record an audit event.

    Args:
        event: Event data to audit (optional, can be dict or string)
        **kwargs: Additional event data as keyword arguments
    """
    if event is None:
        event_copy = {}
    elif isinstance(event, str):
        event_copy = {"event": event}
    else:
        event_copy = event.copy()
    event_copy.update(kwargs)
    event_copy["timestamp"] = datetime.now(timezone.utc).isoformat()
    _audit_log.append(event_copy)
    logger.info(f"AUDIT: {event_copy}")

def get_audit_log() -> list:
    """Get all audit log entries."""
    return _audit_log.copy()

@asynccontextmanager
async def trace(event_name: str, **attrs: Any):
    start = time.time()
    logger.info(f"START {event_name} {attrs}")
    try:
        yield
    finally:
        duration = time.time() - start
        # Convert to milliseconds and guarantee at least 1 ms to avoid zero
        duration_ms = max(int(duration * 1000), 1)
        logger.info(f"END {event_name} duration={duration_ms}ms {attrs}")
        record_metric(f"{event_name}_count")
        record_metric(f"{event_name}_duration_total", duration_ms)
