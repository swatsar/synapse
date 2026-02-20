PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
import pytest
import re
from synapse.observability.logger import trace, get_metric, _metrics

@pytest.mark.asyncio
async def test_trace_logging_and_metrics(caplog):
    async with trace("test_event", foo="bar"):
        pass
    # Ensure logs contain START and END
    start = any(re.search(r"START test_event", rec.message) for rec in caplog.records)
    end = any(re.search(r"END test_event", rec.message) for rec in caplog.records)
    assert start and end
    # Metrics should be recorded
    assert get_metric("test_event_count") == 1
    assert get_metric("test_event_duration_total") > 0
