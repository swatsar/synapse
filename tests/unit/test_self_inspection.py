"""Self-inspection must answer about Synapse itself, using real artifacts."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from synapse.agents.planner import PlannerAgent
from synapse.core.models import ExecutionContext
from synapse.experience import ExperienceRecord, ExperienceStore
from synapse.skills.builtins.self_inspection import execute_self_inspection


def _ctx(workspace, capabilities=("memory:read", "fs:read")) -> ExecutionContext:
    return ExecutionContext(
        session_id="self-inspection-test",
        agent_id="test",
        trace_id="test",
        capabilities=list(capabilities),
        memory_store=SimpleNamespace(workspace_root=str(workspace)),
    )


@pytest.mark.asyncio
async def test_planner_routes_self_study_to_self_inspection():
    planner = PlannerAgent()
    for task in (
        "Изучи себя и напиши что можно улучшить для продуктивного программирования "
        "и разработки и важное чтобы ты развивался",
        "Проанализируй себя: что тебе мешает развиваться?",
        "Study yourself and explain how you learn",
    ):
        plan = await planner.create_plan(task=task)
        assert plan.steps[0].skill == "self_inspection", task
        assert plan.steps[0].params["focus"] == task


@pytest.mark.asyncio
async def test_orchestrator_enforces_self_inspection_without_planner():
    """A missing/failing planner must not turn self-inspection into generic chat."""
    from synapse.core.determinism import (
        DeterministicIDGenerator,
        DeterministicSeedManager,
    )
    from synapse.core.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        DeterministicSeedManager(), DeterministicIDGenerator(), planner=None,
    )
    plan = await orchestrator._plan(
        {"content": "Изучи себя и напиши что можно улучшить", "event_type": "goal"},
        {},
    )
    assert [step["skill"] for step in plan["steps"]] == ["self_inspection"]
    assert plan["steps"][0]["params"]["focus"] == "Изучи себя и напиши что можно улучшить"


@pytest.mark.asyncio
async def test_planner_keeps_project_audit_out_of_self_inspection():
    planner = PlannerAgent()
    plan = await planner.create_plan("Изучи проект и предложи улучшения")
    assert plan.steps[0].skill != "self_inspection"


@pytest.mark.asyncio
async def test_self_inspection_bypasses_planner_llm():
    """A planner model must not rewrite a grounded self-report into advice."""
    class _RecordingLLM:
        def __init__(self):
            self.calls = 0

        async def generate(self, prompt):
            self.calls += 1
            return {"content": json.dumps({"steps": [{
                "step_id": "step_1",
                "action": "Give generic advice",
                "skill": "generic_executor",
                "params": {"task": "generic"},
            }]})}

    llm = _RecordingLLM()
    planner = PlannerAgent(llm_provider=llm)
    plan = await planner.create_plan(
        task="Изучи себя и напиши что можно улучшить для продуктивного программирования",
    )
    assert plan.steps[0].skill == "self_inspection"
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_planner_does_not_confuse_project_audit_with_self_study():
    planner = PlannerAgent()
    plan = await planner.create_plan(task="изучи приложение и его код")
    assert plan.steps[0].skill == "workspace_audit"


@pytest.mark.asyncio
async def test_planner_keeps_explicit_external_delegation():
    planner = PlannerAgent()
    plan = await planner.create_plan(task="передай codex задачу: изучи себя")
    assert plan.steps[0].skill == "external_agent"
    assert plan.steps[0].params["agent"] == "codex"


@pytest.mark.asyncio
async def test_self_inspection_reports_real_growth_and_training_state(tmp_path):
    from synapse.growth import autonomy as autonomy_module
    from synapse.growth import get_autonomy_loop, get_growth_network
    from synapse.growth import network as growth_module

    workspace = tmp_path
    (workspace / ".synapse").mkdir()
    network = get_growth_network(workspace)
    network.record_execution(
        task="write python code",
        skill="code_generator",
        provider="local_transformers",
        model="test-model",
        success=True,
    )
    store = ExperienceStore(workspace / ".synapse" / "experience.sqlite3")
    store.append(ExperienceRecord(
        task_id="task-self-1",
        run_id="run-self-1",
        executor="fixture",
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    ))
    store.close()
    get_autonomy_loop(workspace, growth_network=network)

    try:
        result = await execute_self_inspection(
            _ctx(workspace),
            focus="Изучи себя и напиши что можно улучшить",
        )
    finally:
        growth_module._default_networks.pop(str(workspace.resolve()), None)
        autonomy_module._loops.pop(str(workspace.resolve()), None)

    assert result["success"] is True
    assert result["provider"] == "synapse_self_inspection"
    assert result["growth"]["events"] >= 1
    assert result["experience"]["verified"] == 1
    assert {"growth", "training", "engineering"} <= {
        item["area"] for item in result["findings"]
    }
    assert result["recommendations"]

    content = result["content"]
    assert "Самоинспекция Synapse" in content
    assert "Сеть роста" in content
    assert "Что улучшить" in content
    assert "Самообучение по документации" in content
    # The exact failure reported by the user: generic advice to a human.
    assert "Практикуйтесь" not in content
    assert "Практика - это ключ" not in content
    assert "изучить вас" not in content


@pytest.mark.asyncio
async def test_self_inspection_does_not_claim_a_promoted_adapter_without_one(
    tmp_path, monkeypatch,
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "synapse.models.get_model_registry",
        lambda: SimpleNamespace(list=lambda: []),
    )
    result = await execute_self_inspection(_ctx(tmp_path))
    assert result["success"] is True
    assert result["adapter"]["status"] == "no_local_model"
    assert result["adapter"]["selected"] is False
    assert any(
        "Скачать локальную модель" in item["action"]
        for item in result["recommendations"]
    )


@pytest.mark.asyncio
async def test_self_inspection_requires_read_capabilities(tmp_path):
    result = await execute_self_inspection(_ctx(tmp_path, capabilities=()))
    assert result["success"] is False
    assert "memory:read" in result["error"]


@pytest.mark.asyncio
async def test_self_inspection_answers_what_was_learned_from_past_task(tmp_path):
    """A retrospective question must quote verified learning pairs, not guess.

    Regression: the old planner treated the question as a new learning task and
    the generic executor answered with a canned refusal from the local model.
    """
    from synapse.growth import autonomy as autonomy_module
    from synapse.growth import get_autonomy_loop, get_growth_network
    from synapse.growth import network as growth_module

    workspace = tmp_path
    (workspace / ".synapse").mkdir()
    store = ExperienceStore(workspace / ".synapse" / "experience.sqlite3")
    store.append(ExperienceRecord(
        task_id="learning_loop:security",
        run_id="cycle_1",
        executor="learning_loop",
        objective="обноруживать уязвимости и научись хакерству [Russian]",
        inputs={"teacher_evidence": {"kind": "local", "teacher": "test-teacher"}},
        feedback={"training_text": (
            "User: Как найти уязвимость?\n"
            "Assistant: Нужно проверить входные данные и права доступа."
        )},
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    ))
    # This record was produced by the old misrouting bug. It used the question
    # itself as a topic and must never be quoted back as knowledge.
    store.append(ExperienceRecord(
        task_id="learning_loop:misrouted",
        run_id="cycle_2",
        executor="learning_loop",
        objective=(
            'а что ты узнал когда выполнял это задание: '
            '"научись обноруживать уязвимости и научись хакерству"'
        ),
        feedback={"training_text": (
            "User: Какой из ваших новых знаний вы получили?\n"
            "Assistant: Я получил новую информацию о том, как обрабатывать уязвимости."
        )},
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    ))
    store.close()
    get_autonomy_loop(workspace, growth_network=get_growth_network(workspace))

    try:
        result = await execute_self_inspection(
            _ctx(workspace),
            focus=(
                'а что ты узнал когда выполнял это задание: '
                '"научись обноруживать уязвимости и научись хакерству"'
            ),
        )
    finally:
        growth_module._default_networks.pop(str(workspace.resolve()), None)
        autonomy_module._loops.pop(str(workspace.resolve()), None)

    assert result["success"] is True
    learned = result["experience"]["learned"]
    assert learned["mode"] == "topic"
    assert learned["records"] == 1
    assert learned["items"][0]["teacher"] == "test-teacher"
    assert "Ответ по указанному заданию" in result["content"]
    assert "Нужно проверить входные данные и права доступа" in result["content"]
    assert "Я получил новую информацию" not in result["content"]
    assert "не могу утверждать" not in result["content"]


@pytest.mark.asyncio
async def test_self_inspection_does_not_invent_learning_for_unknown_task(tmp_path):
    from synapse.growth import autonomy as autonomy_module
    from synapse.growth import get_autonomy_loop, get_growth_network
    from synapse.growth import network as growth_module

    workspace = tmp_path
    (workspace / ".synapse").mkdir()
    store = ExperienceStore(workspace / ".synapse" / "experience.sqlite3")
    store.append(ExperienceRecord(
        task_id="task-other",
        run_id="run-other",
        executor="orchestrator.handle",
        objective="напиши функцию",
        execution_success=True,
    ))
    store.close()
    get_autonomy_loop(workspace, growth_network=get_growth_network(workspace))

    try:
        result = await execute_self_inspection(
            _ctx(workspace),
            focus='что ты узнал когда выполнял задание: "квантовая хромодинамика"',
        )
    finally:
        growth_module._default_networks.pop(str(workspace.resolve()), None)
        autonomy_module._loops.pop(str(workspace.resolve()), None)

    learned = result["experience"]["learned"]
    assert learned["mode"] == "topic"
    assert learned["records"] == 0
    assert "не могу утверждать" in result["content"]


@pytest.mark.asyncio
async def test_self_inspection_reports_latest_learning_without_named_task(tmp_path):
    from synapse.growth import autonomy as autonomy_module
    from synapse.growth import get_autonomy_loop, get_growth_network
    from synapse.growth import network as growth_module

    workspace = tmp_path
    (workspace / ".synapse").mkdir()
    store = ExperienceStore(workspace / ".synapse" / "experience.sqlite3")
    store.append(ExperienceRecord(
        task_id="learning_loop:python",
        run_id="cycle_1",
        executor="learning_loop",
        objective="основы Python [Russian]",
        feedback={"training_text": (
            "User: Что такое список?\n"
            "Assistant: Список — это упорядоченная изменяемая коллекция."
        )},
        execution_success=True,
        verifier_passed=True,
        verifier_status="passed",
        eligibility="eligible",
    ))
    store.close()
    get_autonomy_loop(workspace, growth_network=get_growth_network(workspace))

    try:
        result = await execute_self_inspection(
            _ctx(workspace), focus="чему ты научился?",
        )
    finally:
        growth_module._default_networks.pop(str(workspace.resolve()), None)
        autonomy_module._loops.pop(str(workspace.resolve()), None)

    learned = result["experience"]["learned"]
    assert learned["mode"] == "latest"
    assert learned["topic"] is None
    assert learned["records"] == 1
    assert "Список — это упорядоченная изменяемая коллекция" in result["content"]
