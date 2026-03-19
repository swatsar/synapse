"""Unit tests for Goal Management System. Phase 4 — Self-Evolution.

TDD per TDD_INSTRUCTION_v1_2_FINAL.md + AUTOGPT_INTEGRATION.md §2.
"""
import pytest
import pytest_asyncio

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase4
@pytest.mark.unit
class TestGoal:
    def test_goal_defaults(self):
        from synapse.agents.goal_manager import Goal, GoalStatus, GoalPriority
        g = Goal(description="Test goal")
        assert g.id
        assert g.status == GoalStatus.PENDING
        assert g.priority == GoalPriority.MEDIUM
        assert g.protocol_version == PROTOCOL_VERSION

    def test_goal_to_dict(self):
        from synapse.agents.goal_manager import Goal, GoalPriority
        g = Goal(description="Do something", priority=GoalPriority.HIGH)
        d = g.to_dict()
        assert d["description"] == "Do something"
        assert d["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase4
@pytest.mark.unit
class TestGoalManager:
    @pytest.fixture
    def manager(self):
        from synapse.agents.goal_manager import GoalManager
        return GoalManager()

    @pytest.mark.asyncio
    async def test_create_goal(self, manager):
        from synapse.agents.goal_manager import GoalPriority, GoalStatus
        goal = await manager.create_goal("Analyze logs", priority=GoalPriority.HIGH)
        assert goal.id
        assert goal.description == "Analyze logs"
        assert goal.status == GoalStatus.PENDING
        assert goal.protocol_version == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_create_sub_goal(self, manager):
        parent = await manager.create_goal("Main task")
        sub = await manager.create_goal("Sub task", parent_goal_id=parent.id)
        assert sub.parent_goal_id == parent.id
        assert sub.id in parent.sub_goals

    @pytest.mark.asyncio
    async def test_update_status_completed(self, manager):
        from synapse.agents.goal_manager import GoalStatus
        goal = await manager.create_goal("Complete me")
        updated = await manager.update_status(goal.id, GoalStatus.COMPLETED, result="done")
        assert updated.status == GoalStatus.COMPLETED
        assert updated.completed_at is not None
        assert updated.result == "done"

    @pytest.mark.asyncio
    async def test_get_active_goal_returns_highest_priority(self, manager):
        from synapse.agents.goal_manager import GoalPriority
        await manager.create_goal("Low", priority=GoalPriority.LOW)
        await manager.create_goal("Critical", priority=GoalPriority.CRITICAL)
        await manager.create_goal("Medium", priority=GoalPriority.MEDIUM)
        active = manager.get_active_goal()
        assert active is not None
        assert active.description == "Critical"

    @pytest.mark.asyncio
    async def test_decompose_goal(self, manager):
        parent = await manager.create_goal("Big goal")
        subs = await manager.decompose_goal(parent.id, ["Sub 1", "Sub 2", "Sub 3"])
        assert len(subs) == 3
        assert all(s.parent_goal_id == parent.id for s in subs)
        assert len(parent.sub_goals) == 3

    @pytest.mark.asyncio
    async def test_list_goals_by_status(self, manager):
        from synapse.agents.goal_manager import GoalStatus
        await manager.create_goal("G1")
        g2 = await manager.create_goal("G2")
        await manager.update_status(g2.id, GoalStatus.COMPLETED)
        pending = manager.list_goals(status=GoalStatus.PENDING)
        completed = manager.list_goals(status=GoalStatus.COMPLETED)
        assert len(pending) == 1
        assert len(completed) == 1

    @pytest.mark.asyncio
    async def test_goal_tree(self, manager):
        parent = await manager.create_goal("Root")
        await manager.create_goal("Child 1", parent_goal_id=parent.id)
        await manager.create_goal("Child 2", parent_goal_id=parent.id)
        tree = manager.get_goal_tree()
        assert len(tree) == 1
        assert len(tree[0]["children"]) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        from synapse.agents.goal_manager import GoalStatus
        await manager.create_goal("G1")
        await manager.create_goal("G2")
        g3 = await manager.create_goal("G3")
        await manager.update_status(g3.id, GoalStatus.COMPLETED)
        stats = manager.get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["pending"] == 2
        assert stats["by_status"]["completed"] == 1
        assert stats["protocol_version"] == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_unknown_goal_raises_key_error(self, manager):
        from synapse.agents.goal_manager import GoalStatus
        with pytest.raises(KeyError):
            await manager.update_status("nonexistent", GoalStatus.COMPLETED)
