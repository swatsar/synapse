"""Environment Abstraction Layer for cross-platform compatibility.

Implements SYSTEM_SPEC_v3.1 - Environment Abstraction.
With comprehensive audit logging.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional
from enum import Enum
import platform
import subprocess

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Import audit for logging
from synapse.observability.logger import audit


class OSType(str, Enum):
    """Operating system types."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class EnvironmentAdapter(ABC):
    """Base class for environment adapters."""

    @abstractmethod
    async def get_home_dir(self) -> Path:
        """Get user home directory."""
        pass

    @abstractmethod
    async def get_config_dir(self) -> Path:
        """Get configuration directory."""
        pass

    @abstractmethod
    async def execute_command(self, command: str, timeout: int = 60) -> Dict:
        """Execute shell command safely."""
        pass

    @abstractmethod
    async def get_os_info(self) -> Dict:
        """Get operating system information."""
        pass


class LinuxAdapter(EnvironmentAdapter):
    """Linux environment adapter."""

    async def get_home_dir(self) -> Path:
        """Get Linux home directory."""
        return Path.home()

    async def get_config_dir(self) -> Path:
        """Get Linux config directory."""
        return Path.home() / ".config" / "synapse"

    async def execute_command(self, command: str, timeout: int = 60) -> Dict:
        """Execute command on Linux with audit logging."""
        # Audit: command execution started
        audit(
            event="command_execution_started",
            command=command[:100],
            timeout=timeout,
            protocol_version=PROTOCOL_VERSION
        )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Audit: command execution completed
            audit(
                event="command_execution_completed",
                return_code=result.returncode,
                protocol_version=PROTOCOL_VERSION
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "protocol_version": PROTOCOL_VERSION
            }
        except Exception as e:
            # Audit: command execution failed
            audit(
                event="command_execution_failed",
                error=str(e)[:200],
                protocol_version=PROTOCOL_VERSION
            )
            return {
                "success": False,
                "error": str(e),
                "protocol_version": PROTOCOL_VERSION
            }

    async def get_os_info(self) -> Dict:
        """Get Linux OS information."""
        return {
            "os_type": OSType.LINUX.value,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "protocol_version": PROTOCOL_VERSION
        }


class MacOSAdapter(LinuxAdapter):
    """macOS environment adapter (inherits from Linux)."""

    async def get_os_info(self) -> Dict:
        """Get macOS OS information."""
        return {
            "os_type": OSType.MACOS.value,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "protocol_version": PROTOCOL_VERSION
        }


class WindowsAdapter(EnvironmentAdapter):
    """Windows environment adapter."""

    async def get_home_dir(self) -> Path:
        """Get Windows home directory."""
        return Path.home()

    async def get_config_dir(self) -> Path:
        """Get Windows config directory."""
        return Path.home() / "AppData" / "Local" / "Synapse"

    async def execute_command(self, command: str, timeout: int = 60) -> Dict:
        """Execute command on Windows with audit logging."""
        # Audit: command execution started
        audit(
            event="command_execution_started",
            command=command[:100],
            timeout=timeout,
            protocol_version=PROTOCOL_VERSION
        )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Audit: command execution completed
            audit(
                event="command_execution_completed",
                return_code=result.returncode,
                protocol_version=PROTOCOL_VERSION
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "protocol_version": PROTOCOL_VERSION
            }
        except Exception as e:
            # Audit: command execution failed
            audit(
                event="command_execution_failed",
                error=str(e)[:200],
                protocol_version=PROTOCOL_VERSION
            )
            return {
                "success": False,
                "error": str(e),
                "protocol_version": PROTOCOL_VERSION
            }

    async def get_os_info(self) -> Dict:
        """Get Windows OS information."""
        return {
            "os_type": OSType.WINDOWS.value,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "protocol_version": PROTOCOL_VERSION
        }


def get_environment_adapter() -> EnvironmentAdapter:
    """Factory for getting the current OS adapter with audit logging."""
    system = platform.system()

    # Audit: environment adapter requested
    audit(
        event="environment_adapter_requested",
        system=system,
        protocol_version=PROTOCOL_VERSION
    )

    if system == "Windows":
        adapter = WindowsAdapter()
    elif system == "Darwin":
        adapter = MacOSAdapter()
    else:
        adapter = LinuxAdapter()

    # Audit: environment adapter created
    audit(
        event="environment_adapter_created",
        adapter_type=type(adapter).__name__,
        protocol_version=PROTOCOL_VERSION
    )

    return adapter
