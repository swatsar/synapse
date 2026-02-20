"""
Synapse Environment Adapters.
Cross-platform support for Windows, macOS, and Linux.

Protocol Version: 1.0
Spec Version: 3.1
"""

from synapse.environment.adapters.base import EnvironmentAdapter
from synapse.environment.adapters.windows import WindowsAdapter
from synapse.environment.adapters.linux import LinuxAdapter
from synapse.environment.adapters.macos import MacOSAdapter
from synapse.environment.adapters.factory import get_environment_adapter

__all__ = [
    'EnvironmentAdapter',
    'WindowsAdapter',
    'LinuxAdapter',
    'MacOSAdapter',
    'get_environment_adapter'
]

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
