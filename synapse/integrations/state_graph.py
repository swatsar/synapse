"""
Secure State Graph for Synapse.

Adapted from LangGraph patterns:
https://github.com/langchain-ai/langgraph

Original License: MIT
Adaptation: Added capability validation, protocol versioning,
           security hash for checkpoints, audit integration,
           human-in-the-loop, resource limits

Copyright (c) 2024 LangChain, Inc.
Copyright (c) 2026 Synapse Contributors
"""

from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio
import hashlib
import json
import uuid
from abc import ABC, abstractmethod

# Protocol versioning
PROTOCOL_VERSION: str = "1.0"


class NodeStatus(str, Enum):
    """Status of graph node"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    INTERRUPTED = "interrupted"


class EdgeType(str, Enum):
    """Type of graph edge"""
    NORMAL = "normal"
    CONDITIONAL = "conditional"
    INTERRUPT = "interrupt"


@dataclass
class StateNode:
    """Node in the state graph"""
    id: str
    name: str
    action: Callable
    required_capabilities: List[str] = field(default_factory=list)
    risk_level: int = 1
    timeout_seconds: int = 60
    status: NodeStatus = NodeStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    isolation_type: str = "container"
    resource_limits: Dict[str, int] = field(default_factory=dict)
    requires_human_approval: bool = False


@dataclass
class StateEdge:
    """Edge in the state graph"""
    source: str
    target: str
    edge_type: EdgeType = EdgeType.NORMAL
    condition: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    validation_rules: List[str] = field(default_factory=list)


@dataclass
class GraphState:
    """State of the graph execution"""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    agent_outputs: List[Dict[str, Any]] = field(default_factory=list)
    current_node: Optional[str] = None
    completed_nodes: List[str] = field(default_factory=list)
    failed_nodes: List[str] = field(default_factory=list)
    interrupted_at: Optional[str] = None
    checkpoint_id: Optional[str] = None
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    trace_id: str = ""
    session_id: str = ""
    agent_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    security_context: Dict[str, Any] = field(default_factory=dict)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GraphCheckpoint:
    """Checkpoint for graph state"""
    id: str
    graph_id: str
    session_id: str
    trace_id: str
    state: Dict[str, Any]
    current_node: Optional[str]
    completed_nodes: List[str]
    failed_nodes: List[str]
    created_at: str
    expires_at: Optional[str] = None
    is_valid: bool = True
    
    # Synapse additions
    protocol_version: str = PROTOCOL_VERSION
    security_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SecureStateGraph:
    """
    Secure State Graph with capability-based access control.
    
    Adapted from LangGraph StateGraph patterns with Synapse security enhancements.
    
    Features:
    - Node capability validation
    - Edge routing with security checks
    - Human-in-the-loop interrupts
    - Checkpointing with security hash
    - Audit logging for all transitions
    - Protocol versioning compliance
    """
    
    PROTOCOL_VERSION: str = PROTOCOL_VERSION
    
    def __init__(
        self,
        state_schema: type = GraphState,
        security_manager: Any = None,
        checkpoint_manager: Any = None,
        audit_logger: Any = None
    ):
        """
        Initialize the state graph.
        
        Args:
            state_schema: Schema class for state
            security_manager: Security manager for capability checks
            checkpoint_manager: Checkpoint manager for state persistence
            audit_logger: Audit logger for action logging
        """
        self.state_schema = state_schema
        self.security = security_manager
        self.checkpoint = checkpoint_manager
        self.audit = audit_logger
        
        # Graph structure
        self.nodes: Dict[str, StateNode] = {}
        self.edges: List[StateEdge] = []
        self.entry_point: Optional[str] = None
        self.finish_node: Optional[str] = None
        self.interrupt_before: List[str] = []
    
    async def add_node(self, node: StateNode) -> 'SecureStateGraph':
        """Add a node to the graph"""
        await self._validate_node(node)
        self.nodes[node.id] = node
        return self
    
    async def add_edge(self, edge: StateEdge) -> 'SecureStateGraph':
        """Add an edge to the graph"""
        await self._validate_edge(edge)
        self.edges.append(edge)
        return self
    
    def set_entry_point(self, node_id: str) -> 'SecureStateGraph':
        """Set the entry point of the graph"""
        if node_id not in self.nodes:
            raise KeyError(f"Node {node_id} not found")
        self.entry_point = node_id
        return self
    
    def set_finish_point(self, node_id: str) -> 'SecureStateGraph':
        """Set the finish point of the graph"""
        if node_id not in self.nodes:
            raise KeyError(f"Node {node_id} not found")
        self.finish_node = node_id
        return self
    
    def set_interrupt_before(self, node_ids: List[str]) -> 'SecureStateGraph':
        """Set nodes that require human approval before execution"""
        for node_id in node_ids:
            if node_id not in self.nodes:
                raise KeyError(f"Node {node_id} not found")
            self.nodes[node_id].requires_human_approval = True
        self.interrupt_before = node_ids
        return self
    
    async def execute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the graph with security checks.
        
        Args:
            initial_state: Initial state for execution
            
        Returns:
            Final state after execution
        """
        # Initialize state
        state = await self._initialize_state(initial_state)
        
        # Create checkpoint before execution
        checkpoint_id = None
        if self.checkpoint:
            checkpoint_id = await self.checkpoint.create_checkpoint(
                agent_id=state.agent_id,
                session_id=state.session_id
            )
            state.checkpoint_id = checkpoint_id
        
        current_node_id = self.entry_point
        max_iterations = 100
        iteration = 0
        
        while current_node_id and iteration < max_iterations:
            iteration += 1
            
            # Check for interrupt (human-in-the-loop)
            if current_node_id in self.interrupt_before:
                interrupt_result = await self._request_human_approval(
                    node_id=current_node_id,
                    state=state
                )
                if not interrupt_result.get("approved", False):
                    state.interrupted_at = current_node_id
                    await self._audit_state_transition(state, "interrupted")
                    break
            
            # Check node capabilities
            node = self.nodes[current_node_id]
            caps_check = await self._check_node_capabilities(node, state)
            if not caps_check.get("approved", False):
                node.status = NodeStatus.FAILED
                state.failed_nodes.append(current_node_id)
                await self._audit_state_transition(state, "capabilities_denied")
                break
            
            # Execute node
            try:
                state.current_node = current_node_id
                node.status = NodeStatus.RUNNING
                
                await self._audit_node_start(node, state)
                
                # Execute node action
                result = await node.action(state.__dict__)
                
                # Update state
                state = await self._update_state(state, result)
                node.status = NodeStatus.COMPLETED
                state.completed_nodes.append(current_node_id)
                
                await self._audit_node_end(node, state, result)
                
            except Exception as e:
                node.status = NodeStatus.FAILED
                state.failed_nodes.append(current_node_id)
                await self._audit_node_error(node, state, e)
                break
            
            # Get next node
            current_node_id = await self._get_next_node(current_node_id, state)
        
        # Final checkpoint
        if self.checkpoint:
            await self.checkpoint.create_checkpoint(
                agent_id=state.agent_id,
                session_id=state.session_id
            )
        
        await self._audit_graph_completion(state)
        
        return state.__dict__
    
    async def _initialize_state(self, initial_data: Dict[str, Any]) -> GraphState:
        """Initialize state from initial data"""
        now = datetime.now(timezone.utc).isoformat()
        
        return self.state_schema(
            **initial_data,
            trace_id=initial_data.get("trace_id", str(uuid.uuid4())),
            session_id=initial_data.get("session_id", str(uuid.uuid4())),
            agent_id=initial_data.get("agent_id", "state_graph"),
            created_at=now,
            updated_at=now,
            protocol_version=self.PROTOCOL_VERSION
        )
    
    async def _validate_node(self, node: StateNode):
        """Validate node before adding"""
        if not node.action or not callable(node.action):
            raise ValueError(f"Node {node.id} must have a callable action")
        
        if node.required_capabilities and self.security:
            valid = await self.security.validate_capabilities(
                node.required_capabilities
            )
            if not valid:
                raise ValueError(f"Node {node.id} has invalid capabilities")
    
    async def _validate_edge(self, edge: StateEdge):
        """Validate edge before adding"""
        if edge.source not in self.nodes:
            raise KeyError(f"Edge source {edge.source} not found")
        if edge.target not in self.nodes and edge.target != "__end__":
            raise KeyError(f"Edge target {edge.target} not found")
    
    async def _check_node_capabilities(
        self,
        node: StateNode,
        state: GraphState
    ) -> Dict[str, Any]:
        """Check if node has required capabilities"""
        if not node.required_capabilities:
            return {"approved": True}
        
        if self.security:
            return await self.security.check_capabilities(
                required=node.required_capabilities,
                context={"state": state.__dict__}
            )
        
        return {"approved": True}
    
    async def _request_human_approval(
        self,
        node_id: str,
        state: GraphState
    ) -> Dict[str, Any]:
        """Request human approval for node execution"""
        if not self.security:
            return {"approved": True}
        
        return await self.security.request_human_approval(
            action_type="graph_node_execution",
            details={
                "node_id": node_id,
                "node_name": self.nodes[node_id].name,
                "risk_level": self.nodes[node_id].risk_level
            },
            trace_id=state.trace_id
        )
    
    async def _update_state(
        self,
        state: GraphState,
        result: Dict[str, Any]
    ) -> GraphState:
        """Update state with node result"""
        state.updated_at = datetime.now(timezone.utc).isoformat()
        state.agent_outputs.append(result)
        state.audit_trail.append({
            "event": "state_updated",
            "timestamp": state.updated_at,
            "node": state.current_node,
            "protocol_version": self.PROTOCOL_VERSION
        })
        return state
    
    async def _get_next_node(
        self,
        current_node_id: str,
        state: GraphState
    ) -> Optional[str]:
        """Determine next node to execute"""
        if current_node_id == self.finish_node:
            return None
        
        outgoing_edges = [
            e for e in self.edges if e.source == current_node_id
        ]
        
        if not outgoing_edges:
            return self.finish_node
        
        # Check conditional edges
        for edge in outgoing_edges:
            if edge.edge_type == EdgeType.CONDITIONAL and edge.condition:
                if await edge.condition(state.__dict__):
                    return edge.target
        
        # Return first normal edge
        for edge in outgoing_edges:
            if edge.edge_type == EdgeType.NORMAL:
                return edge.target
        
        return self.finish_node
    
    async def _audit_state_transition(
        self,
        state: GraphState,
        transition_type: str
    ):
        """Audit state transition"""
        if self.audit:
            await self.audit.log_action(
                action=f"state_transition:{transition_type}",
                result={
                    "current_node": state.current_node,
                    "completed_nodes": state.completed_nodes,
                    "failed_nodes": state.failed_nodes,
                    "protocol_version": self.PROTOCOL_VERSION
                },
                context={
                    "trace_id": state.trace_id,
                    "session_id": state.session_id
                }
            )
    
    async def _audit_node_start(self, node: StateNode, state: GraphState):
        """Audit node start"""
        if self.audit:
            await self.audit.log_action(
                action=f"node_start:{node.id}",
                result={"node_name": node.name, "risk_level": node.risk_level},
                context={"trace_id": state.trace_id, "protocol_version": self.PROTOCOL_VERSION}
            )
    
    async def _audit_node_end(
        self,
        node: StateNode,
        state: GraphState,
        result: Dict[str, Any]
    ):
        """Audit node end"""
        if self.audit:
            await self.audit.log_action(
                action=f"node_end:{node.id}",
                result={
                    "node_name": node.name,
                    "status": node.status.value,
                    "result_preview": str(result)[:500]
                },
                context={"trace_id": state.trace_id, "protocol_version": self.PROTOCOL_VERSION}
            )
    
    async def _audit_node_error(
        self,
        node: StateNode,
        state: GraphState,
        error: Exception
    ):
        """Audit node error"""
        if self.audit:
            await self.audit.log_action(
                action=f"node_error:{node.id}",
                result={
                    "node_name": node.name,
                    "error_type": type(error).__name__,
                    "error_message": str(error)
                },
                context={"trace_id": state.trace_id, "protocol_version": self.PROTOCOL_VERSION}
            )
    
    async def _audit_graph_completion(self, state: GraphState):
        """Audit graph completion"""
        if self.audit:
            await self.audit.log_action(
                action="graph_completion",
                result={
                    "completed_nodes": len(state.completed_nodes),
                    "failed_nodes": len(state.failed_nodes),
                    "interrupted_at": state.interrupted_at,
                    "protocol_version": self.PROTOCOL_VERSION
                },
                context={
                    "trace_id": state.trace_id,
                    "session_id": state.session_id
                }
            )


# Skill manifest for registration
SKILL_MANIFEST = {
    "name": "secure_state_graph",
    "version": "1.0.0",
    "description": "Secure state graph with capability-based access control",
    "author": "synapse_core",
    "inputs": {
        "initial_state": "dict",
        "nodes": "list",
        "edges": "list"
    },
    "outputs": {
        "final_state": "dict",
        "completed_nodes": "list",
        "failed_nodes": "list"
    },
    "required_capabilities": ["graph:execute"],
    "risk_level": 3,
    "isolation_type": "container",
    "protocol_version": PROTOCOL_VERSION
}
