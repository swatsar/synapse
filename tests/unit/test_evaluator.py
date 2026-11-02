"""Unit tests for LLM Evaluation Framework. Phase 5 — Observability.

TDD per LANGSMITH_SDK_INTEGRATION.md §3.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase5
@pytest.mark.unit
class TestEvalDataset:
    def test_create_dataset(self):
        from synapse.observability.evaluator import EvalDataset
        ds = EvalDataset(name="test_ds", version="1.0")
        assert ds.name == "test_ds"
        assert ds.protocol_version == PROTOCOL_VERSION

    def test_add_example(self):
        from synapse.observability.evaluator import EvalDataset
        ds = EvalDataset(name="ds")
        ex = ds.add({"query": "hello"}, expected="world")
        assert ex.input["query"] == "hello"
        assert ex.expected_output == "world"
        assert len(ds.examples) == 1

    def test_dataset_to_dict(self):
        from synapse.observability.evaluator import EvalDataset
        ds = EvalDataset(name="ds")
        d = ds.to_dict()
        assert d["name"] == "ds"
        assert d["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase5
@pytest.mark.unit
class TestBuiltinEvaluators:
    def test_exact_match_pass(self):
        from synapse.observability.evaluator import exact_match_evaluator
        assert exact_match_evaluator("hello", "hello") == 1.0

    def test_exact_match_fail(self):
        from synapse.observability.evaluator import exact_match_evaluator
        assert exact_match_evaluator("hello", "world") == 0.0

    def test_contains_evaluator(self):
        from synapse.observability.evaluator import contains_evaluator
        assert contains_evaluator("protocol", "the protocol_version field") == 1.0
        assert contains_evaluator("missing", "no relevant content") == 0.0

    def test_json_keys_evaluator(self):
        from synapse.observability.evaluator import json_keys_evaluator
        import json
        data = json.dumps({"success": True, "score": 0.9, "feedback": "good"})
        score = json_keys_evaluator(["success", "score", "feedback"], data)
        assert score == 1.0

    def test_json_keys_partial_match(self):
        from synapse.observability.evaluator import json_keys_evaluator
        import json
        data = json.dumps({"success": True})
        score = json_keys_evaluator(["success", "score", "feedback"], data)
        assert 0.0 < score < 1.0

    def test_protocol_version_evaluator(self):
        from synapse.observability.evaluator import protocol_version_evaluator
        assert protocol_version_evaluator("1.0", {"protocol_version": "1.0"}) == 1.0
        assert protocol_version_evaluator("1.0", {"protocol_version": "2.0"}) == 0.0


@pytest.mark.phase5
@pytest.mark.unit
class TestLLMEvaluator:
    @pytest.fixture
    def evaluator(self):
        from synapse.observability.evaluator import LLMEvaluator
        return LLMEvaluator()

    def test_create_dataset(self, evaluator):
        ds = evaluator.create_dataset("my_dataset", version="1.0")
        assert ds.name == "my_dataset"
        assert evaluator.get_dataset("my_dataset") is ds

    @pytest.mark.asyncio
    async def test_run_evaluation_pass(self, evaluator):
        from synapse.observability.evaluator import exact_match_evaluator
        ds = evaluator.create_dataset("test_run")
        ds.add({"x": "hello"}, expected="HELLO")

        async def upper_fn(x): return x.upper()
        result = await evaluator.run("test_run", upper_fn, scorer=exact_match_evaluator)
        assert result.total == 1
        assert result.passed == 1
        assert result.pass_rate == 1.0
        assert result.protocol_version == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_run_evaluation_fail(self, evaluator):
        from synapse.observability.evaluator import exact_match_evaluator
        ds = evaluator.create_dataset("test_fail")
        ds.add({"x": "hello"}, expected="wrong_answer")

        async def identity(x): return x
        result = await evaluator.run("test_fail", identity, scorer=exact_match_evaluator)
        assert result.failed == 1
        assert result.pass_rate == 0.0

    @pytest.mark.asyncio
    async def test_run_handles_function_error(self, evaluator):
        ds = evaluator.create_dataset("test_error")
        ds.add({"x": "val"}, expected="any")

        async def error_fn(x): raise RuntimeError("boom")
        result = await evaluator.run("test_error", error_fn)
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_llm_judge_returns_normalized_score(self, evaluator):
        score = await evaluator.llm_judge("some output", "is it helpful?")
        assert 0.0 <= score <= 1.0

    def test_results_summary(self, evaluator):
        summary = evaluator.get_results_summary()
        assert isinstance(summary, list)
