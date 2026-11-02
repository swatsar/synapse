"""Tests for execution guard."""
import pytest
from synapse.core.models import ResourceLimits


class TestExecutionGuard:
    """Test execution guard."""

    @pytest.fixture
    def execution_guard(self):
        """Create an execution guard for testing."""
        from synapse.security.execution_guard import ExecutionGuard
        limits = ResourceLimits(cpu_seconds=60, memory_mb=512, disk_mb=100, network_kb=1024)
        return ExecutionGuard(limits=limits)

    def test_execution_guard_creation(self, execution_guard):
        """Test execution guard creation."""
        assert execution_guard is not None

    @pytest.mark.asyncio
    async def test_execution_guard_context(self, execution_guard):
        """Test execution guard context."""
        async with execution_guard:
            pass

    @pytest.mark.asyncio
    async def test_execution_guard_run(self, execution_guard):
        """Test execution guard run."""
        async def test_func():
            return {"result": "success"}
        test_func.trust_level = "trusted"
        test_func.risk_level = 1
        result = await execution_guard.run(test_func)
        assert result == {"result": "success"}
