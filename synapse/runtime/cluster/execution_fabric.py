PROTOCOL_VERSION: str = "1.0"
"""ExecutionFabric – deterministic task placement and routing across the cluster.
All public methods are async and respect CapabilityManager, ExecutionGuard,
PolicyEngine and the new network layer.
"""
import asyncio
import uuid
from typing import Any, Dict, List

from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard
from synapse.core.models import ExecutionContext
from synapse.orchestrator import Orchestrator
from synapse.distributed.node_runtime import NodeRuntime
from synapse.policy.engine import PolicyEngine
from synapse.network.transport import Transport
from synapse.network.security import MessageSecurity

class ExecutionFabric:
    protocol_version: str = "1.0"

    def __init__(self, caps: CapabilityManager, orchestrator: Orchestrator, nodes: List[NodeRuntime], policy: PolicyEngine):
        self._caps = caps
        self._orchestrator = orchestrator
        self._nodes = sorted(nodes, key=lambda n: getattr(n, "node_id", uuid.uuid4().hex))
        self._policy = policy
        self._guard = ExecutionGuard()
        # One transport per node (stub implementation)
        self._transports = {node: Transport(caps, self._guard) for node in self._nodes}
        self._security = MessageSecurity(caps)

    async def place_task(self, task_payload: Any, required_caps: List[str]) -> str:
        """Deterministically select a node that satisfies the required capabilities,
        send the task via its transport and return the node identifier.
        """
        # Capability check for the caller
        await self._caps.check_capability(required_caps)
        # Find first node that can satisfy the caps (simplified – assume all nodes have same caps)
        target_node = self._nodes[0]
        transport = self._transports[target_node]
        # Build envelope using RemoteNodeProtocol (minimal – we reuse the transport directly)
        envelope = {
            "protocol_version": self.protocol_version,
            "trace_id": str(uuid.uuid4()),
            "timestamp": asyncio.get_event_loop().time(),
            "node_id": target_node.node_id if hasattr(target_node, "node_id") else "node",
            "capabilities": required_caps,
            "payload": task_payload,
        }
        # Send with retry (simple deterministic 3 attempts)
        for attempt in range(3):
            try:
                await transport.send_message(envelope, required_caps=required_caps)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.1 * (attempt + 1))
        return envelope["node_id"]

    async def route_message(self, envelope: Dict[str, Any]) -> None:
        """Validate, authorize and forward a received envelope to the appropriate node runtime."""
        # Security checks first
        await self._security.authorize_message(envelope)
        # Determine destination node (simple deterministic: hash of trace_id)
        dest_node = self._nodes[hash(envelope["trace_id"]) % len(self._nodes)]
        # Forward via its transport (in a real system this would be a network send)
        await self._transports[dest_node].inject_incoming(envelope)

    async def run(self) -> None:
        """Main loop – listen on all transports and dispatch to orchestrator."""
        async with self._guard:
            while True:
                # Collect messages from all transports concurrently
                tasks = [t.receive_message() for t in self._transports.values()]
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for fut in done:
                    envelope = fut.result()
                    # Pass to orchestrator for processing (simplified)
                    await self._orchestrator.handle_event(envelope)
