"""Deterministic, independent verification of task outcomes.

A successful executor receipt alone is not evidence that the work is correct.
Training eligibility therefore requires acceptance criteria supplied by the
caller (not invented by the executor) to pass against real artifacts or the
actual response text.

Supported criteria are intentionally small and auditable:

- ``file_exists:<workspace-relative path>``
- ``file_contains:<path>::<text>``
- ``file_not_contains:<path>::<text>``
- ``output_contains:<text>``
- ``output_not_contains:<text>``

Dict forms are accepted as ``{"type": "file_exists", "path": "..."}`` or
``{"type": "file_contains", "path": "...", "text": "..."}`` and equivalents.
Path criteria are always constrained to the workspace root.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"

_FILE_CHECKS = {"file_exists", "file_contains", "file_not_contains"}
_OUTPUT_CHECKS = {"output_contains", "output_not_contains"}


def _criteria(payload: dict[str, Any]) -> list[Any]:
    raw = payload.get("acceptance_criteria")
    if raw is None:
        raw = payload.get("verification")
    if raw is None:
        return []
    if isinstance(raw, (str, dict)):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _parse_text_criterion(text: str) -> tuple[str, str, str | None] | None:
    if ":" not in text:
        return None
    kind, rest = text.split(":", 1)
    kind = kind.strip()
    if kind in _FILE_CHECKS:
        if "::" in rest:
            path, needle = rest.split("::", 1)
            return kind, path.strip(), needle
        return kind, rest.strip(), None
    if kind in _OUTPUT_CHECKS:
        return kind, "", rest
    return None


def _resolve_in_workspace(workspace: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(workspace)
    except (OSError, ValueError):
        return None
    return resolved


def _output_text(result: dict[str, Any]) -> str:
    """Collect the human-visible answer from an orchestrator result."""
    pieces: list[str] = []

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 5:
            return
        if isinstance(value, str):
            pieces.append(value)
            return
        if isinstance(value, dict):
            for key in ("content", "message", "output", "text", "answer"):
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    pieces.append(item)
            for key in ("outputs", "steps", "result"):
                item = value.get(key)
                if isinstance(item, (list, dict)):
                    walk(item, depth + 1)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item, depth + 1)

    walk(result.get("action_result") or result)
    return "\n".join(pieces)


def model_outputs(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return executed steps that were actually produced by a language model.

    A route decision exists even for deterministic skills such as ``read_file``.
    Attributing a file's contents to that provider would create a false
    training sample, so only outputs carrying their own provider identity count
    as model-backed.
    """
    if not isinstance(result, dict):
        return []
    action = result.get("action_result")
    if not isinstance(action, dict):
        action = result
    outputs = action.get("outputs")
    if not isinstance(outputs, (list, tuple)):
        return []
    return [
        output for output in outputs
        if isinstance(output, dict) and output.get("provider")
    ]


def build_training_feedback(objective: str, result: dict[str, Any] | None) -> dict[str, Any]:
    """Build truthful provider attribution and training text for one task.

    Training is only possible when a model actually answered. The returned
    ``provider``/``model`` describe the executor output rather than the
    router's tentative decision, and ``training_text`` is present only for a
    non-empty model answer.
    """
    outputs = model_outputs(result)
    primary = next(
        (
            output for output in outputs
            if isinstance(output.get("content"), str) and output["content"].strip()
        ),
        None,
    )
    if primary is None:
        return {
            "model_backed": bool(outputs),
            "training_ready": False,
            "provider": outputs[0].get("provider") if outputs else None,
            "model": outputs[0].get("model") if outputs else None,
            "training_text": None,
        }
    content = primary["content"].strip()
    return {
        "model_backed": True,
        "training_ready": True,
        "provider": primary.get("provider"),
        "model": primary.get("model"),
        "training_text": f"User: {objective}\nAssistant: {content}",
    }


def verify_task_outcome(
    payload: dict[str, Any] | None,
    result: dict[str, Any] | None,
    *,
    workspace_root: str | Path,
) -> dict[str, Any]:
    """Check caller-supplied acceptance criteria against the real outcome."""
    payload = payload or {}
    result = result or {}
    workspace = Path(workspace_root).expanduser().resolve()
    criteria = _criteria(payload)
    if not criteria:
        return {
            "passed": None,
            "status": "no_criteria",
            "eligibility": "ineligible",
            "checks": [],
            "reason": "no independent acceptance criteria were supplied",
            "protocol_version": PROTOCOL_VERSION,
        }

    output = _output_text(result)
    checks: list[dict[str, Any]] = []
    for criterion in criteria:
        if isinstance(criterion, dict):
            kind = str(criterion.get("type") or criterion.get("check") or "").strip()
            raw_path = str(criterion.get("path") or "").strip()
            needle = criterion.get("text")
            needle = str(needle) if needle is not None else None
        elif isinstance(criterion, str):
            parsed = _parse_text_criterion(criterion)
            if parsed is None:
                checks.append({
                    "criterion": criterion,
                    "passed": False,
                    "reason": "unsupported_criterion",
                })
                continue
            kind, raw_path, needle = parsed
        else:
            checks.append({
                "criterion": str(criterion),
                "passed": False,
                "reason": "unsupported_criterion",
            })
            continue

        if kind in _FILE_CHECKS:
            if not raw_path:
                checks.append({
                    "criterion": kind,
                    "passed": False,
                    "reason": "missing_path",
                })
                continue
            path = _resolve_in_workspace(workspace, raw_path)
            if path is None:
                checks.append({
                    "criterion": f"{kind}:{raw_path}",
                    "passed": False,
                    "reason": "path_outside_workspace",
                })
                continue
            if kind == "file_exists":
                passed = path.is_file()
                checks.append({
                    "criterion": f"file_exists:{raw_path}",
                    "passed": passed,
                    "reason": None if passed else "file_not_found",
                })
                continue
            if not path.is_file():
                checks.append({
                    "criterion": f"{kind}:{raw_path}",
                    "passed": False,
                    "reason": "file_not_found",
                })
                continue
            if needle is None:
                checks.append({
                    "criterion": f"{kind}:{raw_path}",
                    "passed": False,
                    "reason": "missing_text",
                })
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                checks.append({
                    "criterion": f"{kind}:{raw_path}",
                    "passed": False,
                    "reason": "file_unreadable",
                })
                continue
            found = needle in content
            passed = found if kind == "file_contains" else not found
            checks.append({
                "criterion": f"{kind}:{raw_path}",
                "passed": passed,
                "reason": None if passed else (
                    "text_not_found" if kind == "file_contains" else "unexpected_text_found"
                ),
            })
            continue

        if kind in _OUTPUT_CHECKS:
            if needle is None:
                checks.append({
                    "criterion": kind,
                    "passed": False,
                    "reason": "missing_text",
                })
                continue
            found = needle in output
            passed = found if kind == "output_contains" else not found
            checks.append({
                "criterion": f"{kind}:{needle[:120]}",
                "passed": passed,
                "reason": None if passed else (
                    "text_not_found" if kind == "output_contains" else "unexpected_text_found"
                ),
            })
            continue

        checks.append({
            "criterion": str(criterion),
            "passed": False,
            "reason": "unsupported_criterion",
        })

    passed = bool(checks) and all(check["passed"] for check in checks)
    return {
        "passed": passed,
        "status": "passed" if passed else "failed",
        "eligibility": "eligible" if passed else "ineligible",
        "checks": checks,
        "criteria_count": len(criteria),
        "protocol_version": PROTOCOL_VERSION,
    }


__all__ = [
    "build_training_feedback",
    "model_outputs",
    "verify_task_outcome",
    "PROTOCOL_VERSION",
]
