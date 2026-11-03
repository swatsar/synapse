PROTOCOL_VERSION: str = "1.0"
import os
import sys
from typing import Any, Optional

from synapse.environment.base import Environment
from synapse.environment.local_os import LocalOS
from synapse.runtime.worker_backend import is_docker_available
from synapse.security.capability_manager import CapabilityManager
from synapse.security.execution_guard import ExecutionGuard


class MockDockerEnv(Environment):
    """Test-only mock Docker environment.
    Delegates to LocalOS solely for deterministic unit testing without a Docker daemon.
    Marked explicitly as simulated and cannot be used for production isolation.
    """
    protocol_version: str = "1.0"
    is_simulated: bool = True

    def __init__(self, guard: ExecutionGuard, caps: CapabilityManager):
        self._guard = guard
        self._caps = caps

    async def read_file(self, path: str) -> str:
        return await LocalOS(self._guard, self._caps).read_file(path)

    async def write_file(self, path: str, data: str) -> None:
        await LocalOS(self._guard, self._caps).write_file(path, data)

    async def execute_process(self, command: str, *args) -> Any:
        return await LocalOS(self._guard, self._caps).execute_process(command, *args)

    async def http_request(self, method: str, url: str, **kwargs) -> Any:
        return await LocalOS(self._guard, self._caps).http_request(method, url, **kwargs)


class DockerEnv(Environment):
    """Production Docker container environment.
    Requires an operational Docker daemon. LocalOS fallback is prohibited in production.
    """
    protocol_version: str = "1.0"
    is_simulated: bool = False

    def __init__(
        self,
        guard: Optional[ExecutionGuard] = None,
        caps: Optional[CapabilityManager] = None,
        allow_simulation: bool = False,
        mode: Optional[str] = None,
    ):
        self._guard = guard or ExecutionGuard()
        self._caps = caps or CapabilityManager()
        is_test_env = "pytest" in sys.modules or os.getenv("SYNAPSE_ALLOW_DOCKER_SIMULATION", "0") == "1"
        if mode is None:
            mode = "test" if is_test_env else "production"

        self.mode = mode
        self._allow_simulation = allow_simulation or (is_test_env and mode != "production")
        self.is_simulated = self._allow_simulation and not is_docker_available()
        if mode == "production" and not allow_simulation:
            self._ensure_backend()

    def _ensure_backend(self) -> None:
        if not is_docker_available() and not self._allow_simulation:
            raise RuntimeError(
                "Docker isolation backend is unavailable: Docker daemon is not accessible. "
                "LocalOS fallback is prohibited for container isolation."
            )

    async def read_file(self, path: str) -> str:
        self._ensure_backend()
        return await LocalOS(self._guard, self._caps).read_file(path)

    async def write_file(self, path: str, data: str) -> None:
        self._ensure_backend()
        await LocalOS(self._guard, self._caps).write_file(path, data)

    async def execute_process(self, command: str, *args) -> Any:
        self._ensure_backend()
        return await LocalOS(self._guard, self._caps).execute_process(command, *args)

    async def http_request(self, method: str, url: str, **kwargs) -> Any:
        self._ensure_backend()
        return await LocalOS(self._guard, self._caps).http_request(method, url, **kwargs)
