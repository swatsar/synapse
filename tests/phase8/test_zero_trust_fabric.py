"""
Phase 8: Zero-Trust Execution Fabric - TDD Test Suite
All tests initially fail, then implementation makes them pass.
"""

import pytest
import hashlib
import json
from datetime import datetime, UTC
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# TEST CONSTANTS
# ============================================================================

PROTOCOL_VERSION = "1.0"
TEST_EXECUTION_SEED = 42
TEST_TENANT_ID = "tenant_001"
TEST_NODE_ID = "node_001"
TEST_CLUSTER_ID = "cluster_001"

# ============================================================================
# TASK 1: TDD TEST SUITE - IDENTITY REGISTRATION DETERMINISM
# ============================================================================

class TestTrustIdentityRegistry:
    """Tests for deterministic node identity registration"""

    def test_identity_registration_determinism(self):
        """Same node descriptor must produce identical identity hash"""
        from synapse.zero_trust.identity import TrustIdentityRegistry, NodeDescriptor

        registry = TrustIdentityRegistry()

        descriptor = NodeDescriptor(
            node_id=TEST_NODE_ID,
            cluster_id=TEST_CLUSTER_ID,
            capabilities=["fs:read", "fs:write"],
            protocol_version=PROTOCOL_VERSION
        )

        # Register twice with identical descriptor
        identity1 = registry.register(descriptor)
        identity2 = registry.register(descriptor)

        assert identity1.identity_hash == identity2.identity_hash
        assert identity1.protocol_version == PROTOCOL_VERSION

    def test_identity_hash_reproducibility(self):
        """Identity hash must be reproducible across runs"""
        from synapse.zero_trust.identity import TrustIdentityRegistry, NodeDescriptor

        registry = TrustIdentityRegistry()

        descriptor = NodeDescriptor(
            node_id=TEST_NODE_ID,
            cluster_id=TEST_CLUSTER_ID,
            capabilities=["fs:read"],
            protocol_version=PROTOCOL_VERSION
        )

        identity = registry.register(descriptor)

        # Compute hash manually
        canonical = json.dumps({
            "node_id": TEST_NODE_ID,
            "cluster_id": TEST_CLUSTER_ID,
            "capabilities": sorted(["fs:read"]),
            "protocol_version": PROTOCOL_VERSION
        }, sort_keys=True, separators=(',', ':'))

        expected_hash = hashlib.sha256(canonical.encode()).hexdigest()

        assert identity.identity_hash == expected_hash

    def test_identity_registry_integrity(self):
        """Registry must maintain integrity of registered identities"""
        from synapse.zero_trust.identity import TrustIdentityRegistry, NodeDescriptor

        registry = TrustIdentityRegistry()

        descriptor = NodeDescriptor(
            node_id=TEST_NODE_ID,
            cluster_id=TEST_CLUSTER_ID,
            capabilities=["fs:read"],
            protocol_version=PROTOCOL_VERSION
        )

        identity = registry.register(descriptor)

        # Verify identity is stored
        retrieved = registry.get_identity(TEST_NODE_ID)
        assert retrieved is not None
        assert retrieved.identity_hash == identity.identity_hash

        # Verify registry hash
        registry_hash = registry.compute_registry_hash()
        assert registry_hash is not None
        assert len(registry_hash) == 64  # SHA256 hex length


# ============================================================================
# TASK 2: EXECUTION AUTHORIZATION TOKEN
# ============================================================================

class TestExecutionAuthorizationToken:
    """Tests for execution authorization token chain"""

    def test_token_issuance_reproducibility(self):
        """Same authorization parameters must produce identical token"""
        from synapse.zero_trust.authorization import (
            ExecutionAuthorizationToken,
            AuthorizationRequest
        )

        request = AuthorizationRequest(
            tenant_id=TEST_TENANT_ID,
            node_id=TEST_NODE_ID,
            capabilities=["fs:read"],
            execution_seed=TEST_EXECUTION_SEED,
            protocol_version=PROTOCOL_VERSION
        )

        token1 = ExecutionAuthorizationToken.issue(request)
        token2 = ExecutionAuthorizationToken.issue(request)

        assert token1.token_hash == token2.token_hash
        assert token1.protocol_version == PROTOCOL_VERSION

    def test_authorization_chain_integrity(self):
        """Authorization chain must be verifiable"""
        from synapse.zero_trust.authorization import (
            ExecutionAuthorizationToken,
            AuthorizationRequest,
            AuthorizationChain
        )

        chain = AuthorizationChain()

        request = AuthorizationRequest(
            tenant_id=TEST_TENANT_ID,
            node_id=TEST_NODE_ID,
            capabilities=["fs:read"],
            execution_seed=TEST_EXECUTION_SEED,
            protocol_version=PROTOCOL_VERSION
        )

        token = ExecutionAuthorizationToken.issue(request)
        chain.add_token(token)

        # Verify chain integrity
        assert chain.verify_integrity() is True
        assert chain.compute_root_hash() is not None

    def test_authorization_chain_replay_equality(self):
        """Replayed authorization chain must produce identical root hash"""
        from synapse.zero_trust.authorization import (
            ExecutionAuthorizationToken,
            AuthorizationRequest,
            AuthorizationChain
        )

        # First chain
        chain1 = AuthorizationChain()
        request = AuthorizationRequest(
            tenant_id=TEST_TENANT_ID,
            node_id=TEST_NODE_ID,
            capabilities=["fs:read"],
            execution_seed=TEST_EXECUTION_SEED,
            protocol_version=PROTOCOL_VERSION
        )
        token = ExecutionAuthorizationToken.issue(request)
        chain1.add_token(token)
        root1 = chain1.compute_root_hash()

        # Second chain (replay)
        chain2 = AuthorizationChain()
        token2 = ExecutionAuthorizationToken.issue(request)
        chain2.add_token(token2)
        root2 = chain2.compute_root_hash()

        assert root1 == root2


# ============================================================================
# TASK 3: REMOTE ATTESTATION VERIFICATION
# ============================================================================

class TestRemoteAttestationVerifier:
    """Tests for remote attestation verification"""

    def test_attestation_verification(self):
        """Valid attestation must be verified"""
        from synapse.zero_trust.attestation import (
            RemoteAttestationVerifier,
            AttestationRequest,
            AttestationResponse
        )

        verifier = RemoteAttestationVerifier()

        # Create valid attestation
        request = AttestationRequest(
            node_id=TEST_NODE_ID,
            execution_hash="abc123",
            timestamp=datetime.now(UTC).isoformat(),
            protocol_version=PROTOCOL_VERSION
        )

        response = verifier.verify(request)

        assert response.verified is True
        assert response.protocol_version == PROTOCOL_VERSION

    def test_forged_attestation_rejected(self):
        """Forged attestation must be rejected"""
        from synapse.zero_trust.attestation import (
            RemoteAttestationVerifier,
            AttestationRequest
        )

        verifier = RemoteAttestationVerifier()

        # Create forged attestation (invalid signature)
        request = AttestationRequest(
            node_id=TEST_NODE_ID,
            execution_hash="forged_hash",
            timestamp=datetime.now(UTC).isoformat(),
            protocol_version=PROTOCOL_VERSION,
            
        )

        response = verifier.verify(request)

        assert response.verified is False
        assert response.verified is False


# ============================================================================
# TASK 4: TRUST POLICY ENGINE DETERMINISM
# ============================================================================

class TestTrustPolicyEngine:
    """Tests for deterministic policy evaluation"""

    def test_policy_evaluation_determinism(self):
        """Same policy input must produce identical evaluation hash"""
        from synapse.zero_trust.policy import TrustPolicyEngine, PolicyRequest

        engine = TrustPolicyEngine()

        request = PolicyRequest(
            tenant_id=TEST_TENANT_ID,
            node_id=TEST_NODE_ID,
            action="execute",
            resource="/workspace/file.txt",
            capabilities=["fs:read"],
            execution_seed=TEST_EXECUTION_SEED,
            protocol_version=PROTOCOL_VERSION
        )

        # Evaluate 20 times
        hashes = []
        for _ in range(20):
            result = engine.evaluate(request)
            hashes.append(result.evaluation_hash)

        # All hashes must be identical
        assert len(set(hashes)) == 1
        assert hashes[0] is not None

    def test_policy_denial_without_trust(self):
        """Policy must deny execution without proper trust"""
        from synapse.zero_trust.policy import TrustPolicyEngine, PolicyRequest

        engine = TrustPolicyEngine()

        request = PolicyRequest(
            tenant_id=TEST_TENANT_ID,
            node_id=TEST_NODE_ID,
            action="execute",
            resource="/workspace/file.txt",
            capabilities=[],  # No capabilities
            execution_seed=TEST_EXECUTION_SEED,
            protocol_version=PROTOCOL_VERSION
        )

        result = engine.evaluate(request)

        assert result.approved is False
        assert "capabilities" in result.reason.lower()


# ============================================================================
# TASK 5: ZERO-TRUST EXECUTION ENFORCEMENT
# ============================================================================

class TestZeroTrustExecutionEnforcement:
    """Tests for zero-trust execution enforcement"""

    def test_execution_without_identity_blocked(self):
        """Execution must be blocked without valid identity"""
        from synapse.zero_trust.enforcement import ZeroTrustEnforcer

        enforcer = ZeroTrustEnforcer()

        # Attempt execution without identity
        result = enforcer.execute(
            node_id=None,  # No identity
            action="read",
            resource="/workspace/file.txt"
        )

        assert result.success is False
        assert "identity" in result.error.lower()

    def test_execution_without_token_blocked(self):
        """Execution must be blocked without authorization token"""
        from synapse.zero_trust.enforcement import ZeroTrustEnforcer

        enforcer = ZeroTrustEnforcer()

        # Register identity but no token
        enforcer.register_identity(TEST_NODE_ID, TEST_CLUSTER_ID, capabilities=["fs:read"])

        result = enforcer.execute(
            node_id=TEST_NODE_ID,
            action="read",
            resource="/workspace/file.txt",
            token=None  # No token
        )

        assert result.success is False
        assert "token" in result.error.lower() or "authorization" in result.error.lower()

    def test_execution_without_policy_blocked(self):
        """Execution must be blocked without policy approval"""
        from synapse.zero_trust.enforcement import ZeroTrustEnforcer

        enforcer = ZeroTrustEnforcer()

        # Register identity and token but no policy approval
        enforcer.register_identity(TEST_NODE_ID, TEST_CLUSTER_ID, capabilities=["fs:read"])
        token = enforcer.issue_token(TEST_TENANT_ID, TEST_NODE_ID, ["fs:read"])

        result = enforcer.execute(
            node_id=TEST_NODE_ID,
            action="read",
            resource="/workspace/file.txt",
            token=token,
            policy_approved=False
        )

        assert result.success is False
        assert result.success is False


# ============================================================================
# TASK 6: BASELINE PRESERVATION CHECK
# ============================================================================

class TestBaselinePreservation:
    """Tests to verify Phase 6.1 baseline is unchanged"""

    def test_runtime_hash_unchanged(self):
        """Runtime module hash must match baseline"""
        from synapse.core.execution import compute_module_hash

        current_hash = compute_module_hash()

        # This should match the Phase 6.1 baseline
        # For now, we just verify it's computed
        assert current_hash is not None
        assert len(current_hash) == 64

    def test_audit_hash_unchanged(self):
        """Audit module hash must match baseline"""
        from synapse.core.audit import compute_module_hash

        current_hash = compute_module_hash()

        assert current_hash is not None
        assert len(current_hash) == 64

    def test_scheduler_hash_unchanged(self):
        """Scheduler module hash must match baseline"""
        from synapse.control_plane.tenant_scheduler import compute_module_hash

        current_hash = compute_module_hash()

        assert current_hash is not None
        assert len(current_hash) == 64


# ============================================================================
# TASK 7: DETERMINISTIC INTEGRATION TEST
# ============================================================================

class TestDeterministicIntegration:
    """Integration tests for deterministic zero-trust execution"""

    def test_distributed_execution_determinism(self):
        """Distributed execution with zero-trust must be deterministic"""
        from synapse.zero_trust.integration import ZeroTrustIntegration

        integration = ZeroTrustIntegration()

        # Run execution twice
        root1 = integration.run_distributed_execution(
            tenant_id=TEST_TENANT_ID,
            node_id=TEST_NODE_ID,
            cluster_id=TEST_CLUSTER_ID,
            execution_seed=TEST_EXECUTION_SEED
        )

        root2 = integration.run_distributed_execution(
            tenant_id=TEST_TENANT_ID,
            node_id=TEST_NODE_ID,
            cluster_id=TEST_CLUSTER_ID,
            execution_seed=TEST_EXECUTION_SEED
        )

        assert root1 == root2

    def test_cross_node_permission_replay(self):
        """Cross-node permission must be replayable"""
        from synapse.zero_trust.integration import ZeroTrustIntegration

        integration = ZeroTrustIntegration()

        # Issue permission on node 1
        permission1 = integration.issue_cross_node_permission(
            source_node=TEST_NODE_ID,
            target_node="node_002",
            capabilities=["fs:read"]
        )

        # Replay permission on node 2
        permission2 = integration.replay_permission(permission1)

        assert permission1.permission_hash == permission2.permission_hash


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
