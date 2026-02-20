"""
Performance benchmark tests for Synapse.
Phase 5: Reliability & Observability

Target Metrics:
- Skill Execution Latency: <100ms
- LLM Request Latency: <2000ms
- Memory Recall Latency: <50ms
- Capability Check Latency: <10ms
- Checkpoint Creation Time: <100ms
- Audit Logging Overhead: <5ms
"""
import pytest
import time
import statistics
from typing import List
from unittest.mock import AsyncMock, MagicMock


# ============================================================================
# TestSkillExecutionLatency
# ============================================================================

@pytest.mark.phase5
@pytest.mark.benchmark
class TestSkillExecutionLatency:
    """Benchmark tests for skill execution latency."""
    
    @pytest.mark.asyncio
    async def test_builtin_skill_latency(self, test_context, tmp_path):
        """Benchmark: Built-in skill execution latency <100ms."""
        from synapse.skills.builtins.read_file import ReadFileSkill
        
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content for benchmark")
        
        skill = ReadFileSkill()
        latencies: List[float] = []
        
        # 100 iterations for statistical significance
        for _ in range(100):
            start = time.perf_counter()
            await skill.execute(
                test_context,
                path=str(test_file)
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)  # Convert to ms
        
        # Statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=100)[94]
        max_latency = max(latencies)
        
        # Assert targets
        assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms > 100ms"
        assert p95_latency < 150, f"P95 latency {p95_latency:.2f}ms > 150ms"
        
        print(f"\nBuilt-in Skill Execution Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_skill_latency_under_load(self, test_context, tmp_path):
        """Benchmark: Skill latency under concurrent load."""
        import asyncio
        from synapse.skills.builtins.read_file import ReadFileSkill
        
        # Create test file
        test_file = tmp_path / "load_test.txt"
        test_file.write_text("load test content")
        
        skill = ReadFileSkill()
        
        async def execute_skill():
            start = time.perf_counter()
            await skill.execute(test_context, path=str(test_file))
            return (time.perf_counter() - start) * 1000
        
        # Run 50 concurrent executions
        tasks = [execute_skill() for _ in range(50)]
        latencies = await asyncio.gather(*tasks)
        
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        
        # Under load, allow higher latency
        assert avg_latency < 200, f"Average latency under load {avg_latency:.2f}ms > 200ms"
        
        print(f"\nSkill Latency Under Load (50 concurrent):")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")


# ============================================================================
# TestMemoryOperations
# ============================================================================

@pytest.mark.phase5
@pytest.mark.benchmark
class TestMemoryOperations:
    """Benchmark tests for memory operations."""
    
    @pytest.mark.asyncio
    async def test_memory_recall_latency(self, memory_store):
        """Benchmark: Memory recall latency <50ms."""
        # Store some test data first (using correct API: episode, data)
        for i in range(100):
            await memory_store.add_episodic(
                episode=f"test_memory_{i}",
                data={"content": f"test memory {i}", "index": i}
            )
        
        latencies: List[float] = []
        
        # 100 recall operations
        for i in range(100):
            start = time.perf_counter()
            results = await memory_store.search(query=f"test_memory_{i % 50}", limit=10)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=100)[94]
        
        assert avg_latency < 50, f"Average recall latency {avg_latency:.2f}ms > 50ms"
        
        print(f"\nMemory Recall Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_memory_store_latency(self, memory_store):
        """Benchmark: Memory store latency <30ms."""
        latencies: List[float] = []
        
        # 100 store operations
        for i in range(100):
            start = time.perf_counter()
            await memory_store.add_episodic(
                episode=f"benchmark_memory_{i}",
                data={"content": f"benchmark memory {i}", "benchmark": True}
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        
        assert avg_latency < 30, f"Average store latency {avg_latency:.2f}ms > 30ms"
        
        print(f"\nMemory Store Latency:")
        print(f"  Average: {avg_latency:.2f}ms")


# ============================================================================
# TestSecurityOverhead
# ============================================================================

@pytest.mark.phase5
@pytest.mark.benchmark
class TestSecurityOverhead:
    """Benchmark tests for security operations overhead."""
    
    @pytest.mark.asyncio
    async def test_capability_check_latency(self, capability_manager, test_context):
        """Benchmark: Capability check latency <10ms."""
        # Grant some capabilities
        capability_manager.grant_capability("fs:read:/workspace/**")
        capability_manager.grant_capability("fs:write:/workspace/**")
        
        latencies: List[float] = []
        
        # 1000 capability checks
        for _ in range(1000):
            start = time.perf_counter()
            result = await capability_manager.check_capability(
                ["fs:read:/workspace/test.txt"]
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=100)[94]
        
        assert avg_latency < 10, f"Average capability check latency {avg_latency:.2f}ms > 10ms"
        
        print(f"\nCapability Check Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_checkpoint_creation_time(self, checkpoint_manager):
        """Benchmark: Checkpoint creation time <100ms."""
        latencies: List[float] = []
        
        # 100 checkpoint creations
        for i in range(100):
            state = {"data": f"benchmark_state_{i}", "nested": {"key": "value"}}
            
            start = time.perf_counter()
            checkpoint = checkpoint_manager.create_checkpoint(
                agent_id=f"benchmark_agent_{i}",
                session_id="benchmark_session",
                state=state
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=100)[94]
        
        assert avg_latency < 100, f"Average checkpoint creation {avg_latency:.2f}ms > 100ms"
        
        print(f"\nCheckpoint Creation Time:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_audit_logging_overhead(self):
        """Benchmark: Audit logging overhead <5ms."""
        from synapse.core.audit import AuditLogger
        
        audit = AuditLogger()
        latencies: List[float] = []
        
        # 1000 audit log operations
        for i in range(1000):
            start = time.perf_counter()
            audit.record(f"benchmark_event_{i}", {"data": "benchmark"})
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        
        assert avg_latency < 5, f"Average audit logging overhead {avg_latency:.2f}ms > 5ms"
        
        print(f"\nAudit Logging Overhead:")
        print(f"  Average: {avg_latency:.2f}ms")


# ============================================================================
# TestTimeSyncPerformance
# ============================================================================

@pytest.mark.phase5
@pytest.mark.benchmark
class TestTimeSyncPerformance:
    """Benchmark tests for time synchronization."""
    
    @pytest.mark.asyncio
    async def test_timestamp_generation_latency(self):
        """Benchmark: Timestamp generation latency <1ms."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        latencies: List[float] = []
        
        # 10000 timestamp generations
        for _ in range(10000):
            start = time.perf_counter()
            ts = TimeSyncManager.now()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        
        assert avg_latency < 1, f"Average timestamp generation {avg_latency:.4f}ms > 1ms"
        
        print(f"\nTimestamp Generation Latency:")
        print(f"  Average: {avg_latency:.4f}ms")
    
    @pytest.mark.asyncio
    async def test_per_node_offset_lookup(self):
        """Benchmark: Per-node offset lookup latency <0.5ms."""
        from synapse.core.time_sync_manager import TimeSyncManager
        
        # Set up multiple node offsets
        for i in range(100):
            TimeSyncManager.set_offset(float(i), node_id=f"node_{i}")
        
        latencies: List[float] = []
        
        # 10000 lookups
        for i in range(10000):
            node_id = f"node_{i % 100}"
            
            start = time.perf_counter()
            ts = TimeSyncManager.now(node_id=node_id)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        
        assert avg_latency < 0.5, f"Average offset lookup {avg_latency:.4f}ms > 0.5ms"
        
        print(f"\nPer-Node Offset Lookup Latency:")
        print(f"  Average: {avg_latency:.4f}ms")


# ============================================================================
# TestConsensusPerformance
# ============================================================================

@pytest.mark.phase5
@pytest.mark.benchmark
class TestConsensusPerformance:
    """Benchmark tests for consensus operations."""
    
    @pytest.mark.asyncio
    async def test_consensus_propose_latency(self, consensus_engine):
        """Benchmark: Consensus propose latency <20ms."""
        # Grant capabilities
        consensus_engine._caps.grant_capability("consensus:propose")
        
        latencies: List[float] = []
        
        # 100 proposals
        for i in range(100):
            start = time.perf_counter()
            await consensus_engine.propose(
                node_id=f"node_{i % 10}",
                state={"value": i}
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        
        assert avg_latency < 20, f"Average consensus propose {avg_latency:.2f}ms > 20ms"
        
        print(f"\nConsensus Propose Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_consensus_decide_latency(self, consensus_engine):
        """Benchmark: Consensus decide latency <10ms."""
        # Grant capabilities
        consensus_engine._caps.grant_capability("consensus:propose")
        consensus_engine._caps.grant_capability("consensus:decide")
        
        # Propose from multiple nodes
        for i in range(10):
            await consensus_engine.propose(f"node_{i}", {"value": i})
        
        latencies: List[float] = []
        
        # 100 decide operations
        for _ in range(100):
            start = time.perf_counter()
            decision = await consensus_engine.decide()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)
        
        avg_latency = statistics.mean(latencies)
        
        assert avg_latency < 10, f"Average consensus decide {avg_latency:.2f}ms > 10ms"
        
        print(f"\nConsensus Decide Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
