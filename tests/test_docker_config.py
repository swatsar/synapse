"""
Tests for Docker Configuration.

Protocol Version: 1.0
Spec Version: 3.1
"""

import pytest
from pathlib import Path
import yaml


@pytest.mark.phase6
@pytest.mark.integration
class TestDockerConfig:
    """Tests for Docker configuration."""

    def test_dockerfile_exists(self):
        """Check Dockerfile exists."""
        assert Path("docker/Dockerfile").exists()

    def test_docker_compose_exists(self):
        """Check docker-compose.yml exists."""
        assert Path("docker/docker-compose.yml").exists()

    def test_docker_compose_dev_exists(self):
        """Check docker-compose.dev.yml exists."""
        assert Path("docker/docker-compose.dev.yml").exists()

    def test_docker_compose_test_exists(self):
        """Check docker-compose.test.yml exists."""
        assert Path("docker/docker-compose.test.yml").exists()

    def test_dockerignore_exists(self):
        """Check .dockerignore exists."""
        assert Path("docker/.dockerignore").exists()

    def test_dockerfile_protocol_version(self):
        """Check protocol_version in Dockerfile."""
        with open("docker/Dockerfile", "r") as f:
            content = f.read()
        assert "PROTOCOL_VERSION=1.0" in content

    def test_dockerfile_spec_version(self):
        """Check spec_version in Dockerfile."""
        with open("docker/Dockerfile", "r") as f:
            content = f.read()
        assert "SPEC_VERSION=3.1" in content

    def test_dockerfile_non_root_user(self):
        """Check non-root user in Dockerfile."""
        with open("docker/Dockerfile", "r") as f:
            content = f.read()
        assert "USER synapse" in content or "USER nonroot" in content

    def test_dockerfile_healthcheck(self):
        """Check healthcheck in Dockerfile."""
        with open("docker/Dockerfile", "r") as f:
            content = f.read()
        assert "HEALTHCHECK" in content

    def test_dockerfile_labels(self):
        """Check labels in Dockerfile."""
        with open("docker/Dockerfile", "r") as f:
            content = f.read()
        assert "org.synapse.protocol_version" in content

    def test_compose_services(self):
        """Check services in docker-compose.yml."""
        with open("docker/docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        required_services = ["synapse-core", "db", "qdrant", "redis"]
        for service in required_services:
            assert service in compose["services"]

    def test_compose_protocol_version(self):
        """Check protocol_version in docker-compose.yml."""
        with open("docker/docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        synapse_env = compose["services"]["synapse-core"]["environment"]
        # Check if PROTOCOL_VERSION is in environment
        env_dict = {e.split("=")[0]: e.split("=")[1] if "=" in e else e 
                    for e in synapse_env if isinstance(e, str)}
        assert "PROTOCOL_VERSION" in env_dict

    def test_compose_healthchecks(self):
        """Check healthchecks in docker-compose.yml."""
        with open("docker/docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        # Check synapse-core has healthcheck
        assert "healthcheck" in compose["services"]["synapse-core"]
        # Check db has healthcheck
        assert "healthcheck" in compose["services"]["db"]

    def test_compose_networks(self):
        """Check networks in docker-compose.yml."""
        with open("docker/docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        assert "networks" in compose

    def test_compose_volumes(self):
        """Check volumes in docker-compose.yml."""
        with open("docker/docker-compose.yml", "r") as f:
            compose = yaml.safe_load(f)
        assert "volumes" in compose
