PROTOCOL_VERSION: str = "1.0"
import asyncio
import pathlib
import subprocess
from typing import Any

from synapse.environment.base import Environment
from synapse.security.execution_guard import ExecutionGuard
from synapse.security.capability_manager import CapabilityManager

class LocalOS(Environment):
    """Concrete environment that runs on the host OS.
    All actions are wrapped by ExecutionGuard to enforce sandboxing and
    capability checks.
    """
    protocol_version: str = "1.0"

    def __init__(self, guard: ExecutionGuard, caps: CapabilityManager):
        self._guard = guard
        self._caps = caps

    async def read_file(self, path: str) -> str:
        # Fix: Use correct path format for capability check
        # path is like "/tmp/..." so we use "fs:read:" + path
        await self._caps.check_capability(["fs:read:" + path])
        async def _read():
            async with self._guard:
                # Use asyncio.to_thread for synchronous file read
                def sync_read():
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                return await asyncio.to_thread(sync_read)
        return await _read()

    async def write_file(self, path: str, data: str) -> None:
        # Fix: Use correct path format for capability check
        # path is like "/tmp/..." so we use "fs:write:" + path
        await self._caps.check_capability(["fs:write:" + path])
        async def _write():
            async with self._guard:
                # Use asyncio.to_thread for synchronous file write
                def sync_write():
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(data)
                await asyncio.to_thread(sync_write)
        await _write()

    async def execute_process(self, command: str, *args) -> Any:
        await self._caps.check_capability(["process:spawn"])
        async def _run():
            async with self._guard:
                proc = await asyncio.create_subprocess_exec(
                    command, *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                return {"returncode": proc.returncode, "stdout": stdout.decode(), "stderr": stderr.decode()}
        return await _run()

    async def http_request(self, method: str, url: str, **kwargs) -> Any:
        await self._caps.check_capability(["network:http"])
        async def _request():
            async with self._guard:
                # Simple async http using aiohttp (installed in requirements)
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url, **kwargs) as resp:
                        return {"status": resp.status, "text": await resp.text()}
        return await _request()
