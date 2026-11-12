"""Grounded self-study must create only source-verified training experience."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from synapse.agents.planner import PlannerAgent
from synapse.core.models import ExecutionContext
from synapse.experience import ExperienceStore
from synapse.growth.autonomy import AutonomyLoop
from synapse.growth.network import GrowthNetwork
from synapse.skills.builtins.self_study import (
    collect_grounded_experience,
    execute_self_study,
)


def _write_readme(workspace: Path) -> Path:
    path = workspace / "README.md"
    path.write_text(
        "# Synapse\n\n"
        "## Назначение\n\n"
        "**Synapse** — автономный агент для программирования и разработки, "
        "который выполняет задачи в локальном workspace и проверяет результаты "
        "независимыми критериями приёмки.\n\n"
        "## Сеть роста\n\n"
        "Успешный маршрут усиливает связь задача → навык, а ошибка тормозит её. "
        "После нескольких успехов путь миелинизируется и становится быстрым "
        "автоматическим маршрутом.\n",
        encoding="utf-8",
    )
    return path


def _ctx(workspace: Path, capabilities=("fs:read",)) -> ExecutionContext:
    return ExecutionContext(
        session_id="self-study-test",
        agent_id="test",
        trace_id="test",
        capabilities=list(capabilities),
        memory_store=SimpleNamespace(workspace_root=str(workspace)),
    )


def test_collect_grounded_experience_writes_verified_records(tmp_path):
    _write_readme(tmp_path)

    result = collect_grounded_experience(tmp_path, max_records=8)

    assert result["success"] is True
    assert result["created"] >= 2
    assert "README.md" in result["documents"]

    store = ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3")
    try:
        records = store.list_records(verified_only=True)
    finally:
        store.close()
    assert len(records) == result["created"]
    for record in records:
        assert record.execution_success is True
        assert record.verifier_passed is True
        assert record.eligibility == "eligible"
        assert record.provider == "documentation"
        assert record.model is None
        assert record.provenance["source"] == "grounded_self_study"
        text = record.feedback["training_text"]
        assert text.startswith("User: ")
        assert "\nAssistant: " in text


def test_collect_grounded_experience_is_idempotent(tmp_path):
    _write_readme(tmp_path)

    first = collect_grounded_experience(tmp_path, max_records=8)
    second = collect_grounded_experience(tmp_path, max_records=8)

    assert first["created"] >= 2
    assert second["created"] == 0
    assert second["success"] is False
    assert any(item["reason"] == "duplicate" for item in second["skipped_details"])


def test_collect_rejects_answers_that_are_not_in_the_source(tmp_path):
    from synapse.skills.builtins import self_study

    _write_readme(tmp_path)
    path = tmp_path / "README.md"
    raw = path.read_text(encoding="utf-8")

    ok, reason = self_study._verify_against_source(
        tmp_path, "README.md", "этой строки нет в документе", 
        self_study.hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )
    assert ok is False
    assert reason == "answer_not_in_source"

    ok, reason = self_study._verify_against_source(
        tmp_path, "README.md", "Synapse", "stale-hash",
    )
    assert ok is False
    assert reason == "source_changed"


@pytest.mark.asyncio
async def test_self_study_skill_requires_fs_read(tmp_path):
    _write_readme(tmp_path)
    result = await execute_self_study(_ctx(tmp_path, capabilities=()))
    assert result["success"] is False
    assert "fs:read" in result["error"]


@pytest.mark.asyncio
async def test_self_study_skill_reports_created_facts(tmp_path):
    _write_readme(tmp_path)
    result = await execute_self_study(_ctx(tmp_path))
    assert result["success"] is True
    assert result["created"] >= 2
    assert "документации" in result["content"]


def test_autonomy_self_study_unblocks_training(tmp_path, monkeypatch):
    """A data-starved loop must study docs, then attempt the gated run."""
    _write_readme(tmp_path)
    loop = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth.sqlite3")
    )
    loop.auto_train_enabled = True
    loop.self_study_enabled = True
    loop.self_study_cooldown = 0.0
    loop.min_records = 1
    loop.min_new_records = 1
    calls: list[bool] = []

    def fake_train():
        calls.append(True)
        return {
            "status": "completed",
            "verified_records": 2,
            "promotion_status": "promoted",
        }

    loop._train_once = fake_train  # type: ignore[method-assign]
    try:
        result = asyncio.run(loop.tick())
    finally:
        loop._release_process_lock()

    assert result["training"]["status"] == "completed"
    assert result["training"]["self_study"]["created"] >= 1
    assert calls == [True]
    study_state = loop.status()["last_self_study_result"]
    assert study_state["created"] >= 1
    assert loop.status()["last_train_status"] == "completed"
    # The study pass must be visible as a real growth route, not only as an
    # experience-store side effect.
    growth = loop.network.status()
    assert growth["events"] >= 1
    assert growth["nodes_by_kind"]["skill"] >= 1
    assert growth["nodes_by_kind"]["provider"] >= 1


def test_new_verified_experience_overrides_completed_cooldown(tmp_path):
    """New data is a legitimate reason to train without waiting a full day."""
    import time

    from synapse.experience import ExperienceRecord

    (tmp_path / ".synapse").mkdir()
    store = ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3")
    for index in range(3):
        store.append(ExperienceRecord(
            task_id=f"fresh-{index}",
            run_id=f"fresh-run-{index}",
            executor="fixture",
            execution_success=True,
            verifier_passed=True,
            verifier_status="passed",
            eligibility="eligible",
            feedback={"training_text": f"User: q{index}\nAssistant: a{index}"},
        ))
    store.close()

    loop = AutonomyLoop(
        tmp_path, growth_network=GrowthNetwork(tmp_path / "growth.sqlite3")
    )
    loop.auto_train_enabled = True
    loop.min_records = 1
    loop.min_new_records = 1
    loop.state["last_train_verified_records"] = 1
    loop.state["last_train_attempt"] = time.time()
    loop.state["last_train_status"] = "completed"

    readiness = loop.training_readiness()
    assert readiness["new_verified_records"] == 2
    assert readiness["ready"] is True
    assert "cooldown" not in readiness["blockers"]


@pytest.mark.asyncio
async def test_planner_routes_documentation_study_to_self_study():
    planner = PlannerAgent()
    plan = await planner.create_plan(
        "Изучи документацию проекта и стань умнее"
    )
    assert plan.steps[0].skill == "self_study"


@pytest.mark.asyncio
async def test_plain_readme_read_stays_read_file():
    planner = PlannerAgent()
    plan = await planner.create_plan("Прочитай README.md")
    assert plan.steps[0].skill == "read_file"
