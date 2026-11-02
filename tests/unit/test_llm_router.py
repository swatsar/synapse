"""Unit tests for LLM Model Router. Phase 3 — Perception & Memory.

TDD: Tests define requirements first per TDD_INSTRUCTION_v1_2_FINAL.md
"""
import pytest
import pytest_asyncio

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase3
@pytest.mark.unit
class TestModelConfig:
    def test_model_config_defaults(self):
        from synapse.llm.model_router import ModelConfig, ModelPriority
        m = ModelConfig(name="openai", provider="openai", model="gpt-4o-mini")
        assert m.priority == ModelPriority.PRIMARY
        assert m.is_active is True
        assert m.timeout_seconds == 30
        assert m.protocol_version == PROTOCOL_VERSION

    def test_model_priority_ordering(self):
        from synapse.llm.model_router import ModelPriority
        assert ModelPriority.PRIMARY < ModelPriority.FALLBACK_1
        assert ModelPriority.FALLBACK_1 < ModelPriority.FALLBACK_2


@pytest.mark.phase3
@pytest.mark.unit
class TestLLMModelRouter:
    @pytest.fixture
    def models(self):
        from synapse.llm.model_router import ModelConfig, ModelPriority
        return [
            ModelConfig(name="gpt4", provider="openai", model="gpt-4o", priority=ModelPriority.PRIMARY),
            ModelConfig(name="gpt_mini", provider="openai", model="gpt-4o-mini", priority=ModelPriority.FALLBACK_1),
            ModelConfig(name="llama", provider="ollama", model="llama3", priority=ModelPriority.FALLBACK_2),
        ]

    @pytest.fixture
    def router(self, models):
        from synapse.llm.model_router import LLMModelRouter
        return LLMModelRouter(models=models)

    @pytest.mark.asyncio
    async def test_get_model_returns_primary(self, router):
        model = await router.get_model()
        assert model is not None
        assert model.name == "gpt4"

    @pytest.mark.asyncio
    async def test_failover_after_3_failures(self, router):
        await router.record_failure("gpt4", "timeout")
        await router.record_failure("gpt4", "timeout")
        await router.record_failure("gpt4", "timeout")
        model = await router.get_model()
        assert model is not None
        assert model.name != "gpt4"

    @pytest.mark.asyncio
    async def test_record_success_resets_failure_count(self, router):
        await router.record_failure("gpt4", "err")
        await router.record_failure("gpt4", "err")
        await router.record_success("gpt4", input_tokens=100, output_tokens=50)
        assert router._failure_counts["gpt4"] == 0

    @pytest.mark.asyncio
    async def test_cost_tracking(self, router):
        cost = await router.record_success("gpt4", input_tokens=1000, output_tokens=500)
        assert isinstance(cost, float)
        assert cost >= 0.0
        summary = router.get_cost_summary()
        assert summary["models"]["gpt4"]["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_health_check_returns_all_models(self, router):
        health = await router.health_check()
        assert "gpt4" in health
        assert "gpt_mini" in health
        assert "llama" in health

    def test_list_models(self, router):
        models = router.list_models()
        assert len(models) == 3
        assert all(m["protocol_version"] == PROTOCOL_VERSION for m in models)

    def test_reset_health(self, router):
        router._health["gpt4"] = False
        router.reset_health("gpt4")
        assert router._health["gpt4"] is True

    @pytest.mark.asyncio
    async def test_task_based_routing(self, models):
        from synapse.llm.model_router import ModelConfig, ModelPriority, LLMModelRouter
        models_with_tasks = [
            ModelConfig(name="coding_model", provider="openai", model="gpt-4o",
                       priority=ModelPriority.PRIMARY, task_types=["coding"]),
            ModelConfig(name="chat_model", provider="openai", model="gpt-3.5-turbo",
                       priority=ModelPriority.FALLBACK_1, task_types=["chat"]),
        ]
        router = LLMModelRouter(models=models_with_tasks)
        coding = await router.get_model(task_type="coding")
        chat = await router.get_model(task_type="chat")
        assert coding.name == "coding_model"
        assert chat.name == "chat_model"
