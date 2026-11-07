from __future__ import annotations

from synapse.api.app import result_message
from synapse.agents.planner import PlannerAgent


def test_result_message_preserves_all_text_outputs():
    task = {
        "status": "completed",
        "result": {"action_result": {"outputs": [
            {"content": "Первый полный фрагмент"},
            {"content": "Второй полный фрагмент"},
        ]}},
    }
    assert result_message(task) == "Первый полный фрагмент\n\nВторой полный фрагмент"


def test_planner_has_read_only_workspace_audit_plan():
    planner = PlannerAgent()
    steps = planner._plan_heuristic("Изучи приложение и рабочую среду, проведи аудит")
    assert steps[0].skill == "workspace_audit"
    assert steps[0].required_capabilities == ["fs:read"]
    assert steps[0].params["read_only"] is True


def test_planner_does_not_claim_self_weight_modification():
    planner = PlannerAgent()
    steps = planner._plan_heuristic("модифицируй себя и свои веса")
    assert steps[0].skill == "generic_executor"
    assert steps[0].params["safety_boundary"] == "no_self_modification"
    assert "fs:write" not in steps[0].required_capabilities


def test_worker_context_carries_workspace_root_for_read_only_skills():
    """Read-only skills executed in the isolated worker must resolve the real
    workspace root instead of the worker's temporary cwd."""
    import asyncio
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace

    from synapse.core.models import ExecutionContext
    from synapse.runtime.worker_backend import IsolatedWorkerBackend

    probe = """import sys, json, os
from pathlib import Path
from types import SimpleNamespace
from synapse.core.models import ExecutionContext

def handler(ctx, **params):
    root = getattr(getattr(ctx, "memory_store", None), "workspace_root", None)
    return {
        "success": True,
        "in_worker": root is not None,
        "workspace_root": str(root or ""),
        "cwd": str(Path.cwd().resolve()),
        "capabilities": ctx.capabilities,
    }
"""
    ctx = ExecutionContext(
        session_id="s",
        agent_id="test",
        trace_id="t",
        capabilities=["fs:read"],
        memory_store=SimpleNamespace(workspace_root=tempfile.gettempdir()),
    )
    result = asyncio.run(IsolatedWorkerBackend().run_skill(
        "probe",
        probe,
        context=ctx,
        isolation_level="subprocess",
    ))
    assert result.get("success") is True, result
    assert result.get("in_worker") is True
    assert result.get("workspace_root") == str(Path(tempfile.gettempdir()).resolve())
    # The audit skills must not resolve against the worker's temporary sandbox cwd.
    root = Path(result["workspace_root"]).resolve()
    cwd = Path(result["cwd"]).resolve()
    assert root != cwd


def test_context_workspace_root_helper_prefers_memory_store():
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace

    from synapse.runtime.worker_backend import _context_workspace_root

    root = tempfile.gettempdir()
    ctx = SimpleNamespace(memory_store=SimpleNamespace(workspace_root=root))
    assert _context_workspace_root(ctx) == str(Path(root).resolve())
