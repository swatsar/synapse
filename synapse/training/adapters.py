"""Adapter history, explicit pinning and rollback.

The training pipeline writes ``.synapse/adapters/<run>/`` directories with a
``training_manifest.json``. Until now inference always selected the newest
promoted adapter by directory mtime, so a newly promoted adapter that regressed
in real use could not be rolled back without deleting files.

This module adds one small piece of state: ``<adapters>/active.json`` holding the
operator's explicit choice. A valid pin wins over mtime; an invalid pin (deleted
directory, rejected manifest, different base model) falls back to the newest
promoted adapter so a stale pointer can never disable self-development.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PIN_FILE = "active.json"
PIN_SCHEMA_VERSION = "1.0"


def adapter_roots(
    model_path: str | Path,
    workspace_root: str | Path | None = None,
) -> list[Path]:
    """Return adapter directories that may belong to ``model_path``."""
    roots: list[Path] = []
    if workspace_root:
        roots.append(Path(workspace_root).expanduser().resolve() / ".synapse" / "adapters")
    # model_path is normally <workspace>/.synapse/models/<checkpoint>.
    model = Path(model_path).expanduser().resolve()
    roots.append(model.parent.parent / "adapters")
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _same_model_path(left: str | Path, right: str | Path) -> bool:
    try:
        return (
            str(Path(left).expanduser().resolve()).casefold()
            == str(Path(right).expanduser().resolve()).casefold()
        )
    except (OSError, ValueError):
        return str(left).casefold() == str(right).casefold()


def read_pin(root: str | Path) -> str | None:
    """Read the pinned adapter name from one adapter root."""
    path = Path(root) / PIN_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    name = str(payload.get("pinned") or "").strip()
    return name or None


def read_pin_payload(root: str | Path) -> dict[str, Any] | None:
    try:
        payload = json.loads((Path(root) / PIN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def adapter_manifest(adapter: str | Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(
            (Path(adapter) / "training_manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _eligible(
    candidate: Path,
    model: Path | None,
) -> bool:
    """An adapter must exist, load, and be promoted for its base model."""
    if not candidate.is_dir():
        return False
    if not (candidate / "adapter_config.json").is_file():
        return False
    manifest = adapter_manifest(candidate)
    if manifest is not None:
        if manifest.get("promotion_status") != "promoted":
            return False
        base_model = manifest.get("base_model")
        if model is not None and base_model and not _same_model_path(base_model, model):
            return False
        return True
    # Manually imported adapters have no manifest; validate the config instead.
    try:
        config = json.loads(
            (candidate / "adapter_config.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return False
    base_model = config.get("base_model_name_or_path")
    if model is not None and base_model and not _same_model_path(base_model, model):
        return False
    return True


def pinned_adapter(
    model_path: str | Path,
    workspace_root: str | Path | None = None,
) -> Path | None:
    """Return the explicitly pinned adapter, or ``None`` when absent/invalid."""
    model = Path(model_path).expanduser().resolve()
    for root in adapter_roots(model, workspace_root):
        name = read_pin(root)
        if not name:
            continue
        candidate = root / name
        if _eligible(candidate, model):
            return candidate.resolve()
    return None


def discover_promoted_adapter(
    model_path: str | Path,
    workspace_root: str | Path | None = None,
) -> Path | None:
    """Return the pinned adapter, else the newest promoted adapter for the model."""
    model = Path(model_path).expanduser().resolve()
    roots = adapter_roots(model, workspace_root)
    eligible: list[tuple[float, Path]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for candidate in root.iterdir():
            if not candidate.is_dir() or candidate.name == PIN_FILE:
                continue
            key = str(candidate.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            if not _eligible(candidate, model):
                continue
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                continue
            eligible.append((mtime, candidate.resolve()))
    if not eligible:
        return None
    pinned = pinned_adapter(model, workspace_root)
    if pinned is not None:
        return pinned
    return max(eligible, key=lambda item: item[0])[1]


def _write_pin(root: Path, payload: dict[str, Any] | None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / PIN_FILE
    if payload is None:
        path.unlink(missing_ok=True)
        return
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def pin_adapter(workspace_root: str | Path, name: str) -> dict[str, Any]:
    """Pin ``name`` as the adapter inference must load.

    Raises ``ValueError`` for an unknown or non-promoted adapter and
    ``FileNotFoundError`` when the adapters directory does not exist.
    """
    workspace = Path(workspace_root).expanduser().resolve()
    root = workspace / ".synapse" / "adapters"
    if not root.is_dir():
        raise FileNotFoundError(f"adapters directory not found: {root}")
    name = str(name or "").strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("invalid adapter name")
    candidate = root / name
    manifest = adapter_manifest(candidate)
    if not candidate.is_dir() or not (candidate / "adapter_config.json").is_file():
        raise FileNotFoundError(f"adapter not found: {name}")
    if manifest is None or manifest.get("promotion_status") != "promoted":
        raise ValueError("only a promoted adapter can be pinned")
    payload = {
        "schema_version": PIN_SCHEMA_VERSION,
        "pinned": name,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _write_pin(root, payload)
    return payload


def unpin_adapter(workspace_root: str | Path) -> dict[str, Any]:
    """Remove the explicit pin; selection returns to newest-promoted."""
    root = Path(workspace_root).expanduser().resolve() / ".synapse" / "adapters"
    _write_pin(root, None)
    return {"pinned": None, "updated_at": datetime.now(UTC).isoformat()}


def list_adapters(
    workspace_root: str | Path,
    *,
    model_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return adapter history, newest first, with pin/selection state."""
    workspace = Path(workspace_root).expanduser().resolve()
    root = workspace / ".synapse" / "adapters"
    pin_payload = read_pin_payload(root) or {}
    pinned_name = str(pin_payload.get("pinned") or "") or None
    selected = (
        discover_promoted_adapter(model_path, workspace)
        if model_path is not None
        else None
    )

    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue
        manifest = adapter_manifest(candidate) or {}
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            mtime = 0.0
        created_at = manifest.get("created_at") or datetime.fromtimestamp(
            mtime, tz=UTC
        ).isoformat()
        resolved = candidate.resolve()
        rows.append(
            {
                "name": candidate.name,
                "path": str(resolved),
                "created_at": created_at,
                "promotion_status": manifest.get("promotion_status", "unknown"),
                "mode": manifest.get("mode", "unknown"),
                "steps": manifest.get("steps"),
                "records": manifest.get("records"),
                "holdout_loss_before": manifest.get("holdout_loss_before"),
                "holdout_loss_after": manifest.get("holdout_loss_after"),
                "promotion_gate": manifest.get("promotion_gate"),
                "topic": manifest.get("topic"),
                "teacher": manifest.get("teacher"),
                "duration_seconds": manifest.get("duration_seconds"),
                "pinned": candidate.name == pinned_name,
                "selected": selected is not None and resolved == selected,
            }
        )
    rows.sort(key=lambda row: (row["created_at"] or ""), reverse=True)
    return rows


__all__ = [
    "PIN_FILE",
    "adapter_manifest",
    "adapter_roots",
    "discover_promoted_adapter",
    "list_adapters",
    "pin_adapter",
    "pinned_adapter",
    "read_pin",
    "read_pin_payload",
    "unpin_adapter",
]
