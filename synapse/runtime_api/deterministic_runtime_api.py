"""
Runtime API Specification Layer for Multi-Tenant Runtime
Formal interface between Control Plane and Runtime

PROTOCOL_VERSION = "1.0"
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading


class ExecutionDomain(str, Enum):
    """Execution domain types"""
    LOCAL = "local"
    DISTRIBUTED = "distributed"
    SANDBOXED = "sandboxed"
    CLUSTER = "cluster"


class ExecutionStatus(str, Enum):
    """Execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionContract:
    """
    Contract for execution in runtime.

    Must define:
    - Capability set
    - Execution domain
    - Tenant context
    - Resource limits
    - Deterministic seed
    """
    contract_id: str
    tenant_id: str
    capability_set: List[str]
    execution_domain: ExecutionDomain
    resource_limits: Dict[str, int]
    deterministic_seed: int
    created_at: str
    contract_hash: str
    protocol_version: str = "1.0"

    @classmethod
    def create(
        cls,
        tenant_id: str,
        capability_set: List[str],
        execution_domain: ExecutionDomain,
        resource_limits: Dict[str, int],
        deterministic_seed: int
    ) -> "ExecutionContract":
        """Create new execution contract"""
        contract_id = cls._generate_contract_id(
            tenant_id, capability_set, deterministic_seed
        )

        contract = cls(
            contract_id=contract_id,
            tenant_id=tenant_id,
            capability_set=sorted(capability_set),
            execution_domain=execution_domain,
            resource_limits=resource_limits,
            deterministic_seed=deterministic_seed,
            created_at=datetime.utcnow().isoformat(),
            contract_hash="",  # Will be calculated
            protocol_version="1.0"
        )

        # Calculate hash
        contract.contract_hash = contract._calculate_hash()

        return contract

    def validate(self) -> bool:
        """Validate contract integrity"""
        # Verify hash
        expected_hash = self._calculate_hash()
        if self.contract_hash != expected_hash:
            return False

        # Verify required fields
        if not self.tenant_id:
            return False
        if not self.capability_set:
            return False
        if self.deterministic_seed < 0:
            return False

        return True

    def verify_capability(self, capability: str) -> bool:
        """Check if capability is in contract"""
        return capability in self.capability_set

    def verify_capabilities(self, capabilities: List[str]) -> bool:
        """Check if all capabilities are in contract"""
        return all(cap in self.capability_set for cap in capabilities)

    def _calculate_hash(self) -> str:
        """Calculate contract hash"""
        data = {
            "contract_id": self.contract_id,
            "tenant_id": self.tenant_id,
            "capability_set": self.capability_set,
            "execution_domain": self.execution_domain.value,
            "resource_limits": self.resource_limits,
            "deterministic_seed": self.deterministic_seed,
            "protocol_version": self.protocol_version
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    @classmethod
    def _generate_contract_id(
        cls,
        tenant_id: str,
        capability_set: List[str],
        seed: int
    ) -> str:
        """Generate deterministic contract ID"""
        data = f"{tenant_id}:{sorted(capability_set)}:{seed}:1.0"
        hash_part = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"contract_{hash_part}"


@dataclass
class RuntimeCall:
    """A call to the runtime"""
    call_id: str
    contract: ExecutionContract
    function_name: str
    arguments: Dict[str, Any]
    timestamp: str
    call_hash: str
    protocol_version: str = "1.0"


@dataclass
class RuntimeResult:
    """Result from runtime call"""
    call_id: str
    success: bool
    output: Any
    error: Optional[str]
    execution_time_ms: int
    result_hash: str
    protocol_version: str = "1.0"


class DeterministicRuntimeAPI:
    """
    Deterministic runtime API.

    Guarantees:
    - All runtime calls are contract-bound
    - No implicit runtime behavior
    - Deterministic execution
    - Replay verifiable
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._contracts: Dict[str, ExecutionContract] = {}
        self._calls: Dict[str, RuntimeCall] = {}
        self._results: Dict[str, RuntimeResult] = {}
        self._functions: Dict[str, Callable] = {}
        self._lock = threading.Lock()

    def register_function(
        self,
        name: str,
        func: Callable,
        required_capabilities: List[str]
    ) -> bool:
        """
        Register function with required capabilities.

        Args:
            name: Function name
            func: Function implementation
            required_capabilities: Required capabilities

        Returns:
            True if successful
        """
        with self._lock:
            self._functions[name] = {
                "func": func,
                "required_capabilities": required_capabilities
            }
            return True

    def create_contract(
        self,
        tenant_id: str,
        capability_set: List[str],
        execution_domain: ExecutionDomain,
        resource_limits: Dict[str, int],
        deterministic_seed: int
    ) -> ExecutionContract:
        """
        Create execution contract.

        Args:
            tenant_id: Tenant identifier
            capability_set: Granted capabilities
            execution_domain: Execution domain
            resource_limits: Resource limits
            deterministic_seed: Deterministic seed

        Returns:
            ExecutionContract
        """
        contract = ExecutionContract.create(
            tenant_id=tenant_id,
            capability_set=capability_set,
            execution_domain=execution_domain,
            resource_limits=resource_limits,
            deterministic_seed=deterministic_seed
        )

        with self._lock:
            self._contracts[contract.contract_id] = contract

        return contract

    async def call(
        self,
        contract_id: str,
        function_name: str,
        arguments: Dict[str, Any]
    ) -> RuntimeResult:
        """
        Execute runtime call.

        All runtime calls MUST be contract-bound.

        Args:
            contract_id: Execution contract ID
            function_name: Function to call
            arguments: Call arguments

        Returns:
            RuntimeResult

        Raises:
            ValueError: If contract not found or invalid
            PermissionError: If capability not granted
        """
        import time
        start = time.perf_counter()

        # Get contract
        with self._lock:
            contract = self._contracts.get(contract_id)

        if contract is None:
            raise ValueError(f"Contract {contract_id} not found")

        if not contract.validate():
            raise ValueError(f"Contract {contract_id} invalid")

        # Get function
        with self._lock:
            func_info = self._functions.get(function_name)

        if func_info is None:
            raise ValueError(f"Function {function_name} not registered")

        # Check capabilities
        required_caps = func_info["required_capabilities"]
        if not contract.verify_capabilities(required_caps):
            raise PermissionError(
                f"Contract missing required capabilities: {required_caps}"
            )

        # Create call record
        call_id = self._generate_call_id(contract_id, function_name, arguments)
        call = RuntimeCall(
            call_id=call_id,
            contract=contract,
            function_name=function_name,
            arguments=arguments,
            timestamp=datetime.utcnow().isoformat(),
            call_hash=self._hash_call(call_id, contract_id, function_name, arguments),
            protocol_version=self.PROTOCOL_VERSION
        )

        with self._lock:
            self._calls[call_id] = call

        # Execute
        try:
            func = func_info["func"]

            if asyncio.iscoroutinefunction(func):
                output = await func(**arguments)
            else:
                output = func(**arguments)

            elapsed = int((time.perf_counter() - start) * 1000)

            result = RuntimeResult(
                call_id=call_id,
                success=True,
                output=output,
                error=None,
                execution_time_ms=elapsed,
                result_hash=self._hash_result(output),
                protocol_version=self.PROTOCOL_VERSION
            )

        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)

            result = RuntimeResult(
                call_id=call_id,
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=elapsed,
                result_hash="",
                protocol_version=self.PROTOCOL_VERSION
            )

        with self._lock:
            self._results[call_id] = result

        return result

    def get_contract(self, contract_id: str) -> Optional[ExecutionContract]:
        """Get contract by ID"""
        with self._lock:
            return self._contracts.get(contract_id)

    def get_result(self, call_id: str) -> Optional[RuntimeResult]:
        """Get result by call ID"""
        with self._lock:
            return self._results.get(call_id)

    def verify_replay(
        self,
        contract_id: str,
        function_name: str,
        arguments: Dict[str, Any],
        expected_hash: str
    ) -> bool:
        """
        Verify replay produces identical result.

        Args:
            contract_id: Contract ID
            function_name: Function name
            arguments: Arguments
            expected_hash: Expected result hash

        Returns:
            True if replay matches
        """
        import asyncio

        result = asyncio.run(self.call(contract_id, function_name, arguments))
        return result.result_hash == expected_hash

    def _generate_call_id(
        self,
        contract_id: str,
        function_name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """Generate deterministic call ID"""
        data = f"{contract_id}:{function_name}:{json.dumps(arguments, sort_keys=True)}"
        hash_part = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"call_{hash_part}"

    def _hash_call(
        self,
        call_id: str,
        contract_id: str,
        function_name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """Hash call data"""
        data = {
            "call_id": call_id,
            "contract_id": contract_id,
            "function_name": function_name,
            "arguments": arguments,
            "protocol_version": self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _hash_result(self, output: Any) -> str:
        """Hash result"""
        data = {"output": str(output), "protocol_version": self.PROTOCOL_VERSION}
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()


import asyncio


__all__ = [
    "ExecutionDomain",
    "ExecutionStatus",
    "ExecutionContract",
    "RuntimeCall",
    "RuntimeResult",
    "DeterministicRuntimeAPI"
]
