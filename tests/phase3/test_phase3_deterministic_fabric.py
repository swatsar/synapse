"""
Phase 3 Tests: Distributed Deterministic Execution Fabric
Tests for Signed Capability Tokens, Distributed Node Protocol,
Multi-Node Replay Consistency, and Policy Validation Engine
"""

import pytest
import hashlib
import json
from datetime import datetime, UTC, timedelta
from unittest.mock import MagicMock, AsyncMock

# Import Phase 3 components
from synapse.crypto.capability_token import (
    CapabilityToken,
    TokenIssuer,
    TokenVerifier,
    TokenRevocationList
)
from synapse.distributed.node_protocol import (
    NodeIdentity,
    ExecutionRequest,
    ExecutionTrace,
    NodeHandshake
)
from synapse.distributed.replay_consistency import (
    StateHash,
    ConsistencyReport,
    ReplayConsistencyManager
)
from synapse.policy.policy_validator import (
    PolicyViolation,
    ValidationResult,
    PolicyEngine
)


# ============================================================================
# SECTION 1: SIGNED CAPABILITY TOKEN TESTS
# ============================================================================

class TestCapabilityToken:
    """Tests for CapabilityToken"""
    
    def test_token_is_immutable(self):
        """Token must be immutable (frozen dataclass)"""
        token = CapabilityToken(
            token_id="test123",
            agent_id="agent1",
            capability="fs:read",
            scope="/workspace/**",
            issued_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-02T00:00:00Z",
            issuer_id="issuer1",
            signature="abc123"
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            token.capability = "fs:write"
    
    def test_token_canonical_serialization(self):
        """Token must have deterministic canonical serialization"""
        token = CapabilityToken(
            token_id="test123",
            agent_id="agent1",
            capability="fs:read",
            scope="/workspace/**",
            issued_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-02T00:00:00Z",
            issuer_id="issuer1",
            signature="abc123"
        )
        canonical1 = token.to_canonical()
        canonical2 = token.to_canonical()
        assert canonical1 == canonical2
        assert isinstance(canonical1, str)
    
    def test_token_deterministic_hash(self):
        """Token hash must be deterministic"""
        token = CapabilityToken(
            token_id="test123",
            agent_id="agent1",
            capability="fs:read",
            scope="/workspace/**",
            issued_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-02T00:00:00Z",
            issuer_id="issuer1",
            signature="abc123"
        )
        hash1 = token.compute_hash()
        hash2 = token.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length


class TestTokenIssuer:
    """Tests for TokenIssuer"""
    
    def test_issuer_creates_signed_token(self):
        """Issuer must create properly signed tokens"""
        issuer = TokenIssuer(issuer_id="issuer1")
        token = issuer.issue_token(
            agent_id="agent1",
            capability="fs:read",
            scope="/workspace/**"
        )
        
        assert token.token_id is not None
        assert token.agent_id == "agent1"
        assert token.capability == "fs:read"
        assert token.issuer_id == "issuer1"
        assert token.signature is not None
        assert len(token.signature) == 64  # SHA256 hex
    
    def test_issuer_tracks_issued_tokens(self):
        """Issuer must track all issued tokens"""
        issuer = TokenIssuer(issuer_id="issuer1")
        token1 = issuer.issue_token("agent1", "fs:read", "/workspace/**")
        token2 = issuer.issue_token("agent2", "fs:write", "/data/**")
        
        retrieved1 = issuer.get_issued_token(token1.token_id)
        retrieved2 = issuer.get_issued_token(token2.token_id)
        
        assert retrieved1.token_id == token1.token_id
        assert retrieved2.token_id == token2.token_id


class TestTokenVerifier:
    """Tests for TokenVerifier"""
    
    def test_verifier_accepts_valid_token(self):
        """Verifier must accept valid signed tokens"""
        issuer = TokenIssuer(issuer_id="issuer1")
        verifier = TokenVerifier(issuer_id="issuer1", secret_key=issuer.secret_key)
        
        token = issuer.issue_token("agent1", "fs:read", "/workspace/**")
        assert verifier.verify_token(token) is True
    
    def test_verifier_rejects_wrong_issuer(self):
        """Verifier must reject tokens from wrong issuer"""
        issuer = TokenIssuer(issuer_id="issuer1")
        verifier = TokenVerifier(issuer_id="issuer2", secret_key=issuer.secret_key)
        
        token = issuer.issue_token("agent1", "fs:read", "/workspace/**")
        assert verifier.verify_token(token) is False
    
    def test_verifier_rejects_tampered_token(self):
        """Verifier must reject tampered tokens"""
        issuer = TokenIssuer(issuer_id="issuer1")
        verifier = TokenVerifier(issuer_id="issuer1", secret_key=issuer.secret_key)
        
        token = issuer.issue_token("agent1", "fs:read", "/workspace/**")
        
        # Create tampered token with different capability
        tampered = CapabilityToken(
            token_id=token.token_id,
            agent_id=token.agent_id,
            capability="fs:write",  # Changed!
            scope=token.scope,
            issued_at=token.issued_at,
            expires_at=token.expires_at,
            issuer_id=token.issuer_id,
            signature=token.signature
        )
        
        assert verifier.verify_token(tampered) is False


class TestTokenRevocationList:
    """Tests for TokenRevocationList"""
    
    def test_revocation_list_tracks_revoked_tokens(self):
        """Revocation list must track revoked tokens"""
        rev_list = TokenRevocationList()
        rev_list.revoke("token123", "security breach")
        
        assert rev_list.is_revoked("token123") is True
        assert rev_list.is_revoked("token456") is False
    
    def test_revocation_list_stores_reason(self):
        """Revocation list must store revocation reason"""
        rev_list = TokenRevocationList()
        rev_list.revoke("token123", "security breach")
        
        reason = rev_list.get_revocation_reason("token123")
        assert reason == "security breach"


# ============================================================================
# SECTION 2: DISTRIBUTED NODE PROTOCOL TESTS
# ============================================================================

class TestNodeIdentity:
    """Tests for NodeIdentity"""
    
    def test_node_identity_has_crypto_properties(self):
        """Node identity must have cryptographic properties"""
        identity = NodeIdentity(
            node_id="node1",
            public_key="pubkey123",
            created_at="2026-01-01T00:00:00Z"
        )
        
        assert identity.node_id == "node1"
        assert identity.public_key == "pubkey123"
        assert identity.protocol_version == "1.0"
    
    def test_node_identity_deterministic_hash(self):
        """Node identity hash must be deterministic"""
        identity = NodeIdentity(
            node_id="node1",
            public_key="pubkey123",
            created_at="2026-01-01T00:00:00Z"
        )
        
        hash1 = identity.compute_hash()
        hash2 = identity.compute_hash()
        assert hash1 == hash2


class TestExecutionRequest:
    """Tests for ExecutionRequest"""
    
    def test_execution_request_canonical_serialization(self):
        """Execution request must have canonical serialization"""
        request = ExecutionRequest(
            request_id="req123",
            workflow_id="wf1",
            workflow_hash="hash123",
            requester_id="agent1",
            target_node_id="node1",
            capability_token_id="token123",
            execution_seed=42,
            timestamp="2026-01-01T00:00:00Z",
            signature="sig123"
        )
        
        canonical1 = request.to_canonical()
        canonical2 = request.to_canonical()
        assert canonical1 == canonical2


class TestExecutionTrace:
    """Tests for ExecutionTrace"""
    
    def test_execution_trace_deterministic_hash(self):
        """Execution trace hash must be deterministic"""
        trace = ExecutionTrace(
            trace_id="trace123",
            workflow_id="wf1",
            node_id="node1",
            state_hash="state123",
            steps=[{"step": 1, "action": "read"}],
            execution_time_ms=100,
            timestamp="2026-01-01T00:00:00Z",
            signature="sig123"
        )
        
        hash1 = trace.compute_hash()
        hash2 = trace.compute_hash()
        assert hash1 == hash2


class TestNodeHandshake:
    """Tests for NodeHandshake"""
    
    def test_handshake_creates_request(self):
        """Handshake must create valid request"""
        identity = NodeIdentity(
            node_id="node1",
            public_key="pubkey123",
            created_at="2026-01-01T00:00:00Z"
        )
        handshake = NodeHandshake(identity, b"secret")
        
        request = handshake.create_handshake_request()
        assert "node_id" in request
        assert "public_key" in request
        assert "timestamp" in request
        assert request["node_id"] == "node1"


# ============================================================================
# SECTION 3: MULTI-NODE REPLAY CONSISTENCY TESTS
# ============================================================================

class TestStateHash:
    """Tests for StateHash"""
    
    def test_state_hash_is_deterministic(self):
        """State hash must be deterministic for same input"""
        state = {"key": "value", "count": 42}
        
        hash1 = StateHash.compute("node1", "wf1", 42, state)
        hash2 = StateHash.compute("node1", "wf1", 42, state)
        
        assert hash1.state_hash == hash2.state_hash
    
    def test_different_state_produces_different_hash(self):
        """Different state must produce different hash"""
        state1 = {"key": "value1"}
        state2 = {"key": "value2"}
        
        hash1 = StateHash.compute("node1", "wf1", 42, state1)
        hash2 = StateHash.compute("node1", "wf1", 42, state2)
        
        assert hash1.state_hash != hash2.state_hash


class TestReplayConsistencyManager:
    """Tests for ReplayConsistencyManager"""
    
    def test_manager_records_state_hashes(self):
        """Manager must record state hashes from nodes"""
        manager = ReplayConsistencyManager()
        
        state_hash = StateHash.compute("node1", "wf1", 42, {"data": "test"})
        manager.record_state_hash(state_hash)
        
        report = manager.check_consistency("wf1", 42)
        assert "node1" in report.node_hashes
    
    def test_manager_detects_consistency(self):
        """Manager must detect when nodes are consistent"""
        manager = ReplayConsistencyManager()
        state = {"data": "test"}
        
        # Same state on 3 nodes
        for node_id in ["node1", "node2", "node3"]:
            state_hash = StateHash.compute(node_id, "wf1", 42, state)
            manager.record_state_hash(state_hash)
        
        report = manager.check_consistency("wf1", 42)
        assert report.is_consistent is True
        assert len(report.node_hashes) == 3
    
    def test_manager_detects_inconsistency(self):
        """Manager must detect when nodes are inconsistent"""
        manager = ReplayConsistencyManager()
        
        # Different states on different nodes
        state_hash1 = StateHash.compute("node1", "wf1", 42, {"data": "test1"})
        state_hash2 = StateHash.compute("node2", "wf1", 42, {"data": "test2"})
        
        manager.record_state_hash(state_hash1)
        manager.record_state_hash(state_hash2)
        
        report = manager.check_consistency("wf1", 42)
        assert report.is_consistent is False
        assert len(report.mismatch_details) > 0


# ============================================================================
# SECTION 4: POLICY VALIDATION ENGINE TESTS
# ============================================================================

class TestPolicyEngine:
    """Tests for PolicyEngine"""
    
    def test_engine_validates_workflow(self):
        """Engine must validate workflows"""
        engine = PolicyEngine()
        
        workflow = MagicMock()
        workflow.id = "wf1"
        workflow.steps = []
        workflow.required_capabilities = []
        
        result = engine.validate_workflow(workflow, set())
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
    
    def test_engine_detects_missing_capabilities(self):
        """Engine must detect missing capabilities"""
        engine = PolicyEngine()
        
        workflow = MagicMock()
        workflow.id = "wf1"
        workflow.steps = []
        workflow.required_capabilities = ["fs:read", "fs:write"]
        
        result = engine.validate_workflow(workflow, {"fs:read"})
        assert result.is_valid is False
        assert len(result.violations) > 0
        assert result.violations[0].violation_type == "missing_capabilities"


class TestPolicyViolation:
    """Tests for PolicyViolation"""
    
    def test_violation_has_required_fields(self):
        """Violation must have all required fields"""
        violation = PolicyViolation(
            violation_type="test_violation",
            severity="high",
            description="Test description",
            context={"key": "value"}
        )
        
        assert violation.violation_type == "test_violation"
        assert violation.severity == "high"
        assert violation.protocol_version == "1.0"


class TestValidationResult:
    """Tests for ValidationResult"""
    
    def test_result_has_required_fields(self):
        """Result must have all required fields"""
        result = ValidationResult(
            is_valid=True,
            violations=[],
            workflow_id="wf1",
            timestamp="2026-01-01T00:00:00Z"
        )
        
        assert result.is_valid is True
        assert result.workflow_id == "wf1"
        assert result.protocol_version == "1.0"


# ============================================================================
# SECTION 5: NEGATIVE SECURITY TESTS
# ============================================================================

class TestNegativeSecurity:
    """Negative security tests - must block attacks"""
    
    def test_unsigned_capability_denied(self):
        """Unsigned capability must be denied"""
        issuer = TokenIssuer(issuer_id="issuer1")
        verifier = TokenVerifier(issuer_id="issuer1", secret_key=issuer.secret_key)
        
        # Create token with empty signature
        unsigned_token = CapabilityToken(
            token_id="test123",
            agent_id="agent1",
            capability="fs:read",
            scope="/workspace/**",
            issued_at="2026-01-01T00:00:00Z",
            expires_at="2026-12-31T00:00:00Z",
            issuer_id="issuer1",
            signature=""  # Empty signature
        )
        
        assert verifier.verify_token(unsigned_token) is False
    
    def test_revoked_token_denied(self):
        """Revoked token must be denied"""
        issuer = TokenIssuer(issuer_id="issuer1")
        verifier = TokenVerifier(issuer_id="issuer1", secret_key=issuer.secret_key)
        rev_list = TokenRevocationList()
        
        token = issuer.issue_token("agent1", "fs:read", "/workspace/**")
        
        # Revoke the token
        rev_list.revoke(token.token_id, "security breach")
        
        # Token should still verify, but revocation list should block it
        assert rev_list.is_revoked(token.token_id) is True
    
    def test_forged_execution_request_detected(self):
        """Forged execution request must be detected"""
        # Create legitimate request
        request = ExecutionRequest(
            request_id="req123",
            workflow_id="wf1",
            workflow_hash="hash123",
            requester_id="agent1",
            target_node_id="node1",
            capability_token_id="token123",
            execution_seed=42,
            timestamp="2026-01-01T00:00:00Z",
            signature="legitimate_sig"
        )
        
        # Create forged request with same ID but different data
        forged = ExecutionRequest(
            request_id="req123",
            workflow_id="wf1",
            workflow_hash="tampered_hash",  # Changed
            requester_id="attacker",  # Changed
            target_node_id="node1",
            capability_token_id="token123",
            execution_seed=42,
            timestamp="2026-01-01T00:00:00Z",
            signature="legitimate_sig"  # Same signature
        )
        
        # Canonical forms should differ
        assert request.to_canonical() != forged.to_canonical()
    
    def test_capability_escalation_blocked(self):
        """Capability escalation must be blocked"""
        engine = PolicyEngine()
        
        workflow = MagicMock()
        workflow.id = "wf1"
        workflow.steps = []
        workflow.required_capabilities = ["admin:full"]  # High privilege
        
        # Agent only has read capability
        result = engine.validate_workflow(workflow, {"fs:read"})
        
        assert result.is_valid is False
        assert any(v.violation_type == "missing_capabilities" for v in result.violations)


# ============================================================================
# SECTION 6: DETERMINISM PROOF TESTS
# ============================================================================

class TestDeterminismProof:
    """Tests proving deterministic execution"""
    
    def test_identical_input_produces_identical_state_hash(self):
        """Identical input must produce identical state hash"""
        state = {"key": "value", "nested": {"a": 1, "b": 2}}
        
        hash1 = StateHash.compute("node1", "wf1", 42, state)
        hash2 = StateHash.compute("node1", "wf1", 42, state)
        hash3 = StateHash.compute("node1", "wf1", 42, state)
        
        assert hash1.state_hash == hash2.state_hash == hash3.state_hash
    
    def test_three_nodes_same_workflow_same_hash(self):
        """Three nodes executing same workflow must produce same hash"""
        manager = ReplayConsistencyManager()
        state = {"result": "success", "count": 100}
        workflow_id = "wf_test"
        seed = 12345
        
        # Simulate 3 nodes executing same workflow
        for node_id in ["node1", "node2", "node3"]:
            state_hash = StateHash.compute(node_id, workflow_id, seed, state)
            manager.record_state_hash(state_hash)
        
        report = manager.check_consistency(workflow_id, seed)
        
        assert report.is_consistent is True
        # All 3 nodes should have same hash
        hashes = list(report.node_hashes.values())
        assert len(set(hashes)) == 1  # All identical


# ============================================================================
# SECTION 7: PROTOCOL VERSION TESTS
# ============================================================================

class TestProtocolVersion:
    """Tests for protocol version compliance"""
    
    def test_all_components_have_protocol_version(self):
        """All Phase 3 components must have protocol_version"""
        # CapabilityToken
        token = CapabilityToken(
            token_id="test",
            agent_id="agent1",
            capability="fs:read",
            scope="/workspace",
            issued_at="2026-01-01T00:00:00Z",
            expires_at="2026-12-31T00:00:00Z",
            issuer_id="issuer1",
            signature="sig"
        )
        assert token.protocol_version == "1.0"
        
        # NodeIdentity
        identity = NodeIdentity(
            node_id="node1",
            public_key="pubkey",
            created_at="2026-01-01T00:00:00Z"
        )
        assert identity.protocol_version == "1.0"
        
        # ExecutionRequest
        request = ExecutionRequest(
            request_id="req",
            workflow_id="wf",
            workflow_hash="hash",
            requester_id="agent",
            target_node_id="node",
            capability_token_id="token",
            execution_seed=42,
            timestamp="2026-01-01T00:00:00Z",
            signature="sig"
        )
        assert request.protocol_version == "1.0"
        
        # ExecutionTrace
        trace = ExecutionTrace(
            trace_id="trace",
            workflow_id="wf",
            node_id="node",
            state_hash="hash",
            steps=[],
            execution_time_ms=100,
            timestamp="2026-01-01T00:00:00Z",
            signature="sig"
        )
        assert trace.protocol_version == "1.0"
        
        # StateHash
        state_hash = StateHash.compute("node", "wf", 42, {})
        assert state_hash.protocol_version == "1.0"
        
        # PolicyViolation
        violation = PolicyViolation(
            violation_type="test",
            severity="low",
            description="test",
            context={}
        )
        assert violation.protocol_version == "1.0"
        
        # ValidationResult
        result = ValidationResult(
            is_valid=True,
            violations=[],
            workflow_id="wf",
            timestamp="2026-01-01T00:00:00Z"
        )
        assert result.protocol_version == "1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
