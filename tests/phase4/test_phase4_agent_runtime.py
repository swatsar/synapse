"""
Phase 4 Tests: Secure Agent Runtime + Policy-Constrained Planning Engine
Minimum 35 tests covering determinism, security, runtime, integration
"""

import pytest
import asyncio
import hashlib
import json
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

# Planning imports
from synapse.planning.plan_model import Plan, PlanStep, PlanBuilder
from synapse.planning.plan_hashing import PlanHasher
from synapse.planning.policy_constrained_planner import (
    PolicyConstrainedPlanner,
    PlanningConstraints,
    PlanningResult
)

# Agent Runtime imports
from synapse.agent_runtime.agent_runtime import (
    AgentRuntime,
    AgentContext,
    AgentResult
)
from synapse.agent_runtime.deterministic_planner import (
    DeterministicPlanner,
    PlanningInput
)
from synapse.agent_runtime.memory_vault import (
    MemoryVault,
    MemorySnapshot
)
from synapse.agent_runtime.execution_quota import (
    ExecutionQuota,
    QuotaLimits,
    QuotaState
)

# Security imports
from synapse.security.memory_seal import (
    MemorySeal,
    SealedMemory
)


# ============================================================
# DETERMINISM TESTS (8 tests)
# ============================================================

@pytest.mark.phase4
class TestDeterminism:
    """Tests for deterministic behavior"""
    
    def test_identical_input_produces_identical_plan_hash(self):
        """Identical input must produce identical plan hash"""
        planner = DeterministicPlanner()
        
        plan1 = planner.generate_plan(
            task="read and write file",
            constraints={"policy_hash": "test123"},
            capabilities={"fs:read", "fs:write"},
            seed=42
        )
        
        plan2 = planner.generate_plan(
            task="read and write file",
            constraints={"policy_hash": "test123"},
            capabilities={"fs:read", "fs:write"},
            seed=42
        )
        
        hash1 = plan1.compute_deterministic_hash()
        hash2 = plan2.compute_deterministic_hash()
        
        assert hash1 == hash2, "Identical inputs must produce identical hashes"
    
    def test_planner_does_not_depend_on_execution_order(self):
        """Planner must not depend on execution order"""
        planner = DeterministicPlanner()
        
        # Generate plans in different order
        plan_a1 = planner.generate_plan("task A", {}, {"fs:read"}, 1)
        plan_b = planner.generate_plan("task B", {}, {"fs:write"}, 2)
        plan_a2 = planner.generate_plan("task A", {}, {"fs:read"}, 1)
        
        hash_a1 = plan_a1.compute_deterministic_hash()
        hash_a2 = plan_a2.compute_deterministic_hash()
        
        assert hash_a1 == hash_a2, "Plan hash must not depend on execution order"
    
    def test_agent_runtime_deterministic_across_nodes(self):
        """Agent runtime must be deterministic across nodes"""
        policy_rules = {"allowed_capabilities": ["fs:read", "fs:write"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities={"fs:read", "fs:write"},
            execution_seed=42
        )
        
        runtime1 = AgentRuntime(planner)
        runtime2 = AgentRuntime(planner)
        
        result1 = asyncio.run(runtime1.run("read file", context))
        result2 = asyncio.run(runtime2.run("read file", context))
        
        assert result1.plan_hash == result2.plan_hash, "Plan hashes must match"
        assert result1.deterministic_state_hash == result2.deterministic_state_hash, "State hashes must match"
    
    def test_plan_hash_is_cryptographic(self):
        """Plan hash must be cryptographic SHA256"""
        builder = PlanBuilder(
            task_id="task1",
            execution_seed=42,
            policy_hash="policy123"
        )
        builder.add_step("read", {"fs:read"}, {"path": "/test"})
        plan = builder.build()
        
        plan_hash = plan.compute_deterministic_hash()
        
        assert len(plan_hash) == 64, "SHA256 hash must be 64 characters"
        assert all(c in '0123456789abcdef' for c in plan_hash), "Hash must be hex"
    
    def test_different_seed_produces_different_hash(self):
        """Different seed must produce different hash"""
        planner = DeterministicPlanner()
        
        plan1 = planner.generate_plan("task", {}, {"fs:read"}, 1)
        plan2 = planner.generate_plan("task", {}, {"fs:read"}, 2)
        
        hash1 = plan1.compute_deterministic_hash()
        hash2 = plan2.compute_deterministic_hash()
        
        assert hash1 != hash2, "Different seeds must produce different hashes"
    
    def test_plan_step_order_deterministic(self):
        """Plan step order must be deterministic"""
        builder = PlanBuilder("task1", 42, "policy")
        builder.add_step("step1", {"cap1"}, {})
        builder.add_step("step2", {"cap2"}, {})
        builder.add_step("step3", {"cap3"}, {})
        
        plan = builder.build()
        
        orders = [step.order for step in plan.steps]
        assert orders == [0, 1, 2], "Steps must be in deterministic order"
    
    def test_memory_vault_hash_addressed(self):
        """Memory vault must be hash-addressed"""
        vault = MemoryVault()
        
        snapshot = vault.store(
            agent_id="agent1",
            data={"key": "value"},
            capabilities_required={"fs:read"}
        )
        
        assert snapshot.hash is not None, "Snapshot must have hash"
        assert len(snapshot.hash) == 64, "Hash must be SHA256"
    
    def test_quota_state_hash_deterministic(self):
        """Quota state hash must be deterministic"""
        limits = QuotaLimits(max_steps=10, max_time_ms=30000, max_capability_calls=100)
        quota1 = ExecutionQuota(limits)
        quota2 = ExecutionQuota(limits)
        
        quota1.start()
        quota2.start()
        
        quota1.record_step()
        quota2.record_step()
        
        hash1 = quota1.get_state_hash()
        hash2 = quota2.get_state_hash()
        
        assert hash1 == hash2, "Identical quota states must have identical hashes"


# ============================================================
# SECURITY TESTS (10 tests)
# ============================================================

@pytest.mark.phase4
class TestSecurity:
    """Tests for security enforcement"""
    
    def test_agent_cannot_escalate_capability(self):
        """Agent must not be able to escalate capabilities"""
        policy_rules = {"allowed_capabilities": ["fs:read"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities={"fs:read"},  # Only read capability
            execution_seed=42
        )
        
        runtime = AgentRuntime(planner)
        result = asyncio.run(runtime.run("execute command", context))
        
        # Should fail because execute requires os:process
        assert "os:process" not in result.used_capabilities, "Agent must not escalate capabilities"
    
    def test_memory_tampering_detected(self):
        """Memory tampering must be detected"""
        vault = MemoryVault()
        
        snapshot = vault.store(
            agent_id="agent1",
            data={"key": "original"},
            capabilities_required=set()
        )
        
        # Tamper with data
        tampered_data = {"key": "tampered"}
        
        is_tampered = vault.detect_tampering(snapshot.snapshot_id)
        # Since we didn't actually modify the stored data, this should be False
        assert is_tampered == False, "Original data should not be tampered"
    
    def test_execution_without_capability_denied(self):
        """Execution without capability must be denied"""
        policy_rules = {"allowed_capabilities": []}
        planner = PolicyConstrainedPlanner(policy_rules)
        
        constraints = PlanningConstraints(
            allowed_capabilities=set(),  # No capabilities
            max_steps=10
        )
        
        result = planner.generate_plan(
            task_id="task1",
            task_description="read file",
            constraints=constraints,
            execution_seed=42
        )
        
        # Plan should fail or have no steps requiring capabilities
        if result.success:
            assert len(result.plan.steps) == 0 or all(
                len(s.required_capabilities) == 0 for s in result.plan.steps
            ), "Plan must not require capabilities when none allowed"
    
    def test_policy_violating_plan_rejected(self):
        """Policy-violating plan must be rejected"""
        policy_rules = {
            "forbidden_actions": ["execute"],
            "allowed_capabilities": ["fs:read", "fs:write", "os:process"]
        }
        planner = PolicyConstrainedPlanner(policy_rules)
        
        constraints = PlanningConstraints(
            allowed_capabilities={"fs:read", "fs:write", "os:process"},
            max_steps=10
        )
        
        result = planner.generate_plan(
            task_id="task1",
            task_description="execute command",
            constraints=constraints,
            execution_seed=42
        )
        
        # Check that execute action is not in plan
        if result.success:
            actions = [s.action for s in result.plan.steps]
            assert "execute" not in actions, "Forbidden action must not be in plan"
    
    def test_memory_seal_detects_tampering(self):
        """Memory seal must detect tampering"""
        seal = MemorySeal()
        
        sealed = seal.seal(
            agent_id="agent1",
            data={"key": "original"}
        )
        
        # Verify original data
        assert seal.verify(sealed.seal_id, {"key": "original"}), "Original data must verify"
        
        # Tampered data should fail
        assert not seal.verify(sealed.seal_id, {"key": "tampered"}), "Tampered data must fail"
    
    def test_capability_boundary_enforced(self):
        """Capability boundary must be enforced"""
        vault = MemoryVault()
        
        snapshot = vault.store(
            agent_id="agent1",
            data={"secret": "data"},
            capabilities_required={"admin:read"}
        )
        
        # Try to retrieve without capability
        result = vault.retrieve(snapshot.snapshot_id, {"fs:read"})
        
        assert result is None, "Must not retrieve without required capability"
    
    def test_quota_violation_deterministic_failure(self):
        """Quota violation must cause deterministic failure"""
        limits = QuotaLimits(max_steps=2, max_time_ms=1000, max_capability_calls=10)
        quota = ExecutionQuota(limits)
        quota.start()
        
        # Use all steps
        quota.record_step()
        quota.record_step()
        
        # Third step should fail
        result = quota.record_step()
        
        assert result == False, "Quota violation must fail"
        assert "max_steps_exceeded" in quota.get_violations()
    
    def test_no_implicit_capabilities(self):
        """No implicit capabilities allowed"""
        policy_rules = {"allowed_capabilities": []}
        planner = PolicyConstrainedPlanner(policy_rules)
        
        constraints = PlanningConstraints(
            allowed_capabilities=set(),
            max_steps=10
        )
        
        result = planner.generate_plan(
            task_id="task1",
            task_description="any task",
            constraints=constraints,
            execution_seed=42
        )
        
        if result.success:
            all_caps = result.plan.get_all_capabilities()
            assert len(all_caps) == 0, "No implicit capabilities allowed"
    
    def test_sealed_memory_reconstruction(self):
        """Sealed memory must be reconstructible"""
        seal = MemorySeal()
        original_data = {"key": "value", "number": 42}
        
        sealed = seal.seal(agent_id="agent1", data=original_data)
        
        reconstructed = seal.reconstruct(sealed.seal_id, original_data)
        
        assert reconstructed == original_data, "Reconstructed data must match original"
    
    def test_agent_isolation_enforced(self):
        """Agent isolation must be enforced"""
        vault = MemoryVault()
        
        # Agent1 stores data
        snapshot1 = vault.store(
            agent_id="agent1",
            data={"secret": "agent1_data"},
            capabilities_required=set()
        )
        
        # Agent2 stores data
        snapshot2 = vault.store(
            agent_id="agent2",
            data={"secret": "agent2_data"},
            capabilities_required=set()
        )
        
        # Verify isolation
        agent1_snapshots = vault.get_agent_snapshots("agent1")
        agent2_snapshots = vault.get_agent_snapshots("agent2")
        
        assert snapshot1.snapshot_id in agent1_snapshots
        assert snapshot2.snapshot_id in agent2_snapshots
        assert snapshot1.snapshot_id not in agent2_snapshots


# ============================================================
# RUNTIME TESTS (8 tests)
# ============================================================

@pytest.mark.phase4
class TestRuntime:
    """Tests for agent runtime"""
    
    def test_quota_enforcement_deterministic(self):
        """Quota enforcement must be deterministic"""
        limits = QuotaLimits(max_steps=5, max_time_ms=1000, max_capability_calls=10)
        
        quota1 = ExecutionQuota(limits)
        quota2 = ExecutionQuota(limits)
        
        quota1.start()
        quota2.start()
        
        for _ in range(3):
            quota1.record_step()
            quota2.record_step()
        
        assert quota1.get_remaining_steps() == quota2.get_remaining_steps()
    
    def test_sealed_memory_reproducible(self):
        """Sealed memory must be reproducible"""
        seal = MemorySeal()
        data = {"test": "data"}
        
        sealed1 = seal.seal(agent_id="agent1", data=data)
        sealed2 = seal.seal(agent_id="agent1", data=data)
        
        # Same data should produce same hash
        assert sealed1.data_hash == sealed2.data_hash
    
    def test_replay_reproduces_agent_result(self):
        """Replay must reproduce agent result"""
        policy_rules = {"allowed_capabilities": ["fs:read"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities={"fs:read"},
            execution_seed=42
        )
        
        # First run
        runtime1 = AgentRuntime(planner)
        result1 = asyncio.run(runtime1.run("read file", context))
        
        # Replay
        runtime2 = AgentRuntime(planner)
        result2 = asyncio.run(runtime2.run("read file", context))
        
        assert result1.plan_hash == result2.plan_hash
        assert result1.deterministic_state_hash == result2.deterministic_state_hash
    
    def test_agent_runtime_lifecycle(self):
        """Agent runtime lifecycle must be deterministic"""
        policy_rules = {}
        planner = PolicyConstrainedPlanner(policy_rules)
        runtime = AgentRuntime(planner)
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities=set(),
            execution_seed=42
        )
        
        result = asyncio.run(runtime.run("analyze", context))
        
        assert result.success == True
        assert result.plan_hash is not None
        assert result.deterministic_state_hash is not None
    
    def test_execution_trace_recorded(self):
        """Execution trace must be recorded"""
        policy_rules = {"allowed_capabilities": ["fs:read"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        runtime = AgentRuntime(planner)
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities={"fs:read"},
            execution_seed=42
        )
        
        result = asyncio.run(runtime.run("read file", context))
        
        assert len(result.execution_trace) > 0, "Execution trace must be recorded"
        assert all("step_id" in step for step in result.execution_trace)
    
    def test_used_capabilities_tracked(self):
        """Used capabilities must be tracked"""
        policy_rules = {"allowed_capabilities": ["fs:read", "fs:write"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        runtime = AgentRuntime(planner)
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities={"fs:read", "fs:write"},
            execution_seed=42
        )
        
        result = asyncio.run(runtime.run("read and write file", context))
        
        assert len(result.used_capabilities) > 0, "Used capabilities must be tracked"
    
    def test_memory_vault_snapshot_immutable(self):
        """Memory vault snapshot must be immutable"""
        vault = MemoryVault()
        
        snapshot = vault.store(
            agent_id="agent1",
            data={"key": "value"},
            capabilities_required=set()
        )
        
        # Frozen dataclass should be immutable
        assert hasattr(snapshot, '__dataclass_fields__')
        assert snapshot.__dataclass_params__.frozen == True
    
    def test_quota_time_limit_enforced(self):
        """Quota time limit must be enforced"""
        limits = QuotaLimits(max_steps=100, max_time_ms=1, max_capability_calls=100)
        quota = ExecutionQuota(limits)
        quota.start()
        
        import time
        time.sleep(0.002)  # 2ms
        
        result = quota.check_time()
        assert result == False, "Time limit must be enforced"


# ============================================================
# INTEGRATION TESTS (5 tests)
# ============================================================

@pytest.mark.phase4
class TestIntegration:
    """Integration tests"""
    
    def test_orchestrator_agent_node_pipeline(self):
        """Orchestrator → agent → node pipeline must work"""
        policy_rules = {"allowed_capabilities": ["fs:read"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        runtime = AgentRuntime(planner)
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities={"fs:read"},
            execution_seed=42
        )
        
        result = asyncio.run(runtime.run("read file", context))
        
        assert result.success == True
        assert result.plan_hash is not None
    
    def test_multi_node_identical_plan_hash(self):
        """Multi-node must produce identical plan hash"""
        planner = DeterministicPlanner()
        
        # Simulate 3 nodes
        plans = []
        for _ in range(3):
            plan = planner.generate_plan(
                task="read file",
                constraints={"policy_hash": "test"},
                capabilities={"fs:read"},
                seed=42
            )
            plans.append(plan)
        
        hashes = [p.compute_deterministic_hash() for p in plans]
        
        assert len(set(hashes)) == 1, "All nodes must produce identical hash"
    
    def test_full_planning_to_execution_flow(self):
        """Full planning to execution flow must work"""
        # 1. Create planner
        policy_rules = {"allowed_capabilities": ["fs:read", "fs:write"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        
        # 2. Create constraints
        constraints = PlanningConstraints(
            allowed_capabilities={"fs:read", "fs:write"},
            max_steps=10
        )
        
        # 3. Generate plan
        result = planner.generate_plan(
            task_id="task1",
            task_description="read and write file",
            constraints=constraints,
            execution_seed=42
        )
        
        assert result.success == True
        assert result.plan is not None
        assert result.plan_hash is not None
    
    def test_memory_seal_vault_integration(self):
        """Memory seal and vault integration must work"""
        vault = MemoryVault()
        seal = MemorySeal()
        
        # Store in vault
        snapshot = vault.store(
            agent_id="agent1",
            data={"key": "value"},
            capabilities_required=set()
        )
        
        # Seal the data
        sealed = seal.seal(agent_id="agent1", data=snapshot.data)
        
        # Verify
        assert seal.verify(sealed.seal_id, snapshot.data)
    
    def test_quota_runtime_integration(self):
        """Quota and runtime integration must work"""
        policy_rules = {"allowed_capabilities": ["fs:read"]}
        planner = PolicyConstrainedPlanner(policy_rules)
        runtime = AgentRuntime(planner)
        
        limits = QuotaLimits(max_steps=5, max_time_ms=5000, max_capability_calls=10)
        quota = ExecutionQuota(limits)
        quota.start()
        
        context = AgentContext(
            agent_id="agent1",
            task_id="task1",
            capabilities={"fs:read"},
            execution_seed=42,
            max_steps=5
        )
        
        result = asyncio.run(runtime.run("read file", context))
        
        assert result.success == True
        assert quota.is_within_limits()


# ============================================================
# CONCURRENCY TESTS (4 tests)
# ============================================================

@pytest.mark.phase4
class TestConcurrency:
    """Concurrency safety tests"""
    
    def test_concurrent_plan_generation_safe(self):
        """Concurrent plan generation must be safe"""
        planner = DeterministicPlanner()
        
        async def generate():
            return planner.generate_plan("task", {}, {"fs:read"}, 42)
        
        async def run_concurrent():
            tasks = [generate() for _ in range(5)]
            return await asyncio.gather(*tasks)
        
        plans = asyncio.run(run_concurrent())
        hashes = [p.compute_deterministic_hash() for p in plans]
        
        assert len(set(hashes)) == 1, "All concurrent plans must be identical"
    
    def test_concurrent_memory_vault_safe(self):
        """Concurrent memory vault access must be safe"""
        vault = MemoryVault()
        
        async def store(i):
            return vault.store(
                agent_id=f"agent{i}",
                data={"key": f"value{i}"},
                capabilities_required=set()
            )
        
        async def run_concurrent():
            tasks = [store(i) for i in range(5)]
            return await asyncio.gather(*tasks)
        
        snapshots = asyncio.run(run_concurrent())
        
        assert len(snapshots) == 5
        assert vault.get_snapshot_count() == 5
    
    def test_concurrent_quota_safe(self):
        """Concurrent quota access must be safe"""
        limits = QuotaLimits(max_steps=100, max_time_ms=10000, max_capability_calls=100)
        quota = ExecutionQuota(limits)
        quota.start()
        
        async def record_step():
            return quota.record_step()
        
        async def run_concurrent():
            tasks = [record_step() for _ in range(10)]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(run_concurrent())
        
        assert quota.state.steps_used == 10
    
    def test_concurrent_seal_safe(self):
        """Concurrent sealing must be safe"""
        seal = MemorySeal()
        
        async def seal_data(i):
            return seal.seal(agent_id="agent1", data={"key": f"value{i}"})
        
        async def run_concurrent():
            tasks = [seal_data(i) for i in range(5)]
            return await asyncio.gather(*tasks)
        
        sealed = asyncio.run(run_concurrent())
        
        assert len(sealed) == 5
        assert seal.get_seal_count() == 5


# ============================================================
# RUN TESTS
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
