PROTOCOL_VERSION: str = "1.0"
import pytest
import asyncio
from synapse.core.models import ExecutionContext, ResourceLimits
from synapse.core.orchestrator import Orchestrator
from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard
from synapse.skills.system.file_ops import read_file, write_file

@pytest.fixture
def test_context(tmp_path):
    # Provide a temporary workspace for file ops
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return ExecutionContext(
        session_id="sess",
        agent_id="agent",
        trace_id="trace",
        capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**"],
        memory_store=None,
        logger=None,
        resource_limits=ResourceLimits(cpu_seconds=10, memory_mb=256, disk_mb=10, network_kb=500),
        protocol_version="1.0"
    )

@pytest.mark.asyncio
async def test_orchestrator_executes_skill(test_context, tmp_path):
    # Register a dummy skill that writes a file
    guard = ExecutionGuard(test_context.resource_limits)
    cap_manager = CapabilityManager()
    orchestrator = Orchestrator(test_context, cap_manager, guard)
    orchestrator.register_skill("write_file", write_file)
    orchestrator.register_skill("read_file", read_file)
    # Execute write
    file_path = str(tmp_path / "workspace" / "test.txt")
    await orchestrator.execute_skill("write_file", path=file_path, data="hello")
    # Execute read and verify content
    result = await orchestrator.execute_skill("read_file", path=file_path)
    assert result["content"] == "hello"
