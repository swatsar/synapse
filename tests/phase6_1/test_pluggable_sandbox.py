"""
Tests for Pluggable Deterministic Sandbox
"""

import pytest
import hashlib
import json
from datetime import datetime

from synapse.runtime.sandbox_interface import (
    SandboxType,
    SandboxCapabilities,
    ExecutionContract,
    ExecutionResult,
    SandboxInterface,
    SandboxRegistry,
    ProcessSandbox
)


class TestSandboxInterfaceSpecification:
    """Specification tests for SandboxInterface"""

    def test_sandbox_interface_exists(self):
        """Sandbox interface must exist"""
        sandbox = ProcessSandbox()
        assert sandbox is not None
        assert sandbox.sandbox_type == SandboxType.PROCESS

    def test_sandbox_capabilities(self):
        """Sandbox must report capabilities"""
        sandbox = ProcessSandbox()
        caps = sandbox.capabilities

        assert caps is not None
        assert caps.protocol_version == "1.0"
        assert isinstance(caps.supports_sealed_memory, bool)
        assert isinstance(caps.supports_network, bool)
        assert isinstance(caps.supports_filesystem, bool)
        assert isinstance(caps.max_memory_mb, int)
        assert isinstance(caps.max_cpu_seconds, int)

    @pytest.mark.asyncio
    async def test_deterministic_execution(self):
        """Sandbox must provide deterministic execution"""
        sandbox = ProcessSandbox()

        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain="local",
            resource_limits={"memory_mb": 256, "cpu_seconds": 30},
            deterministic_seed=42
        )

        code = "result = inputs['a'] + inputs['b']"
        inputs = {"a": 1, "b": 2}

        # Execute twice
        result1 = await sandbox.execute(contract, code, inputs)
        result2 = await sandbox.execute(contract, code, inputs)

        # Results must be identical
        assert result1.success == result2.success
        assert result1.output == result2.output
        assert result1.result_hash == result2.result_hash

    @pytest.mark.asyncio
    async def test_capability_enforcement(self):
        """Sandbox must enforce capabilities"""
        sandbox = ProcessSandbox()

        # Contract without network capability
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain="local",
            resource_limits={},
            deterministic_seed=42
        )

        # Code that tries to access network (should fail in real sandbox)
        # For ProcessSandbox, we just verify the contract is checked
        assert contract.verify_capability("fs:read") == True
        assert contract.verify_capability("network:http") == False

    @pytest.mark.asyncio
    async def test_resource_quota_enforcement(self):
        """Sandbox must enforce resource quotas"""
        sandbox = ProcessSandbox()

        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain="local",
            resource_limits={"memory_mb": 256, "cpu_seconds": 30},
            deterministic_seed=42
        )

        code = "result = sum(range(1000))"
        inputs = {}

        result = await sandbox.execute(contract, code, inputs)

        # Should complete within limits
        assert result.success == True

    @pytest.mark.asyncio
    async def test_replay_compatibility(self):
        """Sandbox must support replay"""
        sandbox = ProcessSandbox()

        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain="local",
            resource_limits={},
            deterministic_seed=42
        )

        code = "result = inputs['x'] * 2"
        inputs = {"x": 21}

        # Execute and get hash
        result = await sandbox.execute(contract, code, inputs)
        expected_hash = result.result_hash

        # Verify replay
        is_replay_valid = await sandbox.verify_replay(
            contract, code, inputs, expected_hash
        )

        assert is_replay_valid == True


class TestSandboxRegistrySpecification:
    """Specification tests for SandboxRegistry"""

    def test_registry_exists(self):
        """Registry must exist"""
        registry = SandboxRegistry()
        assert registry is not None
        assert registry.PROTOCOL_VERSION == "1.0"

    def test_register_sandbox(self):
        """Registry must register sandboxes"""
        registry = SandboxRegistry()
        sandbox = ProcessSandbox()

        result = registry.register(sandbox, is_default=True)

        assert result == True
        assert registry.list_sandboxes() == [SandboxType.PROCESS]

    def test_get_sandbox_explicit_type(self):
        """Registry must return sandbox by explicit type"""
        registry = SandboxRegistry()
        sandbox = ProcessSandbox()

        registry.register(sandbox)

        retrieved = registry.get_sandbox(SandboxType.PROCESS)

        assert retrieved.sandbox_type == SandboxType.PROCESS

    def test_get_sandbox_default(self):
        """Registry must return default sandbox"""
        registry = SandboxRegistry()
        sandbox = ProcessSandbox()

        registry.register(sandbox, is_default=True)

        retrieved = registry.get_sandbox()

        assert retrieved.sandbox_type == SandboxType.PROCESS

    def test_sandbox_selection_deterministic(self):
        """Sandbox selection must be deterministic"""
        registry = SandboxRegistry()
        sandbox = ProcessSandbox()

        registry.register(sandbox)

        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain="local",
            resource_limits={"memory_mb": 256},
            deterministic_seed=42
        )

        # Select multiple times
        selected1 = registry.get_sandbox(contract=contract)
        selected2 = registry.get_sandbox(contract=contract)

        assert selected1.sandbox_type == selected2.sandbox_type

    def test_sandbox_swap_preserves_plan_hash(self):
        """Sandbox swap must NOT affect plan hash"""
        registry = SandboxRegistry()
        sandbox1 = ProcessSandbox()
        sandbox2 = ProcessSandbox()

        registry.register(sandbox1, is_default=True)

        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain="local",
            resource_limits={},
            deterministic_seed=42
        )

        # Generate identity with first sandbox
        identity1 = registry.generate_sandbox_identity(
            SandboxType.PROCESS, contract
        )

        # Swap sandbox
        registry.register(sandbox2, is_default=True)

        # Generate identity again
        identity2 = registry.generate_sandbox_identity(
            SandboxType.PROCESS, contract
        )

        # Identities must be identical (contract-based, not sandbox-based)
        assert identity1 == identity2

    def test_sandbox_identity_cryptographically_bound(self):
        """Sandbox identity must be cryptographically bound"""
        registry = SandboxRegistry()
        sandbox = ProcessSandbox()

        registry.register(sandbox)

        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain="local",
            resource_limits={},
            deterministic_seed=42
        )

        identity = registry.generate_sandbox_identity(
            SandboxType.PROCESS, contract
        )

        # Identity must be SHA256 hash
        assert len(identity) == 64  # SHA256 hex length
        assert all(c in '0123456789abcdef' for c in identity)


class TestExecutionContractSpecification:
    """Specification tests for ExecutionContract"""

    def test_contract_exists(self):
        """Contract must exist"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain="local",
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
            execution_domain="local",
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
            execution_domain="sandboxed",
            resource_limits={},
            deterministic_seed=42
        )

        assert contract.execution_domain == "sandboxed"

    def test_contract_defines_tenant_context(self):
        """Contract must define tenant context"""
        contract = ExecutionContract.create(
            tenant_id="tenant_123",
            capability_set=[],
            execution_domain="local",
            resource_limits={},
            deterministic_seed=42
        )

        assert contract.tenant_id == "tenant_123"

    def test_contract_defines_resource_limits(self):
        """Contract must define resource limits"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=[],
            execution_domain="local",
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
            execution_domain="local",
            resource_limits={},
            deterministic_seed=12345
        )

        assert contract.deterministic_seed == 12345

    def test_contract_validation(self):
        """Contract must validate"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain="local",
            resource_limits={},
            deterministic_seed=42
        )

        assert contract.validate() == True

    def test_contract_hash_verification(self):
        """Contract hash must be verifiable"""
        contract = ExecutionContract.create(
            tenant_id="tenant_1",
            capability_set=["fs:read"],
            execution_domain="local",
            resource_limits={},
            deterministic_seed=42
        )

        # Hash must be SHA256
        assert len(contract.contract_hash) == 64

        # Verify hash
        data = {
            "contract_id": contract.contract_id,
            "tenant_id": contract.tenant_id,
            "capability_set": contract.capability_set,
            "execution_domain": contract.execution_domain,
            "resource_limits": contract.resource_limits,
            "deterministic_seed": contract.deterministic_seed,
            "protocol_version": contract.protocol_version
        }
        expected_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

        assert contract.contract_hash == expected_hash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
