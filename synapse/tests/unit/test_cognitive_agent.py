PROTOCOL_VERSION: str = "1.0"
import pytest
from synapse.core.models import ExecutionContext, SkillManifest, ResourceLimits
from synapse.agents.runtime.agent import CognitiveAgent

@pytest.fixture
def dummy_context():
    return ExecutionContext(
        session_id="sess",
        agent_id="agent",
        trace_id="trace",
        capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**", "net:http"],
        memory_store=None,
        logger=None,
        resource_limits=ResourceLimits(cpu_seconds=10, memory_mb=256, disk_mb=10, network_kb=500),
        protocol_version="1.0"
    )

@pytest.mark.asyncio
async def test_agent_skill_execution(dummy_context):
    agent = CognitiveAgent("test_agent", dummy_context)
    # Register a dummy skill that returns a known value
    async def dummy_skill(x):
        return {"result": x * 2}
    manifest = SkillManifest(
        name="dummy",
        version="1.0",
        description="Dummy skill",
        author="test",
        inputs={"x": "int"},
        outputs={"result": "int"},
        required_capabilities=[],
        timeout_seconds=5,
        trust_level="trusted",
        risk_level=1,
        isolation_type="subprocess",
    )
    agent.register_skill(manifest, dummy_skill)
    # Override reason to request the dummy skill
    async def custom_reason(_):
        return {"action": "skill", "skill_name": "dummy", "params": {"x": 3}}
    agent.reason = custom_reason
    result = await agent.run_once()
    assert result == {"result": 6}
