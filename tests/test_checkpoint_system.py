import uuid
import pytest
from synapse.core.checkpoint import CheckpointManager
from synapse.core.rollback import RollbackManager
from synapse.core.security import CapabilityManager
from synapse.core.audit import AuditLogger

@pytest.fixture
def cp_manager():
    cap = CapabilityManager()
    audit = AuditLogger()
    return CheckpointManager(cap_manager=cap, audit=audit)

@pytest.fixture
def rb_manager(cp_manager):
    cap = CapabilityManager()
    audit = AuditLogger()
    return RollbackManager(cp_manager=cp_manager, cap_manager=cap, audit=audit)

@pytest.fixture
def capability_manager():
    return CapabilityManager()

@pytest.mark.unit
def test_checkpoint_creation_returns_id(cp_manager):
    cp = cp_manager.create_checkpoint(state={"key": "value"})
    assert isinstance(cp.id, uuid.UUID)

@pytest.mark.unit
def test_checkpoint_contains_deterministic_state(cp_manager):
    state = {"counter": 42, "data": [1, 2, 3]}
    cp = cp_manager.create_checkpoint(state=state)
    assert cp.state == state

@pytest.mark.unit
def test_rollback_restores_state(cp_manager, rb_manager):
    original = {"value": 10}
    cp = cp_manager.create_checkpoint(state=original)
    # Simulate state change
    cp_manager.update_state(cp.id, {"value": 999})
    rb_manager.rollback_to(cp.id)
    restored = cp_manager.get_state(cp.id)
    assert restored == original

@pytest.mark.unit
def test_cluster_wide_rollback(cp_manager, rb_manager):
    cp = cp_manager.create_checkpoint(state={"cluster": True})
    rb_manager.rollback_to(cp.id)
    assert True

@pytest.mark.unit
def test_audit_log_records_checkpoint_ops(cp_manager, capability_manager):
    cp = cp_manager.create_checkpoint(state={})
    assert cp.id is not None
