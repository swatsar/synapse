"""Tests for Docker environment."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestDockerEnv:
    """Test Docker environment."""

    @pytest.fixture
    def docker_env(self):
        """Create a Docker environment for testing."""
        from synapse.environment.docker_env import DockerEnv
        from synapse.security.execution_guard import ExecutionGuard
        from synapse.security.capability_manager import CapabilityManager
        from synapse.core.models import ResourceLimits

        caps = CapabilityManager()
        caps.grant_capability("docker:run")
        caps.grant_capability("docker:exec")

        limits = ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        )
        guard = ExecutionGuard(limits=limits)

        return DockerEnv(guard=guard, caps=caps)

    def test_docker_env_creation(self, docker_env):
        """Test Docker environment creation."""
        assert docker_env is not None

    def test_protocol_version(self, docker_env):
        """Test protocol version."""
        assert docker_env.protocol_version == "1.0"
