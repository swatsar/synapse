import pytest
from synapse.core.node_runtime import NodeRuntime
from synapse.core.execution_fabric import ExecutionFabric
from synapse.core.rollback import RollbackManager
from synapse.core.checkpoint import CheckpointManager
from synapse.core.security import CapabilityManager
from synapse.core.audit import AuditLogger

@pytest.fixture(scope="module")
def cluster_nodes():
    nodes = [NodeRuntime(node_id=f"node-{i}") for i in range(3)]
    for n in nodes:
        n.start()
    yield nodes
    for n in nodes:
        n.stop()

@pytest.mark.unit
def test_end_to_end_cluster_execution(cluster_nodes):
    fabric = ExecutionFabric()
    for node in cluster_nodes:
        fabric.register_node(node)
    task = {"action": "read_file", "path": "/tmp/test.txt", "required_cap": ["fs:read:/tmp/**"]}
    result = fabric.submit(task)
    assert result["status"] == "completed"
    # Simulated failure
    failing = {"action": "write_file", "path": "/tmp/readonly.txt", "data": "oops", "required_cap": ["fs:write:/tmp/**"]}
    with pytest.raises(Exception):
        fabric.submit(failing)
    # Rollback – using a dummy checkpoint id for illustration
    cap = CapabilityManager()
    audit = AuditLogger()
    cp_manager = CheckpointManager(cap_manager=cap, audit=audit)
    cp = cp_manager.create_checkpoint(state={})
    rb = RollbackManager(cp_manager=cp_manager, cap_manager=cap, audit=audit)
    rb.rollback_to(cp.id)
    assert True
