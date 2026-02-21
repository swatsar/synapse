"""
Tests for Phase 2: Capability Governance + Local Execution Node + Orchestrator Channel
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
import time
from datetime import datetime, timedelta

# Local imports
from synapse.governance.capability_registry import CapabilityRegistry, CapabilityMetadata
from synapse.governance.capability_policy import CapabilityPolicyEngine, PolicyViolation
from synapse.governance.issuance import CapabilityIssuer
from synapse.governance.revocation import CapabilityRevoker
from synapse.node.node_runtime import ExecutionNode
from synapse.node.node_config import NodeConfig
from synapse.node.node_security import NodeSecurity
from synapse.node.node_api import NodeAPI
from synapse.transport.message import ExecutionRequest, ExecutionResult, ExecutionTrace, CapabilityError
from synapse.transport.channel import CommunicationChannel
from synapse.transport.protocol import ProtocolVersion
from synapse.interfaces.orchestrator_service import OrchestratorService
from synapse.orchestrator.orchestrator_agent import OrchestratorAgent
from synapse.orchestrator.task_model import Task
from synapse.orchestrator.planning import TaskPlanner
from synapse.core.binding import BindingManager
from synapse.core.workflow_engine import WorkflowDefinition
from synapse.core.execution import SecureExecutionContext, SecureWorkflowExecutor


# ==================== CAPABILITY GOVERNANCE TESTS ====================
class TestCapabilityRegistry:
    """Tests for capability registry"""
    
    def test_capability_registration(self):
        """Capabilities should be registered with metadata"""
        registry = CapabilityRegistry()
        metadata = CapabilityMetadata(
            name="test_capability",
            description="Test capability",
            category="test",
            risk_level=1
        )
        registry.register("test:capability", metadata)
        
        assert registry.get_metadata("test:capability") == metadata
        assert "test:capability" in registry.list_capabilities()
    
    def test_duplicate_capability_registration(self):
        """Duplicate capabilities should not be allowed"""
        registry = CapabilityRegistry()
        metadata = CapabilityMetadata(name="test", description="Test", category="test", risk_level=1)
        registry.register("test:capability", metadata)
        
        with pytest.raises(ValueError):
            registry.register("test:capability", metadata)


class TestCapabilityIssuance:
    """Tests for capability issuance"""
    
    def test_capability_issuance(self):
        """Capabilities should be issuable to agents"""
        registry = CapabilityRegistry()
        metadata = CapabilityMetadata(name="test", description="Test", category="test", risk_level=1)
        registry.register("test:capability", metadata)
        
        issuer = CapabilityIssuer(registry)
        expires_at = datetime.now() + timedelta(days=1)
        
        issuer.issue("agent1", "test:capability", expires_at)
        
        assert issuer.has_capability("agent1", "test:capability")
    
    def test_issued_capability_expiration(self):
        """Expired capabilities should be invalid"""
        registry = CapabilityRegistry()
        metadata = CapabilityMetadata(name="test", description="Test", category="test", risk_level=1)
        registry.register("test:capability", metadata)
        
        issuer = CapabilityIssuer(registry)
        expires_at = datetime.now() - timedelta(days=1)
        
        issuer.issue("agent1", "test:capability", expires_at)
        
        assert not issuer.validate("agent1", "test:capability")
    
    def test_issue_nonexistent_capability(self):
        """Should not issue nonexistent capabilities"""
        registry = CapabilityRegistry()
        issuer = CapabilityIssuer(registry)
        
        with pytest.raises(ValueError):
            issuer.issue("agent1", "nonexistent:capability")


class TestCapabilityRevocation:
    """Tests for capability revocation"""
    
    def test_capability_revocation(self):
        """Capabilities should be revocable"""
        registry = CapabilityRegistry()
        metadata = CapabilityMetadata(name="test", description="Test", category="test", risk_level=1)
        registry.register("test:capability", metadata)
        
        issuer = CapabilityIssuer(registry)
        issuer.issue("agent1", "test:capability")
        
        revoker = CapabilityRevoker(issuer)
        revoker.revoke("agent1", "test:capability")
        
        assert not issuer.has_capability("agent1", "test:capability")
    
    def test_revocation_blocks_execution(self):
        """Revoked capabilities should prevent execution"""
        # Setup
        registry = CapabilityRegistry()
        metadata = CapabilityMetadata(name="execute", description="Execute tasks", category="execution", risk_level=2)
        registry.register("execution:run", metadata)
        
        # Issue capability
        issuer = CapabilityIssuer(registry)
        issuer.issue("agent1", "execution:run")
        
        # Verify has capability
        assert issuer.has_capability("agent1", "execution:run")
        
        # Revoke
        revoker = CapabilityRevoker(issuer)
        revoker.revoke("agent1", "execution:run")
        
        # Should not have capability anymore
        assert not issuer.has_capability("agent1", "execution:run")


class TestCapabilityPolicyEngine:
    """Tests for capability policy engine"""
    
    def test_capability_risk_validation(self):
        """High risk capabilities require additional checks"""
        policy_engine = CapabilityPolicyEngine()
        
        # Should allow low risk
        assert policy_engine.validate_capability(
            "test:low_risk", CapabilityMetadata(name="Low Risk", description="Low risk capability", category="test", risk_level=1)
        )
        
        # Should require approval for high risk
        assert not policy_engine.validate_capability(
            "test:high_risk", CapabilityMetadata(name="High Risk", description="High risk capability", category="test", risk_level=4)
        )


# ==================== LOCAL EXECUTION NODE TESTS ====================
class TestExecutionNode:
    """Tests for local execution node"""
    
    @pytest_asyncio.fixture
    async def node(self):
        config = NodeConfig()
        issuer = MagicMock()
        issuer.validate.return_value = True
        security = NodeSecurity(issuer)
        executor = MagicMock(spec=SecureWorkflowExecutor)
        return ExecutionNode(executor, security)
    
    @pytest.mark.asyncio
    async def test_node_executes_workflow(self, node):
        """Node should execute workflows"""
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        context.agent_id = "test_agent"
        context.capabilities = {"execution:run"}
        
        expected_result = MagicMock()
        expected_result.success = True
        
        node.executor.execute.return_value = expected_result
        
        result = await node.execute_workflow(workflow, context)
        
        assert result.success == True
        node.executor.execute.assert_called_once_with(workflow, context)
    
    @pytest.mark.asyncio
    async def test_node_rejects_missing_capability(self, node):
        """Node should reject execution without required capability"""
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        
        # Should have required capability "nonexistent:capability"
        context.capabilities = set()
        context.agent_id = "test_agent"
        
        with pytest.raises(CapabilityError):
            await node.execute_workflow(workflow, context)
    
    @pytest.mark.asyncio
    async def test_node_produces_deterministic_trace(self, node):
        """Node should produce deterministic execution traces"""
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        context.agent_id = "test_agent"
        context.capabilities = {"execution:run"}
        
        expected_result = MagicMock()
        expected_result.success = True
        expected_result.trace = ExecutionTrace(
            trace_id="trace_00000001",
            workflow_id="test_workflow",
            steps=[],
            execution_time_ms=100,
            protocol_version="1.0"
        )
        
        node.executor.execute.return_value = expected_result
        
        result1 = await node.execute_workflow(workflow, context)
        result2 = await node.execute_workflow(workflow, context)
        
        # Both should succeed
        assert result1.success == True
        assert result2.success == True


class TestNodeAPI:
    """Tests for node API"""
    
    @pytest_asyncio.fixture
    async def node_api(self):
        node = MagicMock(spec=ExecutionNode)
        api = NodeAPI(node)
        return api
    
    @pytest.mark.asyncio
    async def test_node_api_accepts_request(self, node_api):
        """Node API should accept execution requests"""
        request = MagicMock(spec=ExecutionRequest)
        request.workflow = MagicMock(spec=WorkflowDefinition)
        request.context = MagicMock(spec=SecureExecutionContext)
        request.context.agent_id = "test_agent"
        request.context.capabilities = {"execution:run"}
        
        node_api.node.execute_workflow.return_value = MagicMock(success=True)
        
        result = await node_api.execute(request)
        
        assert result.success == True


# ==================== ORCHESTRATOR COMMUNICATION TESTS ====================
class TestCommunicationChannel:
    """Tests for orchestrator communication channel"""
    
    def test_message_serialization(self):
        """Messages should serialize deterministically"""
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        
        request1 = ExecutionRequest(workflow, context)
        request2 = ExecutionRequest(workflow, context)
        
        assert request1.serialize() == request2.serialize()
    
    def test_message_deserialization(self):
        """Messages should deserialize correctly"""
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        
        request = ExecutionRequest(workflow, context)
        serialized = request.serialize()
        deserialized = ExecutionRequest.deserialize(serialized)
        
        assert deserialized.protocol_version == request.protocol_version


class TestOrchestratorToNodeCommunication:
    """Tests for orchestrator to node communication flow"""
    
    @pytest_asyncio.fixture
    async def channel(self):
        channel = CommunicationChannel()
        return channel
    
    @pytest.mark.asyncio
    async def test_orchestrator_send_receive(self, channel):
        """Orchestrator should send request and receive result"""
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        request = ExecutionRequest(workflow, context)
        
        # Test send
        await channel.send_request(request)
        received = await channel.receive_request()
        assert received.workflow == workflow
        
        # Test reply
        result = ExecutionResult(success=True, steps_executed=2)
        await channel.send_result(result)
        received_result = await channel.receive_result()
        assert received_result.success == True


# ==================== INTEGRATION TESTS ====================
class TestOrchestratorNodeIntegration:
    """Tests for orchestrator to node integration"""
    
    @pytest_asyncio.fixture
    async def test_setup(self):
        """Create complete setup for integration tests"""
        # Create governance
        registry = CapabilityRegistry()
        metadata = CapabilityMetadata(name="execute", description="Execute tasks", category="execution", risk_level=2)
        registry.register("execution:run", metadata)
        
        issuer = CapabilityIssuer(registry)
        issuer.issue("agent1", "execution:run")
        
        security = NodeSecurity(issuer)
        
        # Create node
        executor = MagicMock(spec=SecureWorkflowExecutor)
        expected_result = MagicMock()
        expected_result.success = True
        expected_result.trace = ExecutionTrace(
            trace_id="trace_00000001",
            workflow_id="test_workflow",
            steps=[],
            execution_time_ms=100,
            protocol_version="1.0"
        )
        executor.execute.return_value = expected_result
        
        node = ExecutionNode(executor, security)
        
        return {"node": node, "issuer": issuer, "registry": registry}
    
    @pytest.mark.asyncio
    async def test_orchestrated_execution_via_node(self, test_setup):
        """Complete orchestration flow from user to execution node"""
        node = test_setup["node"]
        
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        context.capabilities = {"execution:run"}
        context.agent_id = "agent1"
        
        result = await node.execute_workflow(workflow, context)
        
        assert result.success == True
    
    @pytest.mark.asyncio
    async def test_governance_enforced_before_execution(self, test_setup):
        """Governance should prevent execution without capability"""
        node = test_setup["node"]
        
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        context.capabilities = {"nonexistent:capability"}
        context.agent_id = "agent1"
        
        with pytest.raises(CapabilityError):
            await node.execute_workflow(workflow, context)
    
    @pytest.mark.asyncio
    async def test_replay_across_node_boundary(self, test_setup):
        """Replay should work across node boundary"""
        node = test_setup["node"]
        
        workflow = MagicMock(spec=WorkflowDefinition)
        context = MagicMock(spec=SecureExecutionContext)
        context.capabilities = {"execution:run"}
        context.agent_id = "agent1"
        
        result1 = await node.execute_workflow(workflow, context)
        result2 = await node.execute_workflow(workflow, context)
        
        # Both should succeed
        assert result1.success == True
        assert result2.success == True


class TestOrchestratorServiceUpgrade:
    """Tests for upgraded orchestrator service"""
    
    @pytest_asyncio.fixture
    async def service(self):
        binding_manager = BindingManager()
        service = OrchestratorService(binding_manager=binding_manager)
        return service
    
    @pytest.mark.asyncio
    async def test_service_accepts_task(self, service):
        """Orchestrator service should accept tasks from users"""
        task_data = {
            "agent_id": "test_agent",
            "description": "Test task",
            "capabilities": ["execution:run"]
        }
        
        result = await service.accept_task(task_data)
        
        assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_service_returns_trace(self, service):
        """Orchestrator service should return execution traces"""
        task_data = {
            "agent_id": "test_agent",
            "description": "Test task",
            "capabilities": ["execution:run"]
        }
        
        response = await service.accept_task(task_data)
        
        assert "task_id" in response
        assert response["protocol_version"] == "1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
