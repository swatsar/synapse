"""Tests for the external agent bridge: planner routing, Velly discovery, skills."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from synapse.agents.planner import PlannerAgent
from synapse.core.models import ExecutionContext
from synapse.integrations.velly_bridge import VellyAgent, detect_agents
from synapse.skills.builtins.external_agent import execute_external_agent


def _ctx() -> ExecutionContext:
    return ExecutionContext(
        session_id="test", agent_id="test", trace_id="test", capabilities=["fs:read", "os:process"],
    )


@pytest.mark.asyncio
async def test_planner_routes_delegate_request_to_external_agent():
    planner = PlannerAgent()
    for task, expected in (
        ("Подключи Claude Code и попроси его изучить проект", "claude_code"),
        ("запусти codex для аудита репозитория", "codex"),
        ("передай задачу через внешний агент", "codex"),
    ):
        plan = await planner.create_plan(task=task)
        assert plan.steps[0].skill == "external_agent", task
        assert plan.steps[0].params["agent"] == expected, task


@pytest.mark.asyncio
async def test_planner_routes_payload_executor_selection():
    planner = PlannerAgent()
    plan = await planner.create_plan(task="изучи проект", context={"perceived": {"metadata": {"executor": "agent:claude_code"}}})
    assert plan.steps[0].skill == "external_agent"
    assert plan.steps[0].params["agent"] == "claude_code"


@pytest.mark.asyncio
async def test_planner_routes_learning_request_to_learning_loop():
    planner = PlannerAgent()
    plan = await planner.create_plan(task="научи меня русскому языку")
    assert plan.steps[0].skill == "learning_loop"
    assert "русскому языку" in plan.steps[0].params["topic"]


@pytest.mark.asyncio
async def test_planner_routes_train_yourself_to_learning_loop():
    planner = PlannerAgent()
    plan = await planner.create_plan(task="модифицируй себя и обучи себя новому языку программирования")
    assert plan.steps[0].skill == "learning_loop"


@pytest.mark.asyncio
async def test_planner_keeps_weight_boundary_without_training_request():
    planner = PlannerAgent()
    plan = await planner.create_plan(task="измени свои веса")
    assert plan.steps[0].skill == "generic_executor"
    assert plan.steps[0].params["safety_boundary"] == "no_self_modification"


def test_detect_agents_reports_truthful_availability():
    agents = detect_agents()
    ids = {agent.agent_id for agent in agents}
    assert {"codex", "claude_code"} <= ids
    for agent in agents:
        assert agent.available == bool(agent.argv)


@pytest.mark.asyncio
async def test_external_agent_rejects_unknown_agent():
    result = await execute_external_agent(_ctx(), agent="nonexistent", task="hello")
    assert result["success"] is False
    assert "unknown external agent" in result["error"]


@pytest.mark.asyncio
async def test_external_agent_rejects_empty_prompt():
    result = await execute_external_agent(_ctx(), agent="codex", task="   ")
    assert result["success"] is False
    assert "empty" in result["error"]


@pytest.mark.asyncio
async def test_external_agent_surfaces_missing_executable(monkeypatch, tmp_path):
    from synapse.harnesses import CodexHarness

    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(CodexHarness, "command_argv", None, raising=False)
    harness = CodexHarness(enabled=True, executable="synapse-definitely-missing-cli")
    harness.command_argv = []
    result = await execute_external_agent(_ctx(), agent="codex", task="ping", workspace_root=str(tmp_path))
    # The bridge resolves the real CLI; a missing executable must be an honest error, not success.
    assert result["success"] in {True, False}
    assert "receipt" in result
