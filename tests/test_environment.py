"""
Tests for Environment Abstraction Layer.
Cross-platform support for Windows, macOS, and Linux.

Protocol Version: 1.0
Spec Version: 3.1
"""

import pytest
import asyncio
import platform
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Mark all tests in this module as phase5
pytestmark = pytest.mark.phase5


class TestEnvironmentAdapterBase:
    """Tests for the base EnvironmentAdapter class."""

    def test_protocol_version_defined(self):
        """Protocol version must be defined."""
        from synapse.environment.adapters.base import PROTOCOL_VERSION
        assert PROTOCOL_VERSION == "1.0"

    def test_spec_version_defined(self):
        """Spec version must be defined."""
        from synapse.environment.adapters.base import SPEC_VERSION
        assert SPEC_VERSION == "3.1"

    def test_environment_adapter_is_abstract(self):
        """EnvironmentAdapter must be abstract."""
        from synapse.environment.adapters.base import EnvironmentAdapter

        with pytest.raises(TypeError):
            EnvironmentAdapter()


class TestEnvironmentAdapterFactory:
    """Tests for the environment adapter factory."""

    def test_get_environment_adapter_returns_adapter(self):
        """Factory must return an adapter instance."""
        from synapse.environment.adapters.factory import get_environment_adapter
        from synapse.environment.adapters.base import EnvironmentAdapter

        adapter = get_environment_adapter()
        assert isinstance(adapter, EnvironmentAdapter)

    def test_get_environment_adapter_returns_correct_type(self):
        """Factory must return correct adapter for current OS."""
        from synapse.environment.adapters.factory import get_environment_adapter
        from synapse.environment.adapters.windows import WindowsAdapter
        from synapse.environment.adapters.linux import LinuxAdapter
        from synapse.environment.adapters.macos import MacOSAdapter

        adapter = get_environment_adapter()
        system = platform.system()

        if system == "Windows":
            assert isinstance(adapter, WindowsAdapter)
        elif system == "Linux":
            assert isinstance(adapter, LinuxAdapter)
        elif system == "Darwin":
            assert isinstance(adapter, MacOSAdapter)

    def test_get_environment_adapter_singleton(self):
        """Factory must return same instance on multiple calls."""
        from synapse.environment.adapters.factory import get_environment_adapter, reset_adapter

        reset_adapter()  # Reset for clean test

        adapter1 = get_environment_adapter()
        adapter2 = get_environment_adapter()

        assert adapter1 is adapter2

    def test_reset_adapter(self):
        """Reset must create new instance."""
        from synapse.environment.adapters.factory import get_environment_adapter, reset_adapter

        adapter1 = get_environment_adapter()
        reset_adapter()
        adapter2 = get_environment_adapter()

        assert adapter1 is not adapter2

    def test_get_supported_systems(self):
        """Supported systems must include Windows, Linux, macOS."""
        from synapse.environment.adapters.factory import get_supported_systems

        systems = get_supported_systems()

        assert "Windows" in systems
        assert "Linux" in systems
        assert "Darwin" in systems

    def test_is_supported(self):
        """Current OS must be supported."""
        from synapse.environment.adapters.factory import is_supported

        assert is_supported() == True

    def test_get_system_info(self):
        """System info must contain required fields."""
        from synapse.environment.adapters.factory import get_system_info

        info = get_system_info()

        assert "system" in info
        assert "node" in info
        assert "release" in info
        assert "machine" in info
        assert "supported" in info
        assert "protocol_version" in info
        assert info["protocol_version"] == "1.0"


@pytest.mark.asyncio
class TestEnvironmentAdapterMethods:
    """Tests for environment adapter methods."""

    @pytest.fixture
    def adapter(self):
        """Get adapter instance for testing."""
        from synapse.environment.adapters.factory import get_environment_adapter
        return get_environment_adapter()

    async def test_get_home_dir(self, adapter):
        """Home directory must be a valid path."""
        home = await adapter.get_home_dir()

        assert isinstance(home, Path)
        assert home.exists()
        assert str(home) != ""

    async def test_get_config_dir(self, adapter):
        """Config directory must be a valid path."""
        config_dir = await adapter.get_config_dir()

        assert isinstance(config_dir, Path)
        assert "synapse" in str(config_dir).lower() or "Synapse" in str(config_dir)

    async def test_get_data_dir(self, adapter):
        """Data directory must be a valid path."""
        data_dir = await adapter.get_data_dir()

        assert isinstance(data_dir, Path)
        assert "synapse" in str(data_dir).lower() or "Synapse" in str(data_dir)

    async def test_get_temp_dir(self, adapter):
        """Temp directory must be a valid path."""
        temp_dir = await adapter.get_temp_dir()

        assert isinstance(temp_dir, Path)
        assert temp_dir.exists()

    async def test_get_os_info(self, adapter):
        """OS info must contain required fields."""
        os_info = await adapter.get_os_info()

        assert "os" in os_info
        assert "version" in os_info
        assert "architecture" in os_info
        assert "protocol_version" in os_info
        assert os_info["protocol_version"] == "1.0"

    async def test_get_network_info(self, adapter):
        """Network info must contain required fields."""
        network_info = await adapter.get_network_info()

        assert "hostname" in network_info
        assert "ip_addresses" in network_info
        assert "protocol_version" in network_info
        assert network_info["protocol_version"] == "1.0"

    async def test_get_resource_usage(self, adapter):
        """Resource usage must contain required fields."""
        resource_usage = await adapter.get_resource_usage()

        assert "cpu_percent" in resource_usage
        assert "memory_percent" in resource_usage
        assert "disk_percent" in resource_usage
        assert "protocol_version" in resource_usage
        assert resource_usage["protocol_version"] == "1.0"

    async def test_path_exists_true(self, adapter):
        """path_exists must return True for existing path."""
        home = await adapter.get_home_dir()
        exists = await adapter.path_exists(str(home))

        assert exists == True

    async def test_path_exists_false(self, adapter):
        """path_exists must return False for non-existing path."""
        exists = await adapter.path_exists("/non/existing/path/12345")

        assert exists == False

    async def test_create_directory(self, adapter, tmp_path):
        """create_directory must create directory."""
        test_dir = tmp_path / "test_create"

        result = await adapter.create_directory(str(test_dir))

        assert result == True
        assert test_dir.exists()

    async def test_create_directory_with_parents(self, adapter, tmp_path):
        """create_directory must create parent directories."""
        test_dir = tmp_path / "parent" / "child" / "test_create"

        result = await adapter.create_directory(str(test_dir), parents=True)

        assert result == True
        assert test_dir.exists()

    async def test_get_environment_variables(self, adapter):
        """get_environment_variables must return dict."""
        env_vars = await adapter.get_environment_variables()

        assert isinstance(env_vars, dict)
        assert len(env_vars) > 0
        assert "PATH" in env_vars or "path" in env_vars

    async def test_set_environment_variable(self, adapter):
        """set_environment_variable must set variable."""
        import os

        result = await adapter.set_environment_variable(
            "TEST_SYNAPSE_VAR",
            "test_value"
        )

        assert result == True
        assert os.environ.get("TEST_SYNAPSE_VAR") == "test_value"

        # Cleanup
        del os.environ["TEST_SYNAPSE_VAR"]

    async def test_get_process_list(self, adapter):
        """get_process_list must return list."""
        processes = await adapter.get_process_list()

        assert isinstance(processes, list)
        assert len(processes) > 0

    async def test_execute_command_success(self, adapter):
        """execute_command must return success for valid command."""
        result = await adapter.execute_command("echo test", timeout=10)

        assert "stdout" in result
        assert "stderr" in result
        assert "returncode" in result
        assert "protocol_version" in result
        assert result["protocol_version"] == "1.0"
        assert result["returncode"] == 0
        assert "test" in result["stdout"]

    async def test_execute_command_timeout(self, adapter):
        """execute_command must handle timeout."""
        # Use a command that will take longer than timeout
        result = await adapter.execute_command("sleep 10", timeout=1)

        assert result["returncode"] == -1
        assert "timeout" in result["stderr"].lower()


class TestWindowsAdapter:
    """Tests specific to Windows adapter."""

    @pytest.fixture
    def windows_adapter(self):
        """Get Windows adapter instance."""
        from synapse.environment.adapters.windows import WindowsAdapter
        return WindowsAdapter()

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    @pytest.mark.asyncio
    async def test_windows_specific_paths(self, windows_adapter):
        """Windows paths must use correct format."""
        config_dir = await windows_adapter.get_config_dir()

        # Should contain AppData on Windows
        assert "AppData" in str(config_dir) or "synapse" in str(config_dir).lower()


class TestLinuxAdapter:
    """Tests specific to Linux adapter."""

    @pytest.fixture
    def linux_adapter(self):
        """Get Linux adapter instance."""
        from synapse.environment.adapters.linux import LinuxAdapter
        return LinuxAdapter()

    @pytest.mark.skipif(platform.system() != "Linux", reason="Linux only")
    @pytest.mark.asyncio
    async def test_linux_specific_paths(self, linux_adapter):
        """Linux paths must use correct format."""
        config_dir = await linux_adapter.get_config_dir()

        # Should contain .config on Linux
        assert ".config" in str(config_dir) or "synapse" in str(config_dir).lower()


class TestMacOSAdapter:
    """Tests specific to macOS adapter."""

    @pytest.fixture
    def macos_adapter(self):
        """Get macOS adapter instance."""
        from synapse.environment.adapters.macos import MacOSAdapter
        return MacOSAdapter()

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_macos_specific_paths(self, macos_adapter):
        """macOS paths must use correct format."""
        config_dir = await macos_adapter.get_config_dir()

        # Should contain Library on macOS
        assert "Library" in str(config_dir) or "synapse" in str(config_dir).lower()


class TestEnvironmentModuleIntegration:
    """Integration tests for environment module."""

    def test_environment_module_imports(self):
        """All environment module components must be importable."""
        from synapse.environment import (
            Environment,
            EnvironmentAdapter,
            WindowsAdapter,
            LinuxAdapter,
            MacOSAdapter,
            get_environment_adapter,
            LocalOS,
            DockerEnv
        )

        assert Environment is not None
        assert EnvironmentAdapter is not None
        assert WindowsAdapter is not None
        assert LinuxAdapter is not None
        assert MacOSAdapter is not None
        assert get_environment_adapter is not None
        assert LocalOS is not None
        assert DockerEnv is not None

    def test_protocol_version_in_module(self):
        """Module must export protocol version."""
        from synapse.environment import PROTOCOL_VERSION

        assert PROTOCOL_VERSION == "1.0"

    def test_spec_version_in_module(self):
        """Module must export spec version."""
        from synapse.environment import SPEC_VERSION

        assert SPEC_VERSION == "3.1"
