"""Regression tests for the issues reported from the running app.

Covers:
- "Active skill not found: code_generator / data_processor"
- "Required container isolation backend is not available"
- chat answers being truncated by a small generation budget
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from synapse.core.isolation_policy import RuntimeIsolationType
from synapse.core.models import ExecutionContext, SkillManifest
from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard


def _orchestrator(tmp_path):
    from synapse.core.orchestrator import build_orchestrator

    return build_orchestrator(
        db_path=str(tmp_path / "memory.sqlite3"),
        vector_persist_dir=str(tmp_path / "vectors"),
        workspace_root=str(tmp_path / "workspace"),
    )


def test_planner_skills_are_registered(tmp_path):
    """code_generator/data_processor/write_file/web_search must exist as skills."""
    orchestrator = _orchestrator(tmp_path)
    names = {record.manifest.name for record in orchestrator.skill_registry.get_active_skills()}
    assert {"code_generator", "data_processor", "write_file", "web_search"} <= names


def test_model_backed_builtins_run_in_process(tmp_path):
    """Model-backed trusted built-ins must not be pushed into the 60s worker.

    A worker subprocess reloads the checkpoint and is killed after the guard's
    default CPU budget, so code generation would always time out even though
    the skill exists. They opt into main-process execution explicitly.
    """
    orchestrator = _orchestrator(tmp_path)
    manifests = {
        record.manifest.name: record.manifest
        for record in orchestrator.skill_registry.get_active_skills()
    }
    for name in ("code_generator", "data_processor"):
        assert manifests[name].isolation_type == "none"
    # Long-running isolated skills get a real budget instead of 60s.
    assert manifests["learning_loop"].timeout_seconds >= 600
    assert manifests["external_agent"].timeout_seconds >= 600


def test_trusted_builtin_can_execute_in_process_without_worker():
    """isolation_type='none' must be honoured for trusted built-ins only."""
    import asyncio
    import os

    from synapse.skills.dynamic.registry import SkillRegistry

    caps = CapabilityManager()
    caps.grant("fs:read")
    registry = SkillRegistry(capability_manager=caps)

    def handler(context, **params):
        return {"success": True, "pid": os.getpid()}

    registry.register_builtin(
        SkillManifest(
            name="inproc_model_skill",
            risk_level=2,
            trust_level="trusted",
            required_capabilities=["fs:read"],
            isolation_type="none",
        ),
        handler,
    )
    context = ExecutionContext(
        session_id="s", agent_id="a", trace_id="t", capabilities=["fs:read"]
    )
    result = asyncio.run(registry.execute("inproc_model_skill", context=context))
    assert result["success"] is True
    assert result["pid"] == os.getpid()
    assert "worker_pid" not in result


def test_unverified_skill_cannot_opt_into_main_process():
    """The opt-out is restricted to trusted built-ins below the risk boundary."""
    import asyncio
    import uuid

    from synapse.skills.dynamic.registry import SkillLifecycleStatus, SkillRecord, SkillRegistry

    caps = CapabilityManager()
    caps.grant("fs:read")
    registry = SkillRegistry(capability_manager=caps)

    def handler(context, **params):  # pragma: no cover - must not run
        return {"success": True}

    manifest = SkillManifest(
        name="unverified_inproc",
        risk_level=2,
        trust_level="unverified",
        required_capabilities=["fs:read"],
        isolation_type="none",
    )
    # register_builtin forces trust_level="trusted"; simulate a generated skill
    # by inserting the record through the normal lifecycle path instead.
    skill_id = str(uuid.uuid4())
    registry._registry[skill_id] = SkillRecord(
        skill_id=skill_id,
        manifest=manifest,
        handler=handler,
        status=SkillLifecycleStatus.ACTIVE,
        is_builtin=False,
    )
    context = ExecutionContext(
        session_id="s", agent_id="a", trace_id="t", capabilities=["fs:read"]
    )

    # It must still be isolated, and the isolated worker cannot pickle a local
    # closure, which proves execution did not happen in the main process.
    with pytest.raises(Exception):
        asyncio.run(registry.execute("unverified_inproc", context=context))


def test_manifest_timeout_is_used_for_worker_budget():
    """A manifest timeout must override the guard's 60-second default."""
    from synapse.skills.dynamic.registry import SkillRegistry

    registry = SkillRegistry(capability_manager=CapabilityManager())
    limits = registry._worker_limits(
        SkillManifest(name="long_skill", timeout_seconds=1800)
    )
    assert limits["cpu_seconds"] == 1800


def test_planner_learning_request_is_low_risk():
    """Chat-driven training must not be blocked by the approval gate."""
    import asyncio

    from synapse.agents.planner import PlannerAgent

    planner = PlannerAgent()
    plan = asyncio.run(planner.create_plan("обучи себя языку Python"))
    assert plan.steps[0].skill == "learning_loop"
    assert plan.risk_level <= 2


def test_unknown_skill_degrades_to_generic_executor(tmp_path, monkeypatch):
    """A planner vocabulary mismatch must not abort with Active skill not found."""
    import asyncio

    from synapse.skills.builtins import local_executor

    monkeypatch.setattr(local_executor, "_preferred_external_model", lambda: None)
    orchestrator = _orchestrator(tmp_path)
    plan = {
        "plan_id": "plan-unknown",
        "goal": "unknown skill regression",
        "risk_level": 1,
        "required_capabilities": ["memory:read"],
        "steps": [{
            "step_id": "step_1",
            "action": "Do something unsupported",
            "skill": "definitely_not_registered_xyz",
            "params": {"task": "hello"},
            "required_capabilities": ["memory:read"],
            "risk_level": 1,
        }],
    }
    result = asyncio.run(orchestrator._act(plan))
    errors = " ".join(str(item.get("error", "")) for item in result["errors"])
    assert "Active skill not found" not in errors


def test_container_requirement_degrades_to_subprocess(monkeypatch):
    """Missing Docker must downgrade execution instead of refusing to run.

    The isolation policy still reports CONTAINER (so compliance tooling sees
    the requirement), but the worker backend must actually execute high-risk
    work in a subprocess when no Docker daemon is available.
    """
    import asyncio
    import os

    from synapse.runtime.worker_backend import IsolatedWorkerBackend

    monkeypatch.setattr(
        "synapse.runtime.worker_backend.is_docker_available", lambda: False
    )
    caps = CapabilityManager()
    caps.grant("fs:read")
    guard = ExecutionGuard(capability_manager=caps)
    manifest = SkillManifest(
        name="risk4_skill",
        risk_level=4,
        trust_level="trusted",
        required_capabilities=["fs:read"],
    )
    skill = SimpleNamespace(manifest=manifest)
    context = ExecutionContext(
        session_id="s",
        agent_id="a",
        trace_id="t",
        capabilities=["fs:read"],
        approval_granted=True,
    )

    check = asyncio.run(guard.check_execution_allowed(skill, context))
    assert check.allowed is True
    # Policy still reports the container requirement...
    assert check.required_isolation == RuntimeIsolationType.CONTAINER

    # ...while the worker backend degrades to a real subprocess run.
    code = """
import os
def handler():
    return {"pid": os.getpid(), "success": True}
"""
    result = asyncio.run(
        IsolatedWorkerBackend.run_skill(
            "container_fallback_test", code, isolation_level="container"
        )
    )
    assert result.get("success") is True
    assert result.get("worker_pid") != os.getpid()
    assert result.get("output", {}).get("pid") != os.getpid()


def test_chat_generation_budget_prevents_truncation(tmp_path, monkeypatch):
    """A plain chat turn must request a non-tiny generation budget."""
    import asyncio

    from synapse.skills.builtins import local_executor

    registry = SimpleNamespace(
        list=lambda: [
            SimpleNamespace(
                status="downloaded",
                local_path=str(tmp_path / "model"),
                model_id="local/test",
            )
        ]
    )
    captured: dict = {}

    class FakeProvider:
        async def generate(self, prompt, **kwargs):
            captured.update(kwargs)
            return {
                "content": "полный ответ",
                "provider": "local_transformers",
                "finish_reason": "stop",
                "truncated": False,
            }

    monkeypatch.setattr("synapse.models.get_model_registry", lambda: registry)
    monkeypatch.setattr(
        "synapse.llm.local_model.get_local_provider", lambda *a, **k: FakeProvider()
    )
    monkeypatch.setattr(local_executor, "_preferred_external_model", lambda: None)

    context = ExecutionContext(
        session_id="s", agent_id="a", trace_id="t", capabilities=["memory:read"]
    )
    result = asyncio.run(local_executor.execute_local_task(context, task="привет"))
    assert result["success"] is True
    assert int(captured.get("max_new_tokens", 0)) >= 2048
    assert result["finish_reason"] == "stop"
    assert result["truncated"] is False


def test_local_model_applies_chat_template_and_stops_at_eos():
    """Instruct checkpoints must get a chat template, not a raw completion."""
    from synapse.llm.local_model import LocalTransformersProvider

    class FakeTokenizer:
        chat_template = "{{ messages }}"

        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
            assert tokenize is False
            assert add_generation_prompt is True
            # The checkpoint must be told that it is Synapse, not a stranger.
            assert messages[0]["role"] == "system"
            assert "Synapse" in messages[0]["content"]
            user = next(item for item in messages if item["role"] == "user")
            return f"<user>{user['content']}</user><assistant>"

    class RawTokenizer:
        chat_template = None

    assert (
        LocalTransformersProvider._format_prompt(FakeTokenizer(), "привет")
        == "<user>привет</user><assistant>"
    )
    assert LocalTransformersProvider._format_prompt(RawTokenizer(), "prompt") == "prompt"


@pytest.mark.asyncio
async def test_opencode_endpoint_is_primary_and_velly_is_deprecated(monkeypatch):
    """OpenCode is the primary status surface; Velly only stays as a legacy alias."""
    from fastapi.testclient import TestClient

    from synapse.api.app import app

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    with TestClient(app) as client:
        velly = client.get("/api/v1/integrations/velly")
        opencode = client.get("/api/v1/integrations/opencode")
    assert velly.status_code == 200
    assert opencode.status_code == 200
    payload = opencode.json()
    assert payload["runtime"] == "opencode"
    assert payload["status"] in {"ready", "quota_exhausted", "degraded", "not_found"}
    assert velly.json()["deprecated"] is True
    assert velly.json()["opencode"]["runtime"] == "opencode"


def test_opencode_quota_failure_degrades_to_local_model(monkeypatch, tmp_path):
    """An explicit OpenCode model must fall back to downloaded weights.

    Free OpenCode quotas are account-wide, so a single quota error should not
    leave the user without an answer when the local checkpoint is available.
    """
    import asyncio

    from synapse.skills.builtins import local_executor

    monkeypatch.setenv("SYNAPSE_OPENCODE_HEALTH_FILE", str(tmp_path / "health.json"))
    monkeypatch.setattr(local_executor, "_is_opencode_model", lambda model: True)

    async def fake_router(task, prompt, model_id):
        return {
            "success": False,
            "error": "All available model candidates failed.",
            "provider": "opencode",
            "model": model_id,
            "attempts": [{
                "provider": "opencode",
                "model": model_id,
                "error": "Free usage limit reached. Subscribe to OpenCode Go.",
            }],
        }

    async def fake_local(manifest, prompt, max_new_tokens):
        return {
            "success": True,
            "content": "local answer",
            "provider": "local_transformers",
            "model": "local-test-model",
            "max_new_tokens": max_new_tokens,
            "finish_reason": "stop",
            "truncated": False,
        }

    monkeypatch.setattr(local_executor, "_router_result", fake_router)
    monkeypatch.setattr(
        local_executor, "_downloaded_manifests", lambda: [SimpleNamespace(model_id="local-test-model", local_path=str(tmp_path))]
    )
    monkeypatch.setattr(local_executor, "_local_response", fake_local)

    context = ExecutionContext(
        session_id="s", agent_id="a", trace_id="t", capabilities=["memory:read"]
    )
    result = asyncio.run(
        local_executor.execute_local_task(
            context,
            task="hello",
            model="opencode/deepseek-v4.1-flash-free",
        )
    )
    assert result["success"] is True
    assert result["content"] == "local answer"
    assert result["fallback_from"] == "opencode/deepseek-v4.1-flash-free"
    assert "Free usage limit" in result["fallback_reason"]
    assert result["provider"] == "local_transformers"


def test_opencode_quota_is_cached_and_resettable(monkeypatch, tmp_path):
    """The quota circuit must stop repeated CLI calls and survive status reads."""
    from synapse.integrations import opencode_bridge

    monkeypatch.setenv("SYNAPSE_OPENCODE_HEALTH_FILE", str(tmp_path / "health.json"))
    monkeypatch.setenv("SYNAPSE_OPENCODE_QUOTA_COOLDOWN", "120")
    opencode_bridge.reset_opencode_health()
    try:
        kind = opencode_bridge.record_opencode_failure(
            "Free usage limit reached. Subscribe to OpenCode Go to keep going."
        )
        assert kind == "quota"
        assert opencode_bridge.is_opencode_quota_exhausted() is True
        state = opencode_bridge.quota_status()
        assert state["exhausted"] is True
        assert state["retry_after_seconds"] > 0
        assert opencode_bridge.preferred_model() is None
        assert opencode_bridge.opencode_status()["status"] == "quota_exhausted"
    finally:
        opencode_bridge.reset_opencode_health()
    assert opencode_bridge.is_opencode_quota_exhausted() is False
    assert opencode_bridge.opencode_status()["status"] in {"ready", "degraded", "not_found"}


def test_find_opencode_cli_discovers_standalone_install(monkeypatch, tmp_path):
    """OpenCode must be found on its own, not only inside the Velly bundle."""
    from synapse.integrations import opencode_bridge

    monkeypatch.delenv("SYNAPSE_OPENCODE_CLI", raising=False)
    # Discovery caches the first verified binary for the process lifetime.
    # A test that rewrites the filesystem layout must clear that cache.
    monkeypatch.setattr(opencode_bridge, "_WORKING_CLI", None)
    monkeypatch.setattr(opencode_bridge.shutil, "which", lambda _name: None)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "ProgramFiles"))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "ProgramFilesX86"))
    monkeypatch.delenv("ChocolateyInstall", raising=False)
    local_appdata = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setattr(
        opencode_bridge.Path, "home", classmethod(lambda _cls: tmp_path / "home"),
    )
    binary = local_appdata / "Programs" / "opencode" / "bin" / "opencode.exe"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"")

    assert opencode_bridge.find_opencode_cli() == binary


def test_find_opencode_cli_skips_shim_that_cannot_list_models(monkeypatch, tmp_path):
    """A same-named CLI shim must not hide the real OpenCode catalog.

    Regression: the first `opencode` on PATH was a vendored `vela` CLI that
    printed help and exited 1, so /growth/teachers showed zero OpenCode
    teachers even though a working install existed.
    """
    from synapse.integrations import opencode_bridge

    shim = tmp_path / "shim" / "opencode.exe"
    shim.parent.mkdir(parents=True)
    shim.write_bytes(b"")
    real = tmp_path / "real" / "opencode.exe"
    real.parent.mkdir(parents=True)
    real.write_bytes(b"")

    monkeypatch.setattr(opencode_bridge, "_WORKING_CLI", None)
    monkeypatch.setattr(opencode_bridge, "_MODEL_PROBE_CACHE", {})
    monkeypatch.setattr(
        opencode_bridge, "_opencode_cli_candidates", lambda: [shim, real],
    )
    probed: list = []

    def fake_models(cli, *, force=False):
        probed.append(cli)
        return ["opencode/test-free"] if cli == real else []

    monkeypatch.setattr(opencode_bridge, "_read_cli_models", fake_models)

    assert opencode_bridge.find_opencode_cli() == real
    assert probed == [shim, real]
    # The working binary is remembered instead of re-probing every request.
    assert opencode_bridge.find_opencode_cli() == real
    assert probed == [shim, real]


def test_opencode_provider_fails_fast_while_quota_is_cached(monkeypatch, tmp_path):
    """The provider must not spawn the CLI when the quota circuit is open."""
    import asyncio

    from synapse.integrations import opencode_bridge
    from synapse.llm.opencode_provider import OpenCodeCLIProvider, OpenCodeQuotaExceeded

    monkeypatch.setenv("SYNAPSE_OPENCODE_HEALTH_FILE", str(tmp_path / "health.json"))
    monkeypatch.setenv("SYNAPSE_OPENCODE_QUOTA_COOLDOWN", "120")
    opencode_bridge.reset_opencode_health()
    opencode_bridge.record_opencode_failure("Free usage limit reached.")

    def _must_not_spawn():
        raise AssertionError("quota circuit should prevent spawning the CLI")

    monkeypatch.setattr(
        "synapse.llm.opencode_provider.find_opencode_cli", _must_not_spawn
    )
    try:
        with pytest.raises(OpenCodeQuotaExceeded):
            asyncio.run(OpenCodeCLIProvider("opencode/any-free").generate("hello"))
    finally:
        opencode_bridge.reset_opencode_health()


def test_model_listing_endpoints_do_not_require_container_isolation(monkeypatch, tmp_path):
    """Model discovery must never fall through to the container worker path.

    Regression: /models used to fail with "Required container isolation backend
    is not available. Refusing execution without LocalOS fallback."
    """
    from fastapi.testclient import TestClient

    from synapse.api.app import app

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))

    with TestClient(app) as client:
        for path in (
            "/api/v1/router/catalog",
            "/api/v1/runtime-config/models",
            "/api/v1/providers",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "Required container isolation backend" not in response.text, path


@pytest.mark.asyncio
async def test_router_catalog_discovers_opencode_models(monkeypatch):
    """Only models the CLI actually reports may enter the router catalog."""
    from synapse.llm.omnirouter import OmniRouter

    class FakeRegistry:
        async def list(self):
            return []

        async def test_connection(self, *args, **kwargs):
            return SimpleNamespace(success=False)

        async def discover_models(self, *args, **kwargs):
            return []

    router = OmniRouter()

    async def fake_probe(timeout=2.0):
        router._availability["ollama"] = False
        return []

    async def fake_registry():
        return FakeRegistry()

    monkeypatch.setattr(router, "_probe_ollama", fake_probe)
    monkeypatch.setattr(router, "_registry", fake_registry)
    monkeypatch.setattr(
        "synapse.integrations.opencode_bridge.detect_models",
        lambda: [SimpleNamespace(
            model_id="opencode/test-free",
            display_name="Test Free",
        )],
    )
    monkeypatch.setattr(
        "synapse.integrations.opencode_bridge.is_opencode_quota_exhausted",
        lambda: False,
    )

    await router.refresh_providers()

    descriptor = router.catalog.get("opencode/test-free")
    assert descriptor is not None
    assert descriptor.provider == "opencode"
    assert router.is_provider_available("opencode") is True
    assert router.health_check()["providers"]["opencode"]["model_count"] == 1
