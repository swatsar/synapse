"""
Base Environment Adapter for Cross-Platform Support.

Protocol Version: 1.0
Spec Version: 3.1
"""

import abc
from typing import Dict, List, Optional, Any
from pathlib import Path

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class EnvironmentAdapter(abc.ABC):
    """Abstract base class for platform-specific environment adapters.

    Provides unified API for file operations, process execution,
    and system information across Windows, macOS, and Linux.

    All implementations must:
    - Include protocol_version="1.0" in all responses
    - Use type hints for all methods
    - Follow Google Style docstrings
    - Respect security constraints
    """

    protocol_version: str = PROTOCOL_VERSION
    spec_version: str = SPEC_VERSION

    @abc.abstractmethod
    async def get_home_dir(self) -> Path:
        """Get the user home directory.

        Returns:
            Path: User home directory path
        """
        pass

    @abc.abstractmethod
    async def get_config_dir(self) -> Path:
        """Get the application configuration directory.

        Returns:
            Path: Configuration directory path
        """
        pass

    @abc.abstractmethod
    async def get_data_dir(self) -> Path:
        """Get the application data directory.

        Returns:
            Path: Data directory path
        """
        pass

    @abc.abstractmethod
    async def get_temp_dir(self) -> Path:
        """Get the temporary directory.

        Returns:
            Path: Temporary directory path
        """
        pass

    @abc.abstractmethod
    async def execute_command(
        self, 
        command: str, 
        timeout: int = 60,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute a shell command.

        Args:
            command: Command to execute
            timeout: Timeout in seconds
            cwd: Working directory
            env: Environment variables

        Returns:
            Dict with stdout, stderr, returncode, protocol_version
        """
        pass

    @abc.abstractmethod
    async def get_os_info(self) -> Dict[str, Any]:
        """Get operating system information.

        Returns:
            Dict with os, version, architecture, protocol_version
        """
        pass

    @abc.abstractmethod
    async def get_network_info(self) -> Dict[str, Any]:
        """Get network information.

        Returns:
            Dict with hostname, ip_addresses, protocol_version
        """
        pass

    @abc.abstractmethod
    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get system resource usage.

        Returns:
            Dict with cpu_percent, memory_percent, disk_percent, protocol_version
        """
        pass

    @abc.abstractmethod
    async def path_exists(self, path: str) -> bool:
        """Check if path exists.

        Args:
            path: Path to check

        Returns:
            bool: True if path exists
        """
        pass

    @abc.abstractmethod
    async def create_directory(
        self, 
        path: str, 
        parents: bool = True,
        mode: int = 0o755
    ) -> bool:
        """Create a directory.

        Args:
            path: Directory path
            parents: Create parent directories if needed
            mode: Directory permissions

        Returns:
            bool: True if successful
        """
        pass

    @abc.abstractmethod
    async def get_environment_variables(self) -> Dict[str, str]:
        """Get all environment variables.

        Returns:
            Dict of environment variables
        """
        pass

    @abc.abstractmethod
    async def set_environment_variable(
        self, 
        key: str, 
        value: str,
        persistent: bool = False
    ) -> bool:
        """Set an environment variable.

        Args:
            key: Variable name
            value: Variable value
            persistent: Make persistent across sessions

        Returns:
            bool: True if successful
        """
        pass

    @abc.abstractmethod
    async def get_process_list(self) -> List[Dict[str, Any]]:
        """Get list of running processes.

        Returns:
            List of process info dicts
        """
        pass

    @abc.abstractmethod
    async def kill_process(self, pid: int) -> bool:
        """Kill a process by PID.

        Args:
            pid: Process ID

        Returns:
            bool: True if successful
        """
        pass

    def _create_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a response with protocol version.

        Args:
            data: Response data

        Returns:
            Dict with protocol_version added
        """
        return {
            **data,
            "protocol_version": self.protocol_version
        }
