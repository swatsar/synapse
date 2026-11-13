"""The model catalog must say which entries can actually answer now."""
from __future__ import annotations

from synapse.llm.omnirouter import CostTier, ModelDescriptor, ModelTier, OmniRouter


def _descriptor(model_id: str, provider: str, *, local: bool = False) -> ModelDescriptor:
    return ModelDescriptor(
        id=model_id,
        provider=provider,
        display_name=model_id,
        tier=ModelTier.LOCAL if local else ModelTier.STANDARD,
        cost_tier=CostTier.FREE if local else CostTier.MEDIUM,
        context_window=8192,
        max_output=1024,
        strengths=(),
        capabilities={},
        is_local=local,
    )


def test_unconfigured_provider_models_are_marked_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    router = OmniRouter()
    catalog = {item["id"]: item for item in router.get_catalog()}

    assert catalog["claude-sonnet-5-5"]["available"] is False
    assert catalog["claude-sonnet-5-5"]["unavailable_reason"] == "provider_not_configured"
    assert catalog["gpt-4o"]["available"] is False


def test_ollama_models_require_a_pulled_model(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    router = OmniRouter()
    router._availability["ollama"] = True
    router._ollama_models = {"llama3.2"}
    catalog = {item["id"]: item for item in router.get_catalog()}

    assert catalog["llama3.2"]["available"] is True
    assert catalog["llama3.2"]["unavailable_reason"] is None
    assert catalog["codellama"]["available"] is False
    assert catalog["codellama"]["unavailable_reason"] == "model_not_installed"


def test_opencode_quota_is_reported_as_the_reason(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    router = OmniRouter()
    router.catalog["opencode/test-free"] = _descriptor("opencode/test-free", "opencode")
    router._availability["opencode"] = False
    router._quota_blocked = True
    catalog = {item["id"]: item for item in router.get_catalog()}

    assert catalog["opencode/test-free"]["available"] is False
    assert catalog["opencode/test-free"]["unavailable_reason"] == "quota_exhausted"


def test_opencode_without_quota_is_available(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    router = OmniRouter()
    router.catalog["opencode/test-free"] = _descriptor("opencode/test-free", "opencode")
    router._availability["opencode"] = True
    router._quota_blocked = False
    catalog = {item["id"]: item for item in router.get_catalog()}

    assert catalog["opencode/test-free"]["available"] is True
