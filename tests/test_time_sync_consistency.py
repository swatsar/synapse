import pytest
from synapse.core.time_sync_manager import TimeSyncManager

@pytest.mark.unit
def test_timestamp_normalization_consistency():
    TimeSyncManager.set_offset(node_id="node-1", offset_ms=5)
    TimeSyncManager.set_offset(node_id="node-2", offset_ms=-3)
    t1 = TimeSyncManager.now(node_id="node-1")
    t2 = TimeSyncManager.now(node_id="node-2")
    assert abs((t1 - t2).total_seconds()) < 0.01

@pytest.mark.unit
def test_monotonic_fallback():
    TimeSyncManager._last_timestamp = None
    t1 = TimeSyncManager.now()
    t2 = TimeSyncManager.now()
    assert t2 >= t1
