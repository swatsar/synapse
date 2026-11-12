"""Tests for the mycelial growth network and its orchestrator wiring."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from synapse.core.determinism import DeterministicIDGenerator, DeterministicSeedManager
from synapse.core.orchestrator import Orchestrator
from synapse.growth.network import GrowthNetwork


def test_record_execution_creates_nodes_and_edges():
    network = GrowthNetwork(":memory:")
    result = network.record_execution(
        task="write a Python function",
        skill="code_generator",
        provider="opencode",
        model="opencode/test-free",
        success=True,
    )
    assert result["success"] is True
    assert result["events"] == 1

    status = network.status()
    assert status["status"] == "growing"
    assert status["events"] == 1
    assert status["nodes_by_kind"]["task"] == 1
    assert status["nodes_by_kind"]["skill"] == 1
    assert status["nodes_by_kind"]["provider"] == 1
    assert status["nodes_by_kind"]["model"] == 1
    relations = {path["relation"] for path in network.recent_paths()}
    assert {"activates", "runs_on", "answered_by", "serves"} <= relations


def test_repeated_success_myelinates_and_failure_inhibits():
    network = GrowthNetwork(":memory:")
    for _ in range(3):
        network.record_execution(task="same task", skill="stable_skill", success=True)
    for _ in range(2):
        network.record_execution(task="same task", skill="failing_skill", success=False)

    status = network.status()
    fast = {(path["source"], path["target"]) for path in status["fast_paths"]}
    assert ("same task", "stable_skill") in fast
    assert status["myelinated_paths"] >= 1

    weak = {(path["source"], path["target"]): path for path in status["weak_paths"]}
    assert ("same task", "failing_skill") in weak
    assert weak[("same task", "failing_skill")]["failures"] >= 1


def test_consolidation_decays_and_prunes_weak_failure_paths():
    network = GrowthNetwork(":memory:")
    network.record_execution(task="fragile task", skill="bad_skill", success=False)
    summary = network.consolidate()
    assert summary["pass"] == 1
    assert summary["consolidations"] if "consolidations" in summary else True
    assert network.status()["consolidation_passes"] == 1
    # A single failure is weak but not yet pruned; repeated consolidation must
    # eventually remove the path instead of keeping dead weight forever.
    for _ in range(10):
        network.consolidate()
    weak = {(path["source"], path["target"]) for path in network.status()["weak_paths"]}
    assert ("fragile task", "bad_skill") not in weak


def test_suggest_skill_recalls_similar_successful_task():
    network = GrowthNetwork(":memory:")
    for _ in range(3):
        network.record_execution(
            task="write a Python function that sorts numbers",
            skill="code_generator",
            success=True,
        )
    network.record_execution(
        task="write a Python function that sorts numbers",
        skill="broken_skill",
        success=False,
    )

    suggestions = network.suggest_skill(
        "write a Python function that sorts a list",
        candidates=["code_generator", "broken_skill"],
    )
    assert suggestions
    assert suggestions[0]["skill"] == "code_generator"
    assert suggestions[0]["similarity"] > 0
    assert all(item["skill"] != "broken_skill" for item in suggestions)


def test_suggest_route_recalls_successful_provider_and_model():
    """The learned path must be reusable for routing, not only for skills."""
    network = GrowthNetwork(":memory:")
    for _ in range(3):
        network.record_execution(
            task="write a Python function that sorts numbers",
            skill="code_generator",
            provider="opencode",
            model="opencode/test-free",
            success=True,
        )
    network.record_execution(
        task="write a Python function that sorts numbers",
        skill="code_generator",
        provider="bad_provider",
        model="bad-model",
        success=False,
    )

    routes = network.suggest_route("write a Python function that sorts a list")
    assert routes
    assert routes[0]["provider"] == "opencode"
    assert routes[0]["model"] == "opencode/test-free"
    assert routes[0]["successes"] >= 3
    assert all(route["model"] != "bad-model" for route in routes)


def test_coactivation_links_skills_that_fire_together():
    """Skills used in one successful task become an associative path."""
    network = GrowthNetwork(":memory:")
    result = network.record_coactivation(
        task="build and verify a module",
        skills=["code_generator", "test_runner"],
        success=True,
    )
    assert result["coactivations"] == 1

    status = network.status()
    assert status["coactivation_paths"] == 2
    paths = network.recent_paths()
    coactivated = {
        (path["source"], path["target"])
        for path in paths
        if path["relation"] == "co_activates"
    }
    assert ("code_generator", "test_runner") in coactivated
    assert ("test_runner", "code_generator") in coactivated

    # A single skill cannot co-activate with itself.
    single = network.record_coactivation(task="alone", skills=["code_generator"])
    assert single["coactivations"] == 0


def test_consolidation_replays_myelinated_paths_before_decay():
    """Consolidation must replay learned fast paths, not only decay them."""
    network = GrowthNetwork(":memory:")
    for _ in range(3):
        network.record_execution(
            task="repeated task", skill="stable_skill", success=True,
        )

    before = next(
        path["weight"]
        for path in network.status()["fast_paths"]
        if path["source"] == "repeated task" and path["target"] == "stable_skill"
    )
    summary = network.consolidate()
    assert summary["replayed_paths"] >= 1
    assert summary["replay_gain"] > 1.0

    after = next(
        path["weight"]
        for path in summary["fast_paths"]
        if path["source"] == "repeated task" and path["target"] == "stable_skill"
    )
    # Replay gain (1.05) outweighs decay (0.97), so a well-used path grows
    # during sleep instead of slowly fading like an unused one.
    assert after > before


def test_suggest_skill_follows_successful_coactivation_partner():
    """Recall must traverse learned skill associations, not only direct paths."""
    network = GrowthNetwork(":memory:")
    for _ in range(3):
        network.record_execution(
            task="write python sorting code", skill="code_generator", success=True,
        )
    network.record_coactivation(
        task="write python sorting code",
        skills=["code_generator", "test_runner"],
        success=True,
    )

    suggestions = network.suggest_skill(
        "write python sorting code",
        candidates=["code_generator", "test_runner"],
    )
    by_skill = {item["skill"]: item for item in suggestions}
    assert "code_generator" in by_skill
    partner = by_skill.get("test_runner")
    assert partner is not None
    assert partner["relation"] == "co_activation"
    assert partner["via_skill"] == "code_generator"
    assert partner["score"] < by_skill["code_generator"]["score"]


def test_failed_coactivation_is_not_recommended():
    """A failing association must be inhibited, never recalled as a partner."""
    network = GrowthNetwork(":memory:")
    for _ in range(3):
        network.record_execution(
            task="write python sorting code", skill="code_generator", success=True,
        )
    for _ in range(3):
        network.record_coactivation(
            task="write python sorting code",
            skills=["code_generator", "broken_skill"],
            success=False,
        )

    suggestions = network.suggest_skill(
        "write python sorting code",
        candidates=["code_generator", "broken_skill"],
    )
    assert suggestions
    assert all(item["skill"] != "broken_skill" for item in suggestions)


def test_growth_network_persists_between_instances(tmp_path):
    db_path = tmp_path / "growth.sqlite3"
    first = GrowthNetwork(db_path)
    first.record_execution(task="persistent task", skill="memory_skill", success=True)
    first.close()

    second = GrowthNetwork(db_path)
    status = second.status()
    assert status["events"] == 1
    assert status["nodes_by_kind"]["task"] == 1
    second.close()


def _orchestrator(network):
    return Orchestrator(
        seed_manager=DeterministicSeedManager(),
        id_generator=DeterministicIDGenerator(),
        growth_network=network,
    )


class _Record:
    def __init__(self, name):
        self.manifest = SimpleNamespace(name=name, required_capabilities=[])


class _FakeRegistry:
    def __init__(self, handlers):
        self.handlers = handlers
        self.calls: list[str] = []
        self._records = [_Record(name) for name in handlers]

    def get_active_skills(self):
        return self._records

    async def execute(self, name, context, **params):
        self.calls.append(name)
        handler = self.handlers[name]
        if isinstance(handler, Exception):
            raise handler
        return handler


def test_orchestrator_records_execution_paths():
    network = GrowthNetwork(":memory:")
    registry = _FakeRegistry({
        "alpha_skill": {"success": True, "provider": "test_provider", "model": "test-model"},
        "generic_executor": {"success": True},
    })
    orchestrator = _orchestrator(network)
    orchestrator.skill_registry = registry
    plan = {
        "plan_id": "plan-growth",
        "goal": "execute alpha task",
        "steps": [{"step_id": "1", "skill": "alpha_skill", "params": {"task": "hi"}}],
    }

    result = asyncio.run(orchestrator._act(plan))
    assert result["success"] is True
    status = network.status()
    assert status["events"] == 1
    paths = network.recent_paths()
    assert any(path["relation"] == "activates" and path["target"] == "alpha_skill" for path in paths)
    assert any(path["relation"] == "runs_on" and path["target"] == "test_provider" for path in paths)


def test_orchestrator_uses_learned_path_for_unknown_skill():
    network = GrowthNetwork(":memory:")
    for _ in range(3):
        network.record_execution(
            task="write python sorting code",
            skill="alpha_skill",
            success=True,
        )
    registry = _FakeRegistry({
        "alpha_skill": {"success": True, "provider": "test_provider", "model": "test-model"},
        "generic_executor": {"success": True},
    })
    orchestrator = _orchestrator(network)
    orchestrator.skill_registry = registry
    plan = {
        "plan_id": "plan-recall",
        "goal": "write python sorting code",
        "steps": [{"step_id": "1", "skill": "unknown_xyz", "params": {"task": "sort"}}],
    }

    result = asyncio.run(orchestrator._act(plan))
    assert result["success"] is True
    # The unknown name is tried first (LookupError), then the learned path is
    # recalled instead of jumping straight to generic_executor.
    assert registry.calls == ["unknown_xyz", "alpha_skill"]
    assert network.status()["events"] == 4


def test_orchestrator_learn_records_consolidation_path():
    network = GrowthNetwork(":memory:")

    class _LearningEngine:
        async def process(self, *, result, task, skill_name):
            return {"ok": True}

    orchestrator = _orchestrator(network)
    orchestrator.learning_engine = _LearningEngine()
    plan = {"goal": "learn something", "steps": [{"skill": "alpha_skill"}]}
    evaluation = {"success": True, "score": 1.0}
    action_result = {"success": True, "steps_completed": 1, "steps_total": 1}

    learning = asyncio.run(orchestrator._learn({}, plan, action_result, evaluation))
    assert learning["stored"] is True
    assert learning["growth_recorded"] is True
    skill_nodes = network.status()["nodes_by_kind"]
    assert skill_nodes["skill"] == 1
    paths = network.recent_paths()
    assert any(path["target"] == "learning_engine" for path in paths)
