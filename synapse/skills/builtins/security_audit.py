"""Read-only security audit skill backed by Synapse's static auditor."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from synapse.core.models import ExecutionContext
from synapse.security.audit_scanner import SecurityAuditor


async def execute_security_audit(ctx: ExecutionContext, target_dir: str = ".", **_: Any) -> dict[str, Any]:
    if not any(value.startswith("fs:read") for value in ctx.capabilities):
        return {"success": False, "error": "Capability denied: fs:read"}
    root = Path(getattr(ctx.memory_store, "workspace_root", Path.cwd())).resolve()
    target = Path(target_dir).expanduser()
    if not target.is_absolute():
        target = root / target
    try:
        report = SecurityAuditor(workspace_root=root).run_audit(target_dir=target)
    except (OSError, ValueError) as exc:
        return {"success": False, "error": str(exc)}
    return {
        "success": True,
        "content": f"Security audit: grade {report.grade}, score {report.score}/100, findings {report.total_findings}.",
        "report": report.to_dict(),
        "read_only": True,
    }


__all__ = ["execute_security_audit"]
