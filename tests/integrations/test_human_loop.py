"""Tests for Human Loop Manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, '/a0/usr/projects/project_synapse')

from synapse.integrations.human_loop import (
    HumanLoopManager,
    HumanApprovalRequest,
    ApprovalStatus,
    PROTOCOL_VERSION
)


class TestHumanLoopProtocol:
    """Tests for protocol version compliance."""
    
    def test_protocol_version_defined(self):
        assert PROTOCOL_VERSION == "1.0"
    
    def test_manager_has_protocol_version(self):
        assert HumanLoopManager.PROTOCOL_VERSION == "1.0"
    
    def test_request_has_protocol_version(self):
        request = HumanApprovalRequest(
            id="test",
            graph_id="test",
            node_id="test",
            node_name="test",
            state_snapshot={},
            risk_level=1,
            required_action="test",
            created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-02T00:00:00Z"
        )
        assert request.protocol_version == "1.0"


class TestHumanLoopManager:
    """Tests for HumanLoopManager."""
    
    @pytest.fixture
    def manager(self):
        return HumanLoopManager()
    
    @pytest.mark.asyncio
    async def test_create_interrupt(self, manager):
        request = await manager.create_interrupt(
            graph_id="test_graph",
            node_id="test_node",
            state={"test": "data"},
            risk_level=3,
            trace_id="test_trace",
            session_id="test_session"
        )
        assert request.id is not None
        assert request.status == ApprovalStatus.PENDING
        assert request.protocol_version == "1.0"
    
    @pytest.mark.asyncio
    async def test_submit_approval(self, manager):
        request = await manager.create_interrupt(
            graph_id="test",
            node_id="test",
            state={},
            risk_level=1,
            trace_id="test",
            session_id="test"
        )
        result = await manager.submit_approval(
            request_id=request.id,
            approved=True,
            user_id="test_user"
        )
        assert result == True
        assert request.status == ApprovalStatus.APPROVED
    
    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, manager):
        await manager.create_interrupt(
            graph_id="test",
            node_id="test",
            state={},
            risk_level=1,
            trace_id="test",
            session_id="test"
        )
        pending = await manager.get_pending_approvals()
        assert len(pending) >= 1


class TestSkillManifest:
    """Tests for skill manifest."""
    
    def test_manifest_has_protocol_version(self):
        from synapse.integrations.human_loop import SKILL_MANIFEST
        assert SKILL_MANIFEST["protocol_version"] == "1.0"
