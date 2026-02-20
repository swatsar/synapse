PROTOCOL_VERSION: str = "1.0"
import pytest
from pathlib import Path

from synapse.skills.builtins.read_file import ReadFileSkill
from synapse.skills.builtins.write_file import WriteFileSkill
from synapse.skills.builtins.web_search import WebSearchSkill
from synapse.core.models import ExecutionContext, ResourceLimits

@pytest.fixture
def test_context():
    return ExecutionContext(
        session_id="test_sess",
        agent_id="test_agent",
        trace_id="trace_1",
        capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**", "net:http"],
        memory_store=None,
        logger=None,
        resource_limits=ResourceLimits(cpu_seconds=10, memory_mb=256, disk_mb=10, network_kb=500),
        protocol_version="1.0"
    )

@pytest.mark.asyncio
async def test_read_file_success(tmp_path, test_context):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello world")
    skill = ReadFileSkill()
    result = await skill.execute(test_context, path=str(file_path))
    assert result["success"] is True
    assert result["content"] == "hello world"

@pytest.mark.asyncio
async def test_write_file_success(tmp_path, test_context):
    file_path = tmp_path / "out.txt"
    skill = WriteFileSkill()
    result = await skill.execute(test_context, path=str(file_path), content="test data")
    assert result["success"] is True
    assert file_path.read_text() == "test data"

@pytest.mark.asyncio
async def test_web_search_success(test_context):
    skill = WebSearchSkill()
    result = await skill.execute(test_context, query="httpbin.org/get")
    assert result["success"] is True
    assert "url" in result["response"]
