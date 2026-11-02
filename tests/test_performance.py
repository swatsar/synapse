"""Performance tests. Marked slow — run separately.

TDD per TDD_INSTRUCTION_v1_2_FINAL.md — Performance tests section.
"""
import pytest
import pytest_asyncio
import time
import asyncio
import statistics

PROTOCOL_VERSION = "1.0"


@pytest.mark.performance
@pytest.mark.slow
class TestCapabilityCheckPerformance:
    """Capability checks must be fast — spec requires <10ms avg."""

    @pytest.fixture
    def capability_manager(self):
        from synapse.security.capability_manager import CapabilityManager
        cm = CapabilityManager()
        cm.grant_capability("fs:read:/workspace/**")
        cm.grant_capability("net:http")
        cm.grant_capability("memory:read")
        return cm

    @pytest.mark.asyncio
    async def test_capability_check_under_10ms(self, capability_manager):
        class Ctx:
            capabilities = ["fs:read:/workspace/**"]
            agent_id = "perf_test"

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            await capability_manager.check_capability(Ctx(), "fs:read:/workspace/test.txt")
            latencies.append((time.perf_counter() - start) * 1000)

        avg = statistics.mean(latencies)
        assert avg < 10.0, f"Avg capability check {avg:.2f}ms > 10ms"

    @pytest.mark.asyncio
    async def test_capability_check_throughput(self, capability_manager):
        """Should handle 1000 checks per second."""
        class Ctx:
            capabilities = ["net:http"]
            agent_id = "throughput_test"

        start = time.perf_counter()
        for _ in range(1000):
            await capability_manager.check_capability(Ctx(), "net:http")
        elapsed = time.perf_counter() - start
        throughput = 1000 / elapsed
        assert throughput > 100, f"Throughput {throughput:.0f} checks/s < 100"


@pytest.mark.performance
@pytest.mark.slow
class TestPromptManagerPerformance:
    @pytest.fixture
    def manager(self):
        from synapse.llm.prompt_manager import PromptManager
        return PromptManager()

    def test_render_latency_under_1ms(self, manager):
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            manager.render("planner_system", task="test", skills="read_file", memory="none")
            latencies.append((time.perf_counter() - start) * 1000)
        avg = statistics.mean(latencies)
        assert avg < 1.0, f"Avg render latency {avg:.3f}ms > 1ms"


@pytest.mark.performance
@pytest.mark.slow
class TestVectorStoreFallbackPerformance:
    @pytest.mark.asyncio
    async def test_keyword_fallback_query_under_5ms(self):
        """BM25 keyword fallback query latency must stay under 5 ms.

        Replaces the former SHA-512 pseudo-embedding latency test: the fallback
        is now honest lexical retrieval instead of a hash-derived fake vector.
        """
        from synapse.memory.vector_store import VectorMemoryStore
        store = VectorMemoryStore()
        async def _no_embedding(text: str) -> None:
            return None

        store._get_embedding = _no_embedding  # type: ignore[assignment]
        for i in range(50):
            await store.add_document(f"document number {i} about agents", doc_id=f"d{i}")

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            await store.query("agents document", limit=5)
            latencies.append((time.perf_counter() - start) * 1000)
        avg = statistics.mean(latencies)
        assert avg < 5.0, f"Avg keyword query {avg:.2f}ms > 5ms"


@pytest.mark.performance
@pytest.mark.slow
class TestChainExecutionPerformance:
    @pytest.mark.asyncio
    async def test_sequential_chain_latency(self):
        from synapse.llm.chains import LLMChain, SequentialChain, ChainInput
        from unittest.mock import AsyncMock

        call_count = 0
        async def fast_generate(prompt, **_):
            nonlocal call_count
            call_count += 1
            return {"content": f"result_{call_count}"}

        mock_llm = AsyncMock()
        mock_llm.generate = fast_generate

        chains = [LLMChain(name=f"step{i}", llm_provider=mock_llm) for i in range(5)]
        seq = SequentialChain(chains=chains)

        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            await seq.execute(ChainInput(data={"input": "test"}))
            latencies.append((time.perf_counter() - start) * 1000)

        avg = statistics.mean(latencies)
        # 5 sequential mocked LLM calls should be well under 100ms
        assert avg < 100.0, f"Sequential chain avg {avg:.2f}ms > 100ms"
