"""
Tests for PyPI Package Configuration.

Protocol Version: 1.0
Spec Version: 3.1
"""

import pytest
from pathlib import Path
import tomllib


@pytest.mark.phase6
@pytest.mark.unit
class TestPyPIConfig:
    """Tests for PyPI package configuration."""

    def test_pyproject_exists(self):
        """Check pyproject.toml exists."""
        assert Path("pyproject.toml").exists()

    def test_pyproject_version(self):
        """Check version in pyproject.toml."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert config["project"]["version"].startswith("3.1")

    def test_pyproject_name(self):
        """Check package name."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert config["project"]["name"] == "synapse-agent"

    def test_pyproject_python_version(self):
        """Check minimum Python version."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert config["project"]["requires-python"] == ">=3.11"

    def test_pyproject_entry_points(self):
        """Check entry points defined."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert "synapse" in config["project"]["scripts"]

    def test_pyproject_dependencies(self):
        """Check core dependencies."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        deps = config["project"]["dependencies"]
        # Check for key dependencies
        dep_names = [d.split(">")[0].split("=")[0].split("[")[0] for d in deps]
        assert "pydantic" in dep_names
        assert "fastapi" in dep_names

    def test_pyproject_optional_dependencies(self):
        """Check optional dependencies."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert "dev" in config["project"]["optional-dependencies"]

    def test_pyproject_classifiers(self):
        """Check classifiers include protocol version."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        classifiers = config["project"]["classifiers"]
        # Check for Python 3.11 and 3.12 support
        assert any("3.11" in c for c in classifiers)
        assert any("3.12" in c for c in classifiers)

    def test_pyproject_urls(self):
        """Check project URLs."""
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        urls = config["project"]["urls"]
        assert "Homepage" in urls
        assert "Documentation" in urls


@pytest.mark.phase6
@pytest.mark.unit
class TestRequirementsFiles:
    """Tests for requirements files."""

    def test_requirements_exists(self):
        """Check requirements.txt exists."""
        assert Path("requirements.txt").exists()

    def test_requirements_test_exists(self):
        """Check requirements-test.txt exists."""
        assert Path("requirements-test.txt").exists()

    def test_requirements_not_empty(self):
        """Check requirements.txt is not empty."""
        with open("requirements.txt", "r") as f:
            content = f.read().strip()
        assert len(content) > 0


@pytest.mark.phase6
@pytest.mark.unit
class TestManifest:
    """Tests for MANIFEST.in."""

    def test_manifest_exists(self):
        """Check MANIFEST.in exists."""
        assert Path("MANIFEST.in").exists()

    def test_manifest_includes_config(self):
        """Check MANIFEST.in includes config files."""
        with open("MANIFEST.in", "r") as f:
            content = f.read()
        assert "config" in content.lower() or "include" in content.lower()
