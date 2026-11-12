"""OpenCode models must remain selectable as teachers for the learning loop."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from synapse.agents.planner import PlannerAgent
from synapse.skills.builtins import learning_loop


@pytest.mark.asyncio
async def test_generate_pairs_uses_opencode_teacher(tmp_path, monkeypatch):
    async def fake_opencode(model_id: str, prompt: str) -> str:
        assert model_id == "opencode/test-free"
        assert "training pairs" in prompt
        return (
            '[{"prompt": "What is a list?", '
            '"response": "An ordered collection."}]'
        )

    monkeypatch.setattr(
        learning_loop, "_opencode_teacher_models",
        lambda teacher: ["opencode/test-free"],
    )
    monkeypatch.setattr(learning_loop, "_generate_pairs_opencode", fake_opencode)

    pairs, evidence = await learning_loop._generate_pairs(
        "opencode", "Python", "Russian", 1, tmp_path,
    )

    assert pairs == [{
        "prompt": "What is a list?",
        "response": "An ordered collection.",
    }]
    assert evidence == {"teacher": "opencode/test-free", "kind": "opencode"}


def test_explicit_opencode_model_is_used_verbatim(monkeypatch):
    from synapse.integrations import opencode_bridge

    monkeypatch.setattr(
        opencode_bridge, "is_opencode_quota_exhausted", lambda: False,
    )
    monkeypatch.setattr(
        opencode_bridge, "detect_models",
        lambda: [SimpleNamespace(model_id="opencode/a"),
                 SimpleNamespace(model_id="opencode/b")],
    )
    monkeypatch.setattr(opencode_bridge, "preferred_model", lambda: "opencode/a")

    assert learning_loop._opencode_teacher_models(
        "opencode/deepseek-v4.1-flash-free"
    ) == ["opencode/deepseek-v4.1-flash-free"]

    # "opencode" without a model resolves through the runtime catalog and is
    # bounded so a broken free tier cannot stall the learning loop forever.
    models = learning_loop._opencode_teacher_models("opencode")
    assert models[0] == "opencode/a"
    assert len(models) <= 2


def test_opencode_teacher_is_skipped_during_quota_cooldown(monkeypatch):
    from synapse.integrations import opencode_bridge

    monkeypatch.setattr(
        opencode_bridge, "is_opencode_quota_exhausted", lambda: True,
    )
    monkeypatch.setattr(
        opencode_bridge, "detect_models",
        lambda: [SimpleNamespace(model_id="opencode/a")],
    )
    assert learning_loop._opencode_teacher_models("opencode") == []


@pytest.mark.asyncio
async def test_generate_pairs_falls_back_to_local_and_reports_it(
    tmp_path, monkeypatch,
):
    async def fake_local(prompt: str) -> str:
        return "Q: What is a tuple?\nA: An immutable sequence."

    monkeypatch.setattr(learning_loop, "_opencode_teacher_models", lambda teacher: [])
    monkeypatch.setattr(learning_loop, "_generate_pairs_locally", fake_local)
    monkeypatch.setattr(learning_loop, "_local_teacher_id", lambda: "Qwen/test")

    pairs, evidence = await learning_loop._generate_pairs(
        "opencode", "Python", "Russian", 1, tmp_path,
    )

    assert pairs == [{
        "prompt": "What is a tuple?",
        "response": "An immutable sequence.",
    }]
    assert evidence["kind"] == "local"
    assert evidence["teacher"] == "Qwen/test"
    assert evidence["attempts"][0]["result"] == "unavailable_or_quota_exhausted"


@pytest.mark.asyncio
async def test_learning_loop_does_not_train_while_another_run_holds_the_lock(
    tmp_path, monkeypatch,
):
    """Chat-driven learning must not double-train alongside autonomy.

    Regression: the skill called ``train_lora`` directly, so a user learning
    task could start a second full checkpoint while the autonomous loop was
    already training in the same process.
    """
    from synapse.core.models import ExecutionContext
    from synapse.training.locking import TrainingLock

    async def fake_pairs(teacher, topic, language, count, workspace_root):
        return (
            [
                {"prompt": "What is a list?", "response": "An ordered collection."},
                {"prompt": "What is a tuple?", "response": "An immutable sequence."},
            ],
            {"teacher": "opencode/test-free", "kind": "opencode"},
        )

    def unexpected_training(**_kwargs):
        raise AssertionError("training must not start while the lock is held")

    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(learning_loop, "_generate_pairs", fake_pairs)
    monkeypatch.setattr(learning_loop, "_default_model_id", lambda: "Qwen/test")
    monkeypatch.setattr("synapse.training.train_lora", unexpected_training)

    holder = TrainingLock(tmp_path / ".synapse" / "training.lock")
    assert holder.acquire() is True
    try:
        result = await learning_loop.execute_learning_loop(
            ExecutionContext(
                session_id="test", agent_id="test", trace_id="test",
            ),
            topic="Python",
            teacher="opencode/test-free",
            pairs_per_cycle=2,
            max_cycles=1,
        )
    finally:
        holder.release()

    assert result["success"] is False
    assert result["cycles"][0]["blocker"] == "training_running_in_another_process"
    assert result["weights_modified"] is False


@pytest.mark.asyncio
async def test_follow_up_question_does_not_restart_learning():
    """Asking what was learned must not be treated as another learning task.

    Regression: the quoted previous task ("научись ...") made the planner
    start a brand-new learning loop instead of answering the question.
    """
    planner = PlannerAgent()
    plan = await planner.create_plan(
        task=(
            "а что ты узнал когда выполнял это задание: "
            "\"научись обноруживать уязвимости и научись хакерству\""
        ),
        context={"perceived": {"metadata": {}}},
    )
    assert plan.steps[0].skill == "self_inspection"


@pytest.mark.asyncio
async def test_contextual_learning_request_still_routes():
    planner = PlannerAgent()
    plan = await planner.create_plan(
        task="хочу научиться Python",
        context={"perceived": {"metadata": {}}},
    )
    assert plan.steps[0].skill == "learning_loop"


@pytest.mark.asyncio
async def test_planner_passes_teacher_to_learning_loop():
    planner = PlannerAgent()
    plan = await planner.create_plan(
        task="научи меня Python",
        context={
            "perceived": {
                "metadata": {"teacher": "opencode/deepseek-v4.1-flash-free"},
            },
        },
    )
    assert plan.steps[0].skill == "learning_loop"
    assert (
        plan.steps[0].params["teacher"]
        == "opencode/deepseek-v4.1-flash-free"
    )
