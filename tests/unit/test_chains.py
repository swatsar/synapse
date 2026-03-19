"""Unit tests for Chain/Workflow system. Phase 3 — LangChain patterns.

TDD per TDD_INSTRUCTION_v1_2_FINAL.md + LANGCHAIN_INTEGRATION.md §2.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase3
@pytest.mark.unit
class TestChainInput:
    def test_chain_input_defaults(self):
        from synapse.llm.chains import ChainInput
        ci = ChainInput(data={"key": "value"})
        assert ci.trace_id
        assert ci.session_id
        assert ci.protocol_version == PROTOCOL_VERSION

    def test_chain_output_to_dict(self):
        from synapse.llm.chains import ChainOutput
        co = ChainOutput(result="hello", trace_id="t1", session_id="s1")
        d = co.to_dict()
        assert d["result"] == "hello"
        assert d["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase3
@pytest.mark.unit
class TestLLMChain:
    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value={"content": "Hello from LLM", "model": "test"})
        return llm

    @pytest.fixture
    def chain(self, mock_llm):
        from synapse.llm.chains import LLMChain
        return LLMChain(name="test_chain", llm_provider=mock_llm, prompt_template="Answer: {question}")

    @pytest.mark.asyncio
    async def test_llm_chain_execute_success(self, chain):
        from synapse.llm.chains import ChainInput
        inp = ChainInput(data={"question": "What is 2+2?"})
        out = await chain.execute(inp)
        assert out.success is True
        assert out.result == "Hello from LLM"
        assert out.protocol_version == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_llm_chain_propagates_trace_id(self, chain):
        from synapse.llm.chains import ChainInput
        inp = ChainInput(data={"question": "test"}, trace_id="trace-abc")
        out = await chain.execute(inp)
        assert out.trace_id == "trace-abc"

    @pytest.mark.asyncio
    async def test_llm_chain_handles_error(self, mock_llm):
        from synapse.llm.chains import LLMChain, ChainInput
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        chain = LLMChain(name="err_chain", llm_provider=mock_llm)
        inp = ChainInput(data={})
        out = await chain.execute(inp)
        assert out.success is False
        assert out.error


@pytest.mark.phase3
@pytest.mark.unit
class TestSequentialChain:
    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value={"content": "step result"})
        return llm

    @pytest.mark.asyncio
    async def test_sequential_executes_all_steps(self, mock_llm):
        from synapse.llm.chains import LLMChain, SequentialChain, ChainInput
        c1 = LLMChain(name="step1", llm_provider=mock_llm)
        c2 = LLMChain(name="step2", llm_provider=mock_llm)
        seq = SequentialChain(chains=[c1, c2])
        inp = ChainInput(data={"input": "start"})
        out = await seq.execute(inp)
        assert out.success is True
        assert len(out.intermediate_steps) == 2

    @pytest.mark.asyncio
    async def test_sequential_stops_on_error(self, mock_llm):
        from synapse.llm.chains import LLMChain, SequentialChain, ChainInput
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("fail"))
        c1 = LLMChain(name="step1", llm_provider=mock_llm)
        c2 = LLMChain(name="step2", llm_provider=mock_llm)
        seq = SequentialChain(chains=[c1, c2])
        out = await seq.execute(ChainInput(data={}))
        assert out.success is False


@pytest.mark.phase3
@pytest.mark.unit
class TestParallelChain:
    @pytest.mark.asyncio
    async def test_parallel_runs_all_chains(self):
        from synapse.llm.chains import LLMChain, ParallelChain, ChainInput
        llm1 = AsyncMock()
        llm1.generate = AsyncMock(return_value={"content": "r1"})
        llm2 = AsyncMock()
        llm2.generate = AsyncMock(return_value={"content": "r2"})
        chains = [LLMChain(name="c1", llm_provider=llm1), LLMChain(name="c2", llm_provider=llm2)]
        p = ParallelChain(chains=chains)
        out = await p.execute(ChainInput(data={}))
        assert out.success is True
        assert len(out.result["results"]) == 2


@pytest.mark.phase3
@pytest.mark.unit
class TestRouterChain:
    @pytest.mark.asyncio
    async def test_routes_to_correct_chain(self):
        from synapse.llm.chains import LLMChain, RouterChain, ChainInput
        llm_a = AsyncMock()
        llm_a.generate = AsyncMock(return_value={"content": "route_a"})
        llm_b = AsyncMock()
        llm_b.generate = AsyncMock(return_value={"content": "route_b"})
        router = RouterChain(routes={
            "coding": LLMChain(name="code_chain", llm_provider=llm_a),
            "chat": LLMChain(name="chat_chain", llm_provider=llm_b),
        })
        out = await router.execute(ChainInput(data={"route": "coding"}))
        assert out.result == "route_a"

    @pytest.mark.asyncio
    async def test_missing_route_returns_error(self):
        from synapse.llm.chains import RouterChain, ChainInput
        router = RouterChain(routes={})
        out = await router.execute(ChainInput(data={"route": "unknown"}))
        assert out.success is False
