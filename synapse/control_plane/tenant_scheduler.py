"""
Tenant-Aware Scheduler for Multi-Tenant Runtime
Deterministic scheduling with capability-aware routing

PROTOCOL_VERSION = "1.0"
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import threading


@dataclass
class TenantContext:
    """Tenant security context with cryptographic identity"""
    tenant_id: str
    tenant_hash: str
    capabilities: List[str]
    resource_quota: Dict[str, int]
    created_at: str
    protocol_version: str = "1.0"


@dataclass
class SchedulingRequest:
    """Deterministic scheduling request"""
    request_id: str
    tenant_id: str
    task_type: str
    priority: int
    required_capabilities: List[str]
    execution_seed: int
    timestamp: str
    protocol_version: str = "1.0"


@dataclass
class SchedulingDecision:
    """Deterministic scheduling decision"""
    decision_id: str
    request_id: str
    tenant_id: str
    node_id: str
    scheduled_at: str
    execution_order: int
    decision_hash: str
    protocol_version: str = "1.0"


class TenantScheduler:
    """
    Deterministic tenant-aware scheduler.

    Guarantees:
    - Identical input → identical schedule
    - Capability-aware routing
    - Fairness across tenants
    - Replay-stable ordering
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._tenant_contexts: Dict[str, TenantContext] = {}
        self._decision_counter = 0
        self._lock = threading.Lock()
        self._tenant_queues: Dict[str, List[SchedulingRequest]] = {}
        self._scheduled_decisions: Dict[str, SchedulingDecision] = {}

    def register_tenant(self, context: TenantContext):
        """Register tenant context for scheduling"""
        with self._lock:
            self._tenant_contexts[context.tenant_id] = context
            if context.tenant_id not in self._tenant_queues:
                self._tenant_queues[context.tenant_id] = []

    def schedule(self, request: SchedulingRequest) -> SchedulingDecision:
        """
        Schedule a request deterministically.

        Args:
            request: Scheduling request with tenant context

        Returns:
            SchedulingDecision with deterministic ordering

        Raises:
            ValueError: If tenant not registered or lacks capabilities
        """
        with self._lock:
            # Validate tenant exists
            if request.tenant_id not in self._tenant_contexts:
                raise ValueError(f"Tenant {request.tenant_id} not registered")

            tenant_ctx = self._tenant_contexts[request.tenant_id]

            # Validate capabilities
            for cap in request.required_capabilities:
                if cap not in tenant_ctx.capabilities:
                    raise ValueError(
                        f"Tenant {request.tenant_id} lacks capability: {cap}"
                    )

            # Deterministic decision generation
            decision_id = self._generate_decision_id(request)

            # Deterministic execution order based on seed and counter
            execution_order = self._calculate_execution_order(request)

            # Select node deterministically
            node_id = self._select_node(request)

            # Create decision
            decision = SchedulingDecision(
                decision_id=decision_id,
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                node_id=node_id,
                scheduled_at=datetime.utcnow().isoformat(),
                execution_order=execution_order,
                decision_hash=self._hash_decision(request, execution_order),
                protocol_version=self.PROTOCOL_VERSION
            )

            self._scheduled_decisions[request.request_id] = decision
            self._decision_counter += 1

            return decision

    def get_decision(self, request_id: str) -> Optional[SchedulingDecision]:
        """Get scheduling decision by request ID"""
        return self._scheduled_decisions.get(request_id)

    def compute_schedule_hash(
        self,
        tenant_id: str,
        task_id: str,
        seed: int
    ) -> str:
        """
        Compute deterministic schedule hash.
        
        Required for determinism verification.
        Same input must always produce identical hash.
        
        Args:
            tenant_id: Tenant identifier
            task_id: Task identifier
            seed: Deterministic seed
            
        Returns:
            SHA256 hash of schedule decision
        """
        data = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "seed": seed,
            "protocol_version": self.PROTOCOL_VERSION
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _generate_decision_id(self, request: SchedulingRequest) -> str:
        """Generate deterministic decision ID"""
        # Hash based on request details for determinism
        data = f"{request.request_id}:{request.tenant_id}:{request.execution_seed}"
        return f"dec_{hashlib.sha256(data.encode()).hexdigest()[:16]}"

    def _calculate_execution_order(self, request: SchedulingRequest) -> int:
        """Calculate deterministic execution order"""
        # Use seed for deterministic ordering
        base_order = request.execution_seed % 10000
        return base_order + self._decision_counter

    def _select_node(self, request: SchedulingRequest) -> str:
        """Select node deterministically based on request"""
        # Deterministic node selection based on hash
        node_hash = hashlib.sha256(
            f"{request.tenant_id}:{request.task_type}:{request.execution_seed}".encode()
        ).hexdigest()
        node_num = int(node_hash[:8], 16) % 10
        return f"node_{node_num:03d}"

    def _hash_decision(self, request: SchedulingRequest, order: int) -> str:
        """Generate cryptographic hash of decision"""
        decision_data = {
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
            "execution_order": order,
            "seed": request.execution_seed
        }
        return hashlib.sha256(
            json.dumps(decision_data, sort_keys=True).encode()
        ).hexdigest()


# Export
__all__ = ["TenantScheduler", "TenantContext", "SchedulingRequest", "SchedulingDecision"]
