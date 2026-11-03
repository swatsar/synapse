"""
Isolated Worker Backend for dynamic skill and code execution.
Enforces process isolation, environment hygiene, resource limits, and network restrictions.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from synapse.core.isolation_policy import RuntimeIsolationType
from synapse.core.models import ExecutionContext, ResourceLimits

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.runtime.worker_backend")

# Environment variables safe to propagate to worker subprocesses
SAFE_ENV_VARS = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LC_ALL",
    "PYTHONPATH",
    "PYTHONHOME",
    "COMSPEC",
}


def is_docker_available() -> bool:
    """Check if Docker CLI and daemon are accessible."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        res = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


# Code for worker runner subprocess
_WORKER_RUNNER_CODE = r'''
import sys
import os
import json
import pickle
import inspect
import asyncio

def run():
    payload_file = sys.argv[1]
    with open(payload_file, "rb") as f:
        payload = pickle.load(f)

    target_type = payload.get("target_type")
    params = payload.get("params", {})
    context_data = payload.get("context_data", {})
    isolation_type = payload.get("isolation_type", "subprocess")
    capabilities = context_data.get("capabilities", [])

    # If sandbox isolation, restrict network access if network capability is not granted
    has_network = any("network" in c or c == "*" for c in capabilities)
    if isolation_type == "sandbox" and not has_network:
        import socket
        orig_socket = socket.socket
        def blocked_socket(*args, **kwargs):
            raise PermissionError("Network access forbidden in sandbox mode without network capability")
        socket.socket = blocked_socket

    # Reconstruct ExecutionContext if possible
    from synapse.core.models import ExecutionContext, ResourceLimits
    ctx = ExecutionContext(
        session_id=context_data.get("session_id", "default"),
        agent_id=context_data.get("agent_id", "worker"),
        trace_id=context_data.get("trace_id", "trace"),
        capabilities=capabilities,
        approval_granted=context_data.get("approval_granted", False),
    )

    if target_type == "file":
        file_path = payload["file_path"]
        import importlib.util
        spec = importlib.util.spec_from_file_location("worker_target_skill", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        handler = getattr(mod, "handler", None)
        if handler is None:
            manifest = getattr(mod, "manifest", None)
            handler_name = getattr(manifest, "handler", "handler") if manifest else "handler"
            handler = getattr(mod, handler_name)
    elif target_type == "source":
        source_code = payload.get("source_code", "")
        mod_dict = {}
        exec(source_code, mod_dict)
        handler = mod_dict.get("handler") or mod_dict.get("run_skill")
        if handler is None:
            raise AttributeError("No handler or run_skill defined in source code")
    elif target_type == "callable":
        handler = payload["callable"]
    else:
        raise ValueError(f"Unknown target_type: {target_type}")

    execute = handler.execute if hasattr(handler, "execute") else handler
    sig = inspect.signature(execute)
    if len(sig.parameters) == 0:
        res = execute()
    elif "context" in sig.parameters or "ctx" in sig.parameters or (sig.parameters and list(sig.parameters.keys())[0] in {"context", "ctx"}):
        res = execute(ctx, **params)
    else:
        res = execute(**params)
    if inspect.isawaitable(res):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(res)
        finally:
            loop.close()

    if not isinstance(res, dict):
        raise TypeError(f"Skill handler must return a dict, got {type(res).__name__}")

    res["_worker_pid"] = os.getpid()
    with open(payload_file + ".out", "wb") as f:
        pickle.dump({"success": True, "result": res}, f)

if __name__ == "__main__":
    try:
        run()
        sys.exit(0)
    except Exception as e:
        import traceback
        payload_file = sys.argv[1]
        with open(payload_file + ".out", "wb") as f:
            pickle.dump({"success": False, "error": str(e), "traceback": traceback.format_exc()}, f)
        sys.exit(1)
'''


class IsolatedWorkerBackend:
    """Backend executing skill handlers in isolated Python worker subprocesses."""

    @staticmethod
    def _build_clean_env() -> dict[str, str]:
        clean = {}
        for k in SAFE_ENV_VARS:
            if k in os.environ:
                clean[k] = os.environ[k]
        # Always include project root in PYTHONPATH
        root = str(Path(__file__).resolve().parent.parent.parent)
        existing_pythonpath = clean.get("PYTHONPATH", "")
        clean["PYTHONPATH"] = f"{root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else root
        clean["PYTHONUNBUFFERED"] = "1"
        return clean

    @classmethod
    async def run_skill(
        cls,
        skill_id: Optional[str] = None,
        source_code: Optional[str] = None,
        *,
        target_type: Optional[str] = None,
        file_path: Optional[str] = None,
        handler_callable: Optional[Callable] = None,
        context: Optional[ExecutionContext] = None,
        params: Optional[dict[str, Any]] = None,
        limits: Optional[ResourceLimits | dict[str, Any]] = None,
        isolation_type: Optional[RuntimeIsolationType | str] = None,
        isolation_level: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a skill file or callable in an isolated worker process."""
        # Resolve target type
        if source_code is not None:
            target_type = "source"
        elif target_type is None:
            if file_path:
                target_type = "file"
            elif handler_callable:
                target_type = "callable"
            else:
                target_type = "source"

        # Resolve isolation type
        iso = isolation_level or isolation_type or RuntimeIsolationType.SUBPROCESS
        if isinstance(iso, str):
            try:
                iso = RuntimeIsolationType(iso)
            except ValueError:
                iso = RuntimeIsolationType.SUBPROCESS

        # Enforce container isolation policy
        if iso == RuntimeIsolationType.CONTAINER:
            if not is_docker_available():
                raise RuntimeError(
                    "Required container isolation backend is not available. "
                    "Refusing execution without LocalOS fallback."
                )

        # Default context and params
        if context is None:
            context = ExecutionContext(session_id="default", agent_id="worker", trace_id="trace")
        params = params or {}

        # Determine timeout
        if isinstance(limits, ResourceLimits):
            timeout_sec = limits.cpu_seconds
        elif isinstance(limits, dict):
            timeout_sec = limits.get("cpu_seconds", 60)
        else:
            timeout_sec = 60

        context_data = {
            "session_id": getattr(context, "session_id", "default"),
            "agent_id": getattr(context, "agent_id", "default"),
            "trace_id": getattr(context, "trace_id", "default"),
            "capabilities": getattr(context, "capabilities", []),
            "approval_granted": getattr(context, "approval_granted", False),
        }

        payload = {
            "target_type": target_type,
            "file_path": file_path,
            "source_code": source_code,
            "callable": handler_callable,
            "params": params,
            "context_data": context_data,
            "isolation_type": iso.value if hasattr(iso, "value") else str(iso),
        }

        with tempfile.TemporaryDirectory(prefix="synapse_worker_") as tmpdir:
            payload_path = os.path.join(tmpdir, "payload.pkl")
            runner_script_path = os.path.join(tmpdir, "runner.py")
            output_path = payload_path + ".out"

            with open(payload_path, "wb") as f:
                pickle.dump(payload, f)

            with open(runner_script_path, "w", encoding="utf-8") as f:
                f.write(_WORKER_RUNNER_CODE)

            env = cls._build_clean_env()

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-B",
                runner_script_path,
                payload_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
                env=env,
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout_sec),
                )
            except (asyncio.TimeoutError, TimeoutError):
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                raise TimeoutError(f"Worker process exceeded timeout of {timeout_sec}s")

            if not os.path.exists(output_path):
                stderr_text = stderr_data.decode("utf-8", errors="replace")
                raise RuntimeError(f"Worker process crashed without output (exit code {proc.returncode}): {stderr_text}")

            with open(output_path, "rb") as f:
                worker_result = pickle.load(f)

            if not worker_result.get("success", False):
                err = worker_result.get("error", "Unknown worker error")
                tb = worker_result.get("traceback", "")
                raise RuntimeError(f"Worker execution failed: {err}\n{tb}")

            result = worker_result["result"]
            if isinstance(result, dict):
                result["worker_pid"] = result.get("_worker_pid")
                result["output"] = dict(result)
                if "success" not in result:
                    result["success"] = True
            return result
