"""
Pluggable Deterministic Sandbox for Multi-Tenant Runtime
Sandbox interface and registry for pluggable backends

PROTOCOL_VERSION = "1.0"
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Protocol, Type
from dataclasses import dataclass, field
from enum import Enum
import threading


class SandboxType(str, Enum):
    """Types of sandbox backends"""
    PROCESS = "process"
    CONTAINER = "container"
    WASM = "wasm"
    VM = "vm"


@dataclass
class SandboxCapabilities:
    """Capabilities of a sandbox backend"""
    supports_sealed_memory: bool
    supports_network: bool
    supports_filesystem: bool
    supports_capabilities: bool
    max_memory_mb: int
    max_cpu_seconds: int
    protocol_version: str = "1.0"


@dataclass
class ExecutionContract:
    """Contract for execution in sandbox"""
    contract_id: str
    tenant_id: str
    capability_set: List[str]
    execution_domain: str
    resource_limits: Dict[str, int]
    deterministic_seed: int
    timestamp: str
    contract_hash: str
    protocol_version: str = "1.0"


@dataclass
class ExecutionResult:
    """Result of sandbox execution"""
    success: bool
    output: Any
    error: Optional[str]
    execution_time_ms: int
    memory_used_mb: int
    result_hash: str
    protocol_version: str = "1.0"


class SandboxInterface(Protocol):
    """
    Interface that all sandbox backends must implement.

    Required properties:
    - Deterministic execution
    - Capability enforcement
    - Resource quota enforcement
    - Sealed memory support
    - Replay compatibility
    """

    @property
    def sandbox_type(self) -> SandboxType:
        """Return the type of sandbox"""
        ...

    @property
    def capabilities(self) -> SandboxCapabilities:
        """Return sandbox capabilities"""
        ...

    async def execute(
        self,
        contract: ExecutionContract,
        code: str,
        inputs: Dict[str, Any]
    ) -> ExecutionResult:
        """
        Execute code in sandbox.

        Args:
            contract: Execution contract with capabilities and limits
            code: Code to execute
            inputs: Input data

        Returns:
            ExecutionResult with output and hash
        """
        ...

    async def verify_replay(
        self,
        contract: ExecutionContract,
        code: str,
        inputs: Dict[str, Any],
        expected_hash: str
    ) -> bool:
        """
        Verify replay produces identical result.

        Args:
            contract: Execution contract
            code: Code to execute
            inputs: Input data
            expected_hash: Expected result hash

        Returns:
            True if replay matches
        """
        ...


class SandboxRegistry:
    """
    Registry for pluggable sandbox backends.

    Guarantees:
    - Sandbox selection deterministic
    - Sandbox swap does NOT affect plan hash
    - Sandbox identity cryptographically bound to execution
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._sandboxes: Dict[SandboxType, SandboxInterface] = {}
        self._default_type: Optional[SandboxType] = None
        self._lock = threading.Lock()

    def register(
        self,
        sandbox: SandboxInterface,
        is_default: bool = False
    ) -> bool:
        """
        Register sandbox backend.

        Args:
            sandbox: Sandbox implementation
            is_default: Set as default sandbox

        Returns:
            True if successful
        """
        with self._lock:
            self._sandboxes[sandbox.sandbox_type] = sandbox

            if is_default or self._default_type is None:
                self._default_type = sandbox.sandbox_type

            return True

    def get_sandbox(
        self,
        sandbox_type: Optional[SandboxType] = None,
        contract: Optional[ExecutionContract] = None
    ) -> SandboxInterface:
        """
        Get sandbox for execution.

        Selection is deterministic based on:
        1. Explicit sandbox_type if provided
        2. Contract requirements if provided
        3. Default sandbox

        Args:
            sandbox_type: Explicit sandbox type
            contract: Execution contract for requirements-based selection

        Returns:
            SandboxInterface implementation

        Raises:
            ValueError: If no suitable sandbox found
        """
        with self._lock:
            # Explicit type
            if sandbox_type is not None:
                if sandbox_type not in self._sandboxes:
                    raise ValueError(f"Sandbox type {sandbox_type} not registered")
                return self._sandboxes[sandbox_type]

            # Contract-based selection
            if contract is not None:
                selected = self._select_for_contract(contract)
                if selected is not None:
                    return selected

            # Default
            if self._default_type is None:
                raise ValueError("No sandbox registered")

            return self._sandboxes[self._default_type]

    def list_sandboxes(self) -> List[SandboxType]:
        """List registered sandbox types"""
        with self._lock:
            return list(self._sandboxes.keys())

    def get_capabilities(
        self,
        sandbox_type: Optional[SandboxType] = None
    ) -> SandboxCapabilities:
        """Get capabilities of sandbox"""
        sandbox = self.get_sandbox(sandbox_type)
        return sandbox.capabilities

    def _select_for_contract(self, contract: ExecutionContract) -> Optional[SandboxInterface]:
        """
        Deterministically select sandbox based on contract.

        Selection algorithm:
        1. Check resource requirements
        2. Check capability requirements
        3. Select first matching sandbox (deterministic order)
        """
        # Sort sandbox types for deterministic selection
        sorted_types = sorted(self._sandboxes.keys(), key=lambda t: t.value)

        for stype in sorted_types:
            sandbox = self._sandboxes[stype]
            caps = sandbox.capabilities

            # Check resource limits
            if contract.resource_limits.get("memory_mb", 0) > caps.max_memory_mb:
                continue
            if contract.resource_limits.get("cpu_seconds", 0) > caps.max_cpu_seconds:
                continue

            # Check capabilities
            if "network:http" in contract.capability_set and not caps.supports_network:
                continue
            if "fs:write" in contract.capability_set and not caps.supports_filesystem:
                continue

            return sandbox

        return None

    def generate_sandbox_identity(
        self,
        sandbox_type: SandboxType,
        contract: ExecutionContract
    ) -> str:
        """
        Generate cryptographic identity for sandbox execution.

        Args:
            sandbox_type: Type of sandbox
            contract: Execution contract

        Returns:
            SHA256 hash binding sandbox to execution
        """
        data = {
            "sandbox_type": sandbox_type.value,
            "contract_id": contract.contract_id,
            "tenant_id": contract.tenant_id,
            "seed": contract.deterministic_seed,
            "protocol_version": self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


# Default sandbox implementation for testing
class ProcessSandbox:
    """Simple process-based sandbox for testing"""

    def __init__(self):
        self._sandbox_type = SandboxType.PROCESS
        self._capabilities = SandboxCapabilities(
            supports_sealed_memory=False,
            supports_network=False,
            supports_filesystem=True,
            supports_capabilities=True,
            max_memory_mb=512,
            max_cpu_seconds=60,
            protocol_version="1.0"
        )

    @property
    def sandbox_type(self) -> SandboxType:
        return self._sandbox_type

    @property
    def capabilities(self) -> SandboxCapabilities:
        return self._capabilities

    async def execute(
        self,
        contract: ExecutionContract,
        code: str,
        inputs: Dict[str, Any]
    ) -> ExecutionResult:
        """Execute code in process sandbox"""
        import time
        start = time.perf_counter()

        try:
            # Create execution namespace
            namespace = {"inputs": inputs, "result": None}

            # Execute code
            exec(code, namespace)  # nosec B102

            output = namespace.get("result")

            # Calculate hash
            result_hash = self._hash_result(output)

            elapsed = int((time.perf_counter() - start) * 1000)

            return ExecutionResult(
                success=True,
                output=output,
                error=None,
                execution_time_ms=elapsed,
                memory_used_mb=0,
                result_hash=result_hash,
                protocol_version="1.0"
            )

        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)

            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=elapsed,
                memory_used_mb=0,
                result_hash="",
                protocol_version="1.0"
            )

    async def verify_replay(
        self,
        contract: ExecutionContract,
        code: str,
        inputs: Dict[str, Any],
        expected_hash: str
    ) -> bool:
        """Verify replay"""
        result = await self.execute(contract, code, inputs)
        return result.result_hash == expected_hash

    def _hash_result(self, output: Any) -> str:
        """Hash execution result"""
        data = {"output": str(output), "protocol_version": "1.0"}
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


__all__ = [
    "SandboxType",
    "SandboxCapabilities",
    "ExecutionContract",
    "ExecutionResult",
    "SandboxInterface",
    "SandboxRegistry",
    "ProcessSandbox"
]
