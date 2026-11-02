"""Tests for web dashboard."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestDashboard:
    """Test web dashboard."""
    
    @pytest.fixture
    def dashboard(self):
        """Create a dashboard for testing."""
        from synapse.ui.web.dashboard import Dashboard
        
        return Dashboard()
    
    def test_dashboard_creation(self, dashboard):
        """Test dashboard creation."""
        assert dashboard is not None
    
    def test_protocol_version(self, dashboard):
        """Test protocol version."""
        assert dashboard.protocol_version == "1.0"
    
    def test_get_cluster_state(self, dashboard):
        """Test getting cluster state."""
        state = dashboard.get_cluster_state()
        assert isinstance(state, dict)
        assert "status" in state
    
    def test_list_agents(self, dashboard):
        """Test listing agents."""
        agents = dashboard.list_agents()
        assert isinstance(agents, list)
    
    def test_add_agent(self, dashboard):
        """Test adding an agent."""
        from synapse.ui.web.dashboard import AgentInfo
        
        agent = AgentInfo(id="test", name="Test Agent")
        dashboard.add_agent(agent)
        
        agents = dashboard.list_agents()
        assert len(agents) == 1
        assert agents[0].id == "test"
    
    def test_get_pending_approvals(self, dashboard):
        """Test getting pending approvals."""
        approvals = dashboard.get_pending_approvals()
        assert isinstance(approvals, list)
    
    def test_add_approval_request(self, dashboard):
        """Test adding an approval request."""
        from synapse.ui.web.dashboard import ApprovalRequest
        
        request = ApprovalRequest(id="test", action="test_action", risk_level=2)
        dashboard.add_approval_request(request)
        
        approvals = dashboard.get_pending_approvals()
        assert len(approvals) == 1
    
    def test_approve(self, dashboard):
        """Test approving a request."""
        from synapse.ui.web.dashboard import ApprovalRequest
        
        request = ApprovalRequest(id="test", action="test_action", risk_level=2)
        dashboard.add_approval_request(request)
        
        result = dashboard.approve("test")
        assert result == True
    
    def test_reject(self, dashboard):
        """Test rejecting a request."""
        from synapse.ui.web.dashboard import ApprovalRequest
        
        request = ApprovalRequest(id="test", action="test_action", risk_level=2)
        dashboard.add_approval_request(request)
        
        result = dashboard.reject("test")
        assert result == True
    
    def test_get_logs(self, dashboard):
        """Test getting logs."""
        logs = dashboard.get_logs()
        assert isinstance(logs, list)
    
    def test_add_log(self, dashboard):
        """Test adding a log entry."""
        dashboard.add_log({"message": "test"})
        
        logs = dashboard.get_logs()
        assert len(logs) == 1
    
    @pytest.mark.asyncio
    async def test_execute_task(self, dashboard):
        """Test executing a task."""
        result = await dashboard.execute_task("test_task")
        assert isinstance(result, dict)
        assert "status" in result
