"""
Synapse Environment Abstraction Layer.
Cross-platform support for Windows, macOS, and Linux.

Protocol Version: 1.0
Spec Version: 3.1
"""

from synapse.environment.adapters import (
    LinuxAdapter,
    MacOSAdapter,
    WindowsAdapter,
    get_environment_adapter,
)
from synapse.environment.base import Environment, EnvironmentAdapter
from synapse.environment.docker_env import DockerEnv
from synapse.environment.local_os import LocalOS

__all__ = [
    'DockerEnv',
    'Environment',
    'EnvironmentAdapter',
    'LinuxAdapter',
    'LocalOS',
    'MacOSAdapter',
    'WindowsAdapter',
    'get_environment_adapter'
]

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
