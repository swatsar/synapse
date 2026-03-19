"""Unit tests for CapabilityScope system. Phase 2 — Security.

TDD: These tests define requirements FIRST.
"""
import pytest

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase2
@pytest.mark.unit
@pytest.mark.security
class TestCapabilityScope:
    def test_scope_enum_has_filesystem_capabilities(self):
        from synapse.core.capability_scope import CapabilityScope
        assert CapabilityScope.FILESYSTEM_READ.value == "fs:read"
        assert CapabilityScope.FILESYSTEM_WRITE.value == "fs:write"
        assert CapabilityScope.FILESYSTEM_DELETE.value == "fs:delete"

    def test_scope_enum_has_network_capabilities(self):
        from synapse.core.capability_scope import CapabilityScope
        assert CapabilityScope.NETWORK_HTTP.value == "net:http"
        assert CapabilityScope.NETWORK_SCAN.value == "net:scan"

    def test_scope_enum_has_process_capabilities(self):
        from synapse.core.capability_scope import CapabilityScope
        assert CapabilityScope.PROCESS_SPAWN.value == "os:process"

    def test_capability_token_creation(self):
        from synapse.core.capability_scope import CapabilityToken, CapabilityScope
        token = CapabilityToken(scope=CapabilityScope.FILESYSTEM_READ, issued_to="agent1")
        assert token.token_id
        assert token.scope == CapabilityScope.FILESYSTEM_READ
        assert token.protocol_version == PROTOCOL_VERSION

    def test_token_full_scope_without_path(self):
        from synapse.core.capability_scope import CapabilityToken, CapabilityScope
        token = CapabilityToken(scope=CapabilityScope.FILESYSTEM_READ, issued_to="a")
        assert token.full_scope == "fs:read"

    def test_token_full_scope_with_path_constraint(self):
        from synapse.core.capability_scope import CapabilityToken, CapabilityScope
        token = CapabilityToken(scope=CapabilityScope.FILESYSTEM_READ, path_constraint="/workspace/**", issued_to="a")
        assert token.full_scope == "fs:read:/workspace/**"

    def test_token_matches_exact_scope(self):
        from synapse.core.capability_scope import CapabilityToken, CapabilityScope
        token = CapabilityToken(scope=CapabilityScope.FILESYSTEM_READ, issued_to="a")
        assert token.matches("fs:read")

    def test_token_matches_wildcard_path(self):
        from synapse.core.capability_scope import CapabilityToken, CapabilityScope
        token = CapabilityToken(scope=CapabilityScope.FILESYSTEM_READ, path_constraint="/workspace/**", issued_to="a")
        assert token.matches("fs:read:/workspace/file.txt")

    def test_token_not_expired(self):
        from synapse.core.capability_scope import CapabilityToken, CapabilityScope
        token = CapabilityToken(scope=CapabilityScope.FILESYSTEM_READ, issued_to="a")
        assert not token.is_expired()

    def test_token_risk_level(self):
        from synapse.core.capability_scope import CapabilityToken, CapabilityScope
        read = CapabilityToken(scope=CapabilityScope.FILESYSTEM_READ, issued_to="a")
        delete = CapabilityToken(scope=CapabilityScope.FILESYSTEM_DELETE, issued_to="a")
        execute = CapabilityToken(scope=CapabilityScope.FILESYSTEM_EXECUTE, issued_to="a")
        assert read.risk_level < delete.risk_level < execute.risk_level

    def test_make_token_factory(self):
        from synapse.core.capability_scope import make_token, CapabilityScope
        token = make_token(CapabilityScope.NETWORK_HTTP, "agent1", path="/api/**", ttl_hours=1)
        assert token.full_scope == "net:http:/api/**"
        assert token.expires_at is not None
        assert token.issued_to == "agent1"

    def test_default_agent_capabilities(self):
        from synapse.core.capability_scope import DEFAULT_AGENT_CAPABILITIES, CapabilityScope
        assert CapabilityScope.FILESYSTEM_READ in DEFAULT_AGENT_CAPABILITIES
        assert CapabilityScope.SYSTEM_INFO in DEFAULT_AGENT_CAPABILITIES
        assert CapabilityScope.PROCESS_SPAWN not in DEFAULT_AGENT_CAPABILITIES  # too risky
