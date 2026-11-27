"""Explicit agent jobs share the task ledger and the verified dataset."""

import asyncio
import subprocess
import sys

import pytest

from synapse.api.workspace_store import WorkspaceStore
from synapse.experience import ExperienceStore
from synapse.harnesses import HarnessResult


@pytest.mark.asyncio
async def test_verified_agent_answer_becomes_local_training_evidence(tmp_path):
    from synapse.api.agent_runs import ManagedAgentRuns

    store = WorkspaceStore(tmp_path / "workspace.db")
    experience = ExperienceStore(tmp_path / "experience.db")
    session = store.create_session("agent")
    task = store.create_task(session["id"], "Explain the app", {
        "managed_agent": "opencode",
        "model": "opencode/example",
        "acceptance_criteria": ["output_contains:web app"],
    })

    async def execute(_):
        return HarnessResult(
            True, output="It is a web app.",
            events=({"type": "step_finish", "private": "ignore me"},),
        )

    jobs = ManagedAgentRuns(store, experience, tmp_path)
    await jobs.start(task, execute)
    record = store.get_task(task["id"])
    assert record["status"] == "completed"
    assert record["result"]["verification"]["passed"] is True
    saved = experience.latest_for_task(task["id"])
    assert saved.verified_for_training
    assert saved.provider == "opencode"
    assert saved.model == "opencode/example"
    assert saved.visible_events == [{"type": "step_finish"}]


@pytest.mark.asyncio
async def test_stop_waits_for_agent_cleanup_and_keeps_it_out_of_training(tmp_path):
    from synapse.api.agent_runs import ManagedAgentRuns

    store = WorkspaceStore(tmp_path / "workspace.db")
    experience = ExperienceStore(tmp_path / "experience.db")
    session = store.create_session("agent")
    task = store.create_task(session["id"], "Analyze", {"managed_agent": "codex"})
    started = asyncio.Event()
    cleaned_up = asyncio.Event()

    async def execute(_):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cleaned_up.set()

    jobs = ManagedAgentRuns(store, experience, tmp_path)
    jobs.start(task, execute)
    await started.wait()
    stopped = await jobs.stop(task)
    assert cleaned_up.is_set()
    assert stopped["status"] == "cancelled"
    assert experience.latest_for_task(task["id"]) is None


@pytest.mark.asyncio
async def test_opencode_stop_waits_for_the_process_tree(monkeypatch, tmp_path):
    from synapse.llm import opencode_provider

    original_popen = subprocess.Popen
    started = asyncio.Event()
    processes = []

    def capture(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        processes.append(process)
        started.set()
        return process

    monkeypatch.setattr(opencode_provider.subprocess, "Popen", capture)
    ready = tmp_path / "ready"
    script = (
        "import pathlib, subprocess, sys; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "pathlib.Path(sys.argv[1]).touch(); "
        "import time; time.sleep(30)"
    )
    job = asyncio.create_task(opencode_provider._run_cancellable(
        [sys.executable, "-c", script, str(ready)], 40,
    ))
    await asyncio.wait_for(started.wait(), 5)
    async with asyncio.timeout(5):
        while not ready.exists():
            await asyncio.sleep(0.02)
    job.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(job, 8)
    assert processes[0].poll() is not None


def test_cli_progress_is_not_used_as_the_training_answer():
    from synapse.api.agent_runs import _final_harness_result, _visible_steps

    outcome = HarnessResult(True, output="Progress\nFinal", events=(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Progress"}},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "private"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Final"}},
        {"type": "turn.completed"},
    ))
    assert _final_harness_result("codex", outcome).output == "Final"
    assert {"type": "item.completed", "action": "command_execution"} in _visible_steps(outcome.events)
    assert "private" not in str(_visible_steps(outcome.events))


def test_claude_api_failure_is_not_a_successful_answer():
    from synapse.api.agent_runs import _final_harness_result

    outcome = HarnessResult(True, output="API Error: 402", events=(
        {"type": "result", "is_error": True, "result": "API Error: 402 quota exhausted"},
    ))
    result = _final_harness_result("claude_code", outcome)
    assert result.success is False
    assert result.error == "Claude Code: ошибка API 402."


def test_autonomy_targets_qwen_instead_of_the_first_downloaded_model(monkeypatch):
    from types import SimpleNamespace

    import synapse.models
    from synapse.growth.autonomy import AutonomyLoop

    other = SimpleNamespace(model_id="Other", local_path="other", status="downloaded")
    qwen = SimpleNamespace(model_id="Qwen/Qwen3-1.7B", local_path="qwen", status="downloaded")
    monkeypatch.setattr(synapse.models, "get_model_registry", lambda: SimpleNamespace(list=lambda: [other, qwen]))
    assert AutonomyLoop._training_model("Qwen/Qwen3-1.7B") is qwen
    assert AutonomyLoop._training_model("Missing") is None
