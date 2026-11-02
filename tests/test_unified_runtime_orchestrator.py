import pytest
from unittest.mock import AsyncMock, MagicMock
import uuid
import time

class TestSecureExecutionContext:
    @pytest.mark.asyncio
    async def test_context_creation(self):
        from synapse.core.execution import SecureExecutionContext
        context = SecureExecutionContext(
            agent_id="test_agent",
            capabilities=["fs:read:/workspace/**"]
        )
        assert context.agent_id == "test_agent"
        assert len(context.capabilities) == 1
    
    @pytest.mark.asyncio
    async def test_context_has_capability(self):
        from synapse.core.execution import SecureExecutionContext
        context = SecureExecutionContext(
            agent_id="test_agent",
            capabilities=["fs:read:/workspace/**"]
        )
        assert context.has_capability("fs:read:/workspace/**")
        assert not context.has_capability("fs:write:/workspace/**")

class TestBindingManager:
    @pytest.mark.asyncio
    async def test_binding_creation(self):
        from synapse.core.binding import BindingManager
        manager = BindingManager()
        agent_id = str(uuid.uuid4())
        binding = manager.bind(agent_id, "fs:read:/workspace/**")
        assert binding is not None
        assert isinstance(binding, str)
    
    @pytest.mark.asyncio
    async def test_has_binding(self):
        from synapse.core.binding import BindingManager
        manager = BindingManager()
        agent_id = str(uuid.uuid4())
        manager.bind(agent_id, "fs:read:/workspace/**")
        assert manager.has_binding(agent_id, "fs:read:/workspace/**")
        assert not manager.has_binding(agent_id, "fs:write:/workspace/**")
    
    @pytest.mark.asyncio
    async def test_binding_unbind(self):
        from synapse.core.binding import BindingManager
        manager = BindingManager()
        agent_id = str(uuid.uuid4())
        manager.bind(agent_id, "fs:read:/workspace/**")
        manager.unbind(agent_id, "fs:read:/workspace/**")
        assert not manager.has_binding(agent_id, "fs:read:/workspace/**")

class TestWorkflowEngine:
    @pytest.mark.asyncio
    async def test_dependency_ordering(self):
        from synapse.core.workflow_engine import WorkflowEngine, Step, WorkflowDefinition
        
        engine = WorkflowEngine()
        
        step1 = Step(id="1", name="Step 1", capabilities=["fs:read"])
        step2 = Step(id="2", name="Step 2", requires=["1"], capabilities=["fs:write"])
        step3 = Step(id="3", name="Step 3", requires=["2"], capabilities=["net:http"])
        
        workflow = WorkflowDefinition(
            name="Test Workflow",
            steps=[step1, step2, step3],
            dependencies={"2": ["1"], "3": ["2"]}
        )
        
        order = engine.build_execution_order(workflow)
        assert len(order) == 3
        assert order[0].id == "1"
        assert order[1].id == "2"
        assert order[2].id == "3"

class TestSecureWorkflowExecutor:
    @pytest.mark.asyncio
    async def test_workflow_executed_via_executor(self):
        from synapse.core.execution import SecureExecutionContext, SecureWorkflowExecutor
        from synapse.core.workflow_engine import WorkflowDefinition, Step
        from synapse.core.binding import BindingManager
        
        manager = BindingManager()
        
        workflow = WorkflowDefinition(
            name="Test Workflow",
            steps=[
                Step(id="1", name="Read File", capabilities=["fs:read"]),
                Step(id="2", name="Process Data", capabilities=["compute"])
            ]
        )
        
        context = SecureExecutionContext(
            agent_id="test_agent",
            capabilities=["fs:read", "compute"]
        )
        
        executor = SecureWorkflowExecutor(binding_manager=manager)
        result = await executor.execute(workflow, context)
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_capability_enforcement_works(self):
        from synapse.core.execution import SecureExecutionContext, SecureWorkflowExecutor
        from synapse.core.workflow_engine import WorkflowDefinition, Step
        from synapse.core.binding import BindingManager
        
        manager = BindingManager()
        
        workflow = WorkflowDefinition(
            name="Test Workflow",
            steps=[Step(id="1", name="Read File", capabilities=["fs:read"])]
        )
        
        context = SecureExecutionContext(
            agent_id="test_agent",
            capabilities=["compute"]  # Missing fs:read
        )
        
        executor = SecureWorkflowExecutor(binding_manager=manager)
        result = await executor.execute(workflow, context)
        
        assert result["success"] is False
        assert "capability" in result["error"].lower()

class TestReplayManager:
    @pytest.mark.asyncio
    async def test_replay_identical(self):
        from synapse.core.replay import ReplayManager
        replay = ReplayManager()
        trace_id = str(uuid.uuid4())
        replay.start_recording(trace_id)
        replay.record("step1", {"input": "data", "output": "result"})
        recorded = replay.get_recording(trace_id)
        
        assert len(recorded) == 1
        assert recorded[0][0] == "step1"

class TestObservabilityCore:
    @pytest.mark.asyncio
    async def test_all_events_published(self):
        from synapse.core.observability import ObservabilityCore
        obs = ObservabilityCore()
        events = []
        handler = lambda e: events.append(e)
        
        await obs.subscribe("*", handler)
        await obs.emit("test_event", {"data": "test"})
        
        assert len(events) == 1
        assert events[0].event_type == "test_event"

class TestOrchestratorAgent:
    @pytest.mark.asyncio
    async def test_task_to_workflow_plan(self):
        from synapse.orchestrator.orchestrator_agent import OrchestratorAgent
        from synapse.orchestrator.task_model import Task
        from synapse.core.binding import BindingManager
        
        agent = OrchestratorAgent(binding_manager=BindingManager())
        task = Task(
            id=str(uuid.uuid4()),
            agent_id="test_agent",
            description="Test task",
            capabilities=["fs:read"]
        )
        
        plan = await agent.plan_workflow(task)
        assert plan is not None
    
    @pytest.mark.asyncio
    async def test_capability_checked_before_execution(self):
        from synapse.orchestrator.orchestrator_agent import OrchestratorAgent
        from synapse.orchestrator.task_model import Task
        from synapse.core.binding import BindingManager
        
        manager = BindingManager()
        agent = OrchestratorAgent(binding_manager=manager)
        
        task = Task(
            id=str(uuid.uuid4()),
            agent_id="test_agent",
            description="Test task with insufficient permissions",
            capabilities=["fs:read"]
        )
        
        result = await agent.execute_task(task)
        assert result["success"] is False
        assert "capability" in result["error"].lower()

class TestOrchestratorService:
    @pytest.mark.asyncio
    async def test_service_accepts_task(self):
        from synapse.interfaces.orchestrator_service import OrchestratorService
        from synapse.core.binding import BindingManager
        
        service = OrchestratorService(binding_manager=BindingManager())
        task_data = {
            "agent_id": "test_agent",
            "description": "Test task",
            "capabilities": ["fs:read"]
        }
        result = await service.accept_task(task_data)
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_service_returns_trace(self):
        from synapse.interfaces.orchestrator_service import OrchestratorService
        from synapse.core.binding import BindingManager
        
        service = OrchestratorService(binding_manager=BindingManager())
        task_data = {
            "agent_id": "test_agent",
            "description": "Test task",
            "capabilities": ["fs:read"]
        }
        result = await service.accept_task(task_data)
        assert "trace_id" in result
