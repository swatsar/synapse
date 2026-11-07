"""Read-only workspace inventory skill."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from synapse.core.models import ExecutionContext


def _workspace(ctx: ExecutionContext, path: str) -> Path:
    root = None
    if ctx.memory_store is not None:
        root = getattr(ctx.memory_store, "workspace_root", None)
    candidate = Path(path or ".").expanduser()
    if root is not None and not candidate.is_absolute():
        candidate = Path(root) / candidate
    return candidate.resolve()


async def execute_workspace_audit(ctx: ExecutionContext, path: str = ".", read_only: bool = True, **_: Any) -> dict[str, Any]:
    """Inventory files and key project metadata without executing or modifying code."""
    if not any(value.startswith("fs:read") for value in ctx.capabilities):
        return {"success": False, "error": "Capability denied: fs:read"}
    target = _workspace(ctx, path)
    if not target.is_dir():
        return {"success": False, "error": f"Audit target is not a directory: {target}"}
    files: list[dict[str, Any]] = []
    directories: list[str] = []
    for item in sorted(target.rglob("*"), key=lambda value: str(value).lower()):
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"} for part in item.relative_to(target).parts):
            continue
        relative = str(item.relative_to(target)).replace("\\", "/")
        if item.is_dir():
            if len(directories) < 200:
                directories.append(relative)
        elif item.is_file() and len(files) < 500:
            try:
                files.append({"path": relative, "bytes": item.stat().st_size, "suffix": item.suffix})
            except OSError:
                continue
    key_files = []
    for name in ("README.md", "pyproject.toml", "requirements.txt", "package.json", "CLAUDE.md"):
        candidate = target / name
        if candidate.is_file():
            try:
                key_files.append({"path": name, "preview": candidate.read_text(encoding="utf-8", errors="replace")[:4000]})
            except OSError:
                pass
    summary = (
        f"Workspace audit (read-only): {target}\n"
        f"Directories: {len(directories)}; files: {len(files)}\n"
        f"Key metadata files: {', '.join(item['path'] for item in key_files) or 'none'}\n"
        f"Top-level entries: {', '.join(sorted(item.name for item in target.iterdir())[:80])}"
    )
    return {"success": True, "content": summary, "workspace": str(target), "read_only": read_only, "directories": directories, "files": files, "key_files": key_files}


__all__ = ["execute_workspace_audit"]
