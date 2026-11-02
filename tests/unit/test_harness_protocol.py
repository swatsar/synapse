import pytest
from synapse.harnesses import CodexHarness, HarnessRequest
@pytest.mark.asyncio
async def test_harness_is_execution_adapter_not_orchestrator():
    result=await CodexHarness().execute(HarnessRequest('t','r','implement'))
    assert result.success is False
    assert 'not configured' in result.error
