"""
Synapse Environment Abstraction Layer.
Cross-platform support for Windows, macOS, and Linux.

Protocol Version: 1.0
Spec Version: 3.1
"""

from synapse.environment.base import Environment, EnvironmentAdapter
from synapse.environment.adapters import (
    WindowsAdapter,
    LinuxAdapter,
    MacOSAdapter,
    get_environment_adapter
)
from synapse.environment.local_os import LocalOS
from synapse.environment.docker_env import DockerEnv

__all__ = [
    'Environment',
    'EnvironmentAdapter',
    'WindowsAdapter',
    'LinuxAdapter',
    'MacOSAdapter',
    'get_environment_adapter',
    'LocalOS',
    'DockerEnv'
]

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
