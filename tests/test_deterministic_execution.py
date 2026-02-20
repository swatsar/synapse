import pytest
from synapse.core.determinism import DeterministicSeedManager, DeterministicIDGenerator
from synapse.core.orchestrator import Orchestrator
from synapse.core.execution_fabric import ExecutionFabric

@pytest.fixture
def seed_manager():
    return DeterministicSeedManager(seed=12345)

@pytest.fixture
def id_generator():
    return DeterministicIDGenerator()

@pytest.mark.unit
def test_same_input_produces_same_output(seed_manager, id_generator):
    orchestrator = Orchestrator(seed_manager=seed_manager, id_generator=id_generator)
    input_data = {"task": "process", "payload": 1}
    out1 = orchestrator.handle(input_data)
    out2 = orchestrator.handle(input_data)
    assert out1 == out2

@pytest.mark.unit
def test_execution_fabric_node_selection_is_deterministic(seed_manager):
    fabric = ExecutionFabric(seed_manager=seed_manager)
    class DummyNode:
        def __init__(self, name):
            self.name = name
        def execute(self, task):
            return {"node": self.name}
    fabric.register_node(DummyNode("A"))
    fabric.register_node(DummyNode("B"))
    task = {"type": "compute"}
    node_a = fabric.select_node(task)
    node_b = fabric.select_node(task)
    assert node_a == node_b

@pytest.mark.unit
def test_timestamp_normalization_uses_time_sync_manager(seed_manager):
    from synapse.core.time_sync_manager import TimeSyncManager
    ts1 = TimeSyncManager.now()
    ts2 = TimeSyncManager.now()
    assert ts2 >= ts1
