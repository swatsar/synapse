"""
Environment Adapter Factory.

Protocol Version: 1.0
Spec Version: 3.1
"""

import platform
from typing import Optional, List, Dict, Any

from synapse.environment.adapters.base import EnvironmentAdapter, PROTOCOL_VERSION

# Global adapter instance (singleton pattern)
_adapter_instance: Optional[EnvironmentAdapter] = None


def get_environment_adapter() -> EnvironmentAdapter:
    """Factory function to get the appropriate environment adapter.

    Returns:
        EnvironmentAdapter: Platform-specific adapter instance

    Raises:
        RuntimeError: If the operating system is not supported
    """
    global _adapter_instance

    if _adapter_instance is not None:
        return _adapter_instance

    system = platform.system()

    if system == "Windows":
        from synapse.environment.adapters.windows import WindowsAdapter
        _adapter_instance = WindowsAdapter()
    elif system == "Darwin":
        from synapse.environment.adapters.macos import MacOSAdapter
        _adapter_instance = MacOSAdapter()
    elif system == "Linux":
        from synapse.environment.adapters.linux import LinuxAdapter
        _adapter_instance = LinuxAdapter()
    else:
        raise RuntimeError(f"Unsupported operating system: {system}")

    return _adapter_instance


def reset_adapter():
    """Reset the adapter instance (useful for testing)."""
    global _adapter_instance
    _adapter_instance = None


def get_supported_systems() -> List[str]:
    """Get list of supported operating systems.

    Returns:
        List of supported OS names
    """
    return ["Windows", "Darwin", "Linux"]


def is_supported(system: Optional[str] = None) -> bool:
    """Check if a system is supported.

    Args:
        system: System name (defaults to current system)

    Returns:
        bool: True if supported
    """
    if system is None:
        system = platform.system()
    return system in get_supported_systems()


def get_system_info() -> Dict[str, Any]:
    """Get current system information.

    Returns:
        Dict with system information
    """
    return {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'node': platform.node(),  # Added 'node' field
        'supported': is_supported(),
        'protocol_version': PROTOCOL_VERSION
    }
