"""
Tests for Runtime API Specification Layer
"""

import pytest
import hashlib
import json
from datetime import datetime

from synapse.runtime_api.deterministic_runtime_api import (
    ExecutionDomain,
    ExecutionStatus,
    ExecutionContract,
    RuntimeCall,
    RuntimeResult,
    DeterministicRuntimeAPI
)


class TestExecutionContractSpecification:
    """Specification tests for ExecutionContract"""

    def test_contract_exists(self):
        """Contract must exist"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        assert contract is not None
        assert contract.protocol_version == "1.0"

    def test_contract_defines_capability_set(self):
        """Contract must define capability set"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read", "fs:write"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        assert "fs:read" in contract.capability_set
        assert "fs:write" in contract.capability_set

    def test_contract_defines_execution_domain(self):
        """Contract must define execution domain"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.SANDBOXED,
            resource_limits={},
            deterministic_seed=42
        )

        assert contract.execution_domain == ExecutionDomain.SANDBOXED

    def test_contract_defines_tenant_context(self):
        """Contract must define tenant context"""
        contract = ExecutionContract.create(
            tenant_id="tenant_123",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        assert contract.tenant_id == "tenant_123"

    def test_contract_defines_resource_limits(self):
        """Contract must define resource limits"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={"memory_mb": 512, "cpu_seconds": 60},
            deterministic_seed=42
        )

        assert contract.resource_limits["memory_mb"] == 512
        assert contract.resource_limits["cpu_seconds"] == 60

    def test_contract_defines_deterministic_seed(self):
        """Contract must define deterministic seed"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=12345
        )

        assert contract.deterministic_seed == 12345

    def test_contract_validation(self):
        """Contract must validate"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        assert contract.validate() == True

    def test_contract_hash_verification(self):
        """Contract hash must be verifiable"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        # Hash must be SHA256
        assert len(contract.contract_hash) == 64

    def test_contract_deterministic_id(self):
        """Contract ID must be deterministic"""
        contract1 = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        contract2 = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        assert contract1.contract_id == contract2.contract_id


class TestDeterministicRuntimeAPISpecification:
    """Specification tests for DeterministicRuntimeAPI"""

    def test_api_exists(self):
        """API must exist"""
        api = DeterministicRuntimeAPI()
        assert api is not None
        assert api.PROTOCOL_VERSION == "1.0"

    def test_register_function(self):
        """API must register functions"""
        api = DeterministicRuntimeAPI()

        def test_func(x: int) -> int:
            return x * 2

        result = api.register_function(
            name="double",
            func=test_func,
            required_capabilities=["math:basic"]
        )

        assert result == True

    def test_create_contract(self):
        """API must create contracts"""
        api = DeterministicRuntimeAPI()

        contract = api.create_contract(
            tenant_id="tenant_1",
            capability_set=["math:basic"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        assert contract is not None
        assert contract.tenant_id == "tenant_1"

    @pytest.mark.asyncio
    async def test_call_contract_bound(self):
        """All runtime calls must be contract-bound"""
        api = DeterministicRuntimeAPI()

        def test_func(x: int) -> int:
            return x * 2

        api.register_function(
            name="double",
            func=test_func,
            required_capabilities=["math:basic"]
        )

        contract = api.create_contract(
            tenant_id="tenant_1",
            capability_set=["math:basic"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        result = await api.call(
            contract_id=contract.contract_id,
            function_name="double",
            arguments={"x": 21}
        )

        assert result.success == True
        assert result.output == 42

    @pytest.mark.asyncio
    async def test_call_without_contract_fails(self):
        """Call without contract must fail"""
        api = DeterministicRuntimeAPI()

        def test_func(x: int) -> int:
            return x * 2

        api.register_function(
            name="double",
            func=test_func,
            required_capabilities=[]
        )

        with pytest.raises(ValueError):
            await api.call(
                contract_id="nonexistent",
                function_name="double",
                arguments={"x": 21}
            )

    @pytest.mark.asyncio
    async def test_call_missing_capability_fails(self):
        """Call with missing capability must fail"""
        api = DeterministicRuntimeAPI()

        def test_func(x: int) -> int:
            return x * 2

        api.register_function(
            name="double",
            func=test_func,
            required_capabilities=["math:basic"]
        )

        # Contract without required capability
        contract = api.create_contract(
            tenant_id="tenant_1",
            capability_set=[],  # Missing math:basic
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        with pytest.raises(PermissionError):
            await api.call(
                contract_id=contract.contract_id,
                function_name="double",
                arguments={"x": 21}
            )

    @pytest.mark.asyncio
    async def test_no_implicit_runtime_behavior(self):
        """No implicit runtime behavior allowed"""
        api = DeterministicRuntimeAPI()

        # Try to call without registering function
        contract = api.create_contract(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        with pytest.raises(ValueError):
            await api.call(
                contract_id=contract.contract_id,
                function_name="nonexistent",
                arguments={}
            )

    @pytest.mark.asyncio
    async def test_deterministic_execution(self):
        """Execution must be deterministic"""
        api = DeterministicRuntimeAPI()

        def test_func(x: int) -> int:
            return x * 2

        api.register_function(
            name="double",
            func=test_func,
            required_capabilities=[]
        )

        contract = api.create_contract(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        # Execute twice
        result1 = await api.call(
            contract_id=contract.contract_id,
            function_name="double",
            arguments={"x": 21}
        )

        result2 = await api.call(
            contract_id=contract.contract_id,
            function_name="double",
            arguments={"x": 21}
        )

        # Results must be identical
        assert result1.output == result2.output
        assert result1.result_hash == result2.result_hash

    @pytest.mark.asyncio
    async def test_replay_verifiable(self):
        """Execution must be replay-verifiable"""
        api = DeterministicRuntimeAPI()

        def test_func(x: int) -> int:
            return x * 2

        api.register_function(
            name="double",
            func=test_func,
            required_capabilities=[]
        )

        contract = api.create_contract(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={},
            deterministic_seed=42
        )

        # Execute and get hash
        result = await api.call(
            contract_id=contract.contract_id,
            function_name="double",
            arguments={"x": 21}
        )

        # Verify replay
        is_valid = api.verify_replay(
            contract_id=contract.contract_id,
            function_name="double",
            arguments={"x": 21},
            expected_hash=result.result_hash
        )

        assert is_valid == True


class TestRuntimeContractIntegration:
    """Integration tests for Runtime Contract"""

    @pytest.mark.asyncio
    async def test_full_contract_workflow(self):
        """Full contract workflow"""
        api = DeterministicRuntimeAPI()

        # 1. Register function
        def compute(x: int, y: int) -> int:
            return x + y

        api.register_function(
            name="add",
            func=compute,
            required_capabilities=["math:basic"]
        )

        # 2. Create contract
        contract = api.create_contract(
            tenant_id="tenant_1",
            capability_set=["math:basic"],
            execution_domain=ExecutionDomain.LOCAL,
            resource_limits={"memory_mb": 256},
            deterministic_seed=42
        )

        # 3. Validate contract
        assert contract.validate() == True

        # 4. Execute call
        result = await api.call(
            contract_id=contract.contract_id,
            function_name="add",
            arguments={"x": 10, "y": 20}
        )

        # 5. Verify result
        assert result.success == True
        assert result.output == 30

        # 6. Verify replay
        is_valid = api.verify_replay(
            contract_id=contract.contract_id,
            function_name="add",
            arguments={"x": 10, "y": 20},
            expected_hash=result.result_hash
        )

        assert is_valid == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
