from __future__ import annotations

from fastapi.testclient import TestClient

from synapse.api.app import app


def test_growth_status_record_paths_and_consolidate(monkeypatch, tmp_path):
    """The growth network must be observable and writable over HTTP."""
    from synapse.growth import network as growth_module

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    # The process-wide cache keyed by workspace must not leak a previous
    # database into this temporary workspace.
    growth_module._default_networks.pop(str(tmp_path.resolve()), None)

    with TestClient(app) as client:
        status = client.get("/api/v1/growth/status")
        assert status.status_code == 200
        assert status.json()["status"] == "empty"
        # Self-development must be visible, including whether a promoted
        # adapter is applied to real inference.
        assert "self_development" in status.json()
        assert status.json()["self_development"]["protocol_version"] == "1.0"

        recorded = client.post(
            "/api/v1/growth/record",
            json={
                "task": "write python code",
                "skill": "code_generator",
                "provider": "opencode",
                "model": "opencode/test-free",
                "success": True,
            },
        )
        assert recorded.status_code == 200
        assert recorded.json()["success"] is True

        status = client.get("/api/v1/growth/status")
        payload = status.json()
        assert payload["events"] == 1
        assert payload["nodes_by_kind"]["skill"] == 1
        assert payload["nodes_by_kind"]["provider"] == 1

        paths = client.get("/api/v1/growth/paths?limit=10")
        assert paths.status_code == 200
        relations = {item["relation"] for item in paths.json()["paths"]}
        assert {"activates", "runs_on", "answered_by", "serves"} <= relations

        suggest = client.get(
            "/api/v1/growth/suggest",
            params={"task": "write python code"},
        )
        assert suggest.status_code == 200
        suggestions = suggest.json()["suggestions"]
        assert suggestions and suggestions[0]["skill"] == "code_generator"

        consolidated = client.post("/api/v1/growth/consolidate")
        assert consolidated.status_code == 200
        assert consolidated.json()["consolidated"] is True
        assert consolidated.json()["summary"]["pass"] == 1

        after = client.get("/api/v1/growth/status").json()
        assert after["consolidation_passes"] == 1
        assert after["status"] == "growing"

        autonomy = client.get("/api/v1/growth/autonomy")
        assert autonomy.status_code == 200
        autonomy_payload = autonomy.json()
        assert autonomy_payload["auto_train_enabled"] is False
        assert autonomy_payload["status"] in {"idle", "running"}

        manual = client.post("/api/v1/growth/autonomy/tick")
        assert manual.status_code == 200
        assert manual.json()["cycle"]["tick"] >= 1
        assert manual.json()["cycle"]["training"] is None

    growth_module._default_networks.pop(str(tmp_path.resolve()), None)


def test_growth_autonomy_train_is_gated(monkeypatch, tmp_path):
    """The manual training trigger must not bypass the safety gates."""
    from synapse.growth import autonomy as autonomy_module
    from synapse.growth import network as growth_module

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    growth_module._default_networks.pop(str(tmp_path.resolve()), None)
    autonomy_module._loops.pop(str(tmp_path.resolve()), None)

    with TestClient(app) as client:
        response = client.post("/api/v1/growth/autonomy/train")
        assert response.status_code == 200
        payload = response.json()
        # The test suite runs with automatic training disabled, so the endpoint
        # must report the blocker rather than claim a training run happened.
        assert payload["training"]["status"] == "skipped"
        assert payload["training"]["reason"] == "auto_train_disabled"
        assert "auto_train_disabled" in payload["readiness"]["blockers"]
        assert payload["status"]["auto_train_enabled"] is False

    growth_module._default_networks.pop(str(tmp_path.resolve()), None)
    autonomy_module._loops.pop(str(tmp_path.resolve()), None)


def test_growth_self_study_api_adds_verified_facts_once(monkeypatch, tmp_path):
    """The manual study endpoint must create verified records and no duplicates."""
    from synapse.experience import ExperienceStore
    from synapse.growth import autonomy as autonomy_module
    from synapse.growth import network as growth_module

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    growth_module._default_networks.pop(str(tmp_path.resolve()), None)
    (tmp_path / "README.md").write_text(
        "# Synapse\n\n"
        "## Назначение\n\n"
        "**Synapse** — автономный агент для программирования, который выполняет "
        "задачи в локальном workspace и проверяет результат независимыми "
        "критериями приёмки.\n\n"
        "## Сеть роста\n\n"
        "Успешный маршрут усиливает связь задача → навык, а ошибка тормозит её. "
        "После нескольких успехов путь миелинизируется и становится быстрым "
        "автоматическим маршрутом.\n",
        encoding="utf-8",
    )

    try:
        with TestClient(app) as client:
            first = client.post("/api/v1/growth/autonomy/self-study")
            assert first.status_code == 200
            payload = first.json()
            assert payload["created"] >= 1
            assert payload["protocol_version"] == "1.0"
            assert payload["status"]["last_self_study_result"]["created"] == payload["created"]

            store = ExperienceStore(tmp_path / ".synapse" / "experience.sqlite3")
            try:
                records = store.list_records(verified_only=True)
            finally:
                store.close()
            assert len(records) == payload["created"]
            assert all(
                record.provider == "documentation"
                and record.execution_success
                and record.verifier_passed
                for record in records
            )

            second = client.post("/api/v1/growth/autonomy/self-study")
            assert second.status_code == 200
            assert second.json()["created"] == 0
            assert second.json()["status"]["last_self_study_result"]["created"] == 0
            assert "не найдено" in second.json()["content"]
    finally:
        growth_module._default_networks.pop(str(tmp_path.resolve()), None)
        autonomy_module._loops.pop(str(tmp_path.resolve()), None)


def test_growth_teachers_lists_opencode_models(monkeypatch, tmp_path):
    """OpenCode models must stay selectable as teachers in the app."""
    from types import SimpleNamespace

    from synapse.integrations import opencode_bridge

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(
        opencode_bridge, "quota_status",
        lambda: {"exhausted": False, "retry_after_seconds": 0},
    )
    monkeypatch.setattr(
        opencode_bridge, "detect_models",
        lambda: [SimpleNamespace(
            model_id="opencode/test-free", display_name="Test Free",
        )],
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/growth/teachers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["opencode"]["available_models"] == 1
    assert payload["opencode"]["model_count"] == 1
    assert payload["opencode"]["usable"] is True
    teachers = payload["teachers"]
    assert any(
        teacher["id"] == "opencode/test-free"
        and teacher["kind"] == "opencode"
        and teacher["available"] is True
        for teacher in teachers
    )
    assert teachers[0]["id"] == "auto"


def test_growth_teachers_keeps_opencode_listed_when_quota_is_exhausted(
    monkeypatch, tmp_path,
):
    from types import SimpleNamespace

    from synapse.integrations import opencode_bridge

    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(
        opencode_bridge, "quota_status",
        lambda: {"exhausted": True, "retry_after_seconds": 900},
    )
    monkeypatch.setattr(
        opencode_bridge, "detect_models",
        lambda: [SimpleNamespace(
            model_id="opencode/test-free", display_name="Test Free",
        )],
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/growth/teachers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["opencode"]["available_models"] == 0
    assert payload["opencode"]["model_count"] == 1
    assert payload["opencode"]["usable"] is False
    assert payload["opencode"]["quota"]["exhausted"] is True
    # The catalog stays visible during cooldown; it is only marked unavailable.
    opencode_teachers = [
        teacher for teacher in payload["teachers"] if teacher["kind"] == "opencode"
    ]
    assert [teacher["id"] for teacher in opencode_teachers] == ["opencode/test-free"]
    assert opencode_teachers[0]["available"] is False


def test_growth_record_requires_task_and_skill(monkeypatch, tmp_path):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    from synapse.growth import network as growth_module

    growth_module._default_networks.pop(str(tmp_path.resolve()), None)
    with TestClient(app) as client:
        response = client.post("/api/v1/growth/record", json={"task": "only a task"})
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "task and skill" in response.json()["error"]
    growth_module._default_networks.pop(str(tmp_path.resolve()), None)
