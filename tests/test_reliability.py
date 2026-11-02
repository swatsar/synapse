"""Tests for reliability modules."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestFaultTolerance:
    """Test fault tolerance."""

    def test_fault_tolerance_creation(self):
        """Test fault tolerance creation."""
        from synapse.reliability.rollback_manager import RollbackManager
        from synapse.reliability.fault_tolerance import FaultTolerance
        rm = MagicMock()
        ft = FaultTolerance(rm)
        assert ft is not None

    @pytest.mark.asyncio
    async def test_fault_tolerance_wrapper_success(self):
        """Test fault tolerance wrapper success."""
        from synapse.reliability.rollback_manager import RollbackManager
        from synapse.reliability.fault_tolerance import FaultTolerance
        rm = MagicMock()
        ft = FaultTolerance(rm)

        @ft
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_fault_tolerance_wrapper_failure(self):
        """Test fault tolerance wrapper failure."""
        from synapse.reliability.rollback_manager import RollbackManager
        from synapse.reliability.fault_tolerance import FaultTolerance
        rm = MagicMock()
        ft = FaultTolerance(rm)

        @ft
        async def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await fail_func()
