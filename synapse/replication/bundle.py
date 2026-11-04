"""Portable, hash-verified agent state bundles.

A bundle is a filesystem artifact, not a network replication protocol. It is
safe to export/import locally and can later be transported through a governed
peer channel. Secrets and raw provider credentials are deliberately excluded.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"


class ReplicaBundleError(RuntimeError):
    """Raised when a bundle is malformed, unsafe, or fails integrity checks."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_root() -> Path:
    return Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).expanduser().resolve()


def _relative_safe(path: Path, root: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ReplicaBundleError(f"path escapes workspace: {path}")
    return str(resolved.relative_to(root)).replace("\\", "/")


def _collect_files(root: Path) -> list[tuple[Path, str]]:
    """Collect portable state while excluding caches, secrets, and runtime locks."""
    candidates = [
        root / ".synapse" / "memory.sqlite3",
        root / ".synapse" / "workspace.sqlite3",
        root / ".synapse" / "work.sqlite3",
        root / ".synapse" / "experience.sqlite3",
        root / ".synapse" / "config.sqlite3",
        root / ".synapse" / "memory_vault.json",
        root / ".synapse" / "trajectories",
        root / ".synapse" / "datasets",
        root / ".synapse" / "models",
        root / ".synapse" / "adapters",
        root / "synapse" / "skills",
        root / "synapse" / "plugins",
    ]
    found: list[tuple[Path, str]] = []
    for candidate in candidates:
        if candidate.is_file():
            found.append((candidate, _relative_safe(candidate, root)))
        elif candidate.is_dir():
            for item in candidate.rglob("*"):
                if not item.is_file() or any(part in {"__pycache__", ".git"} for part in item.parts):
                    continue
                rel = _relative_safe(item, root)
                if any(token in item.name.lower() for token in ("secret", "credential", ".env")):
                    continue
                found.append((item, rel))
    return sorted(found, key=lambda item: item[1])


def export_bundle(destination: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    workspace = Path(root or _workspace_root()).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = _collect_files(workspace)
    entries = [{"path": rel, "sha256": _sha256(path), "size": path.stat().st_size} for path, rel in files]
    manifest = {
        "schema_version": "1.0",
        "protocol_version": PROTOCOL_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "source_workspace": str(workspace),
        "files": entries,
        "secrets_excluded": True,
    }
    with tempfile.TemporaryDirectory(prefix="synapse_replica_") as staging:
        staging_path = Path(staging)
        for path, rel in files:
            target = staging_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        (staging_path / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging_path.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging_path).as_posix())
    manifest["bundle_sha256"] = _sha256(destination)
    return manifest


def verify_bundle(bundle: str | Path) -> dict[str, Any]:
    bundle = Path(bundle).expanduser().resolve()
    if not bundle.is_file():
        raise ReplicaBundleError("bundle not found")
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names:
            raise ReplicaBundleError("manifest.json is missing")
        manifest = json.loads(archive.read("manifest.json"))
        for entry in manifest.get("files", []):
            rel = entry["path"]
            if rel.startswith("/") or ".." in Path(rel).parts or rel not in names:
                raise ReplicaBundleError(f"unsafe or missing bundle path: {rel}")
            with archive.open(rel) as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            if digest != entry["sha256"]:
                raise ReplicaBundleError(f"hash mismatch: {rel}")
    return {"valid": True, "bundle": str(bundle), "manifest": manifest, "bundle_sha256": _sha256(bundle)}


def import_bundle(bundle: str | Path, *, root: str | Path | None = None, overwrite: bool = False) -> dict[str, Any]:
    verification = verify_bundle(bundle)
    workspace = Path(root or _workspace_root()).expanduser().resolve()
    with zipfile.ZipFile(Path(bundle).expanduser().resolve()) as archive:
        imported: list[str] = []
        for entry in verification["manifest"].get("files", []):
            rel = entry["path"]
            target = workspace / rel
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(rel) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            imported.append(rel)
    return {"valid": True, "imported": imported, "skipped_existing": len(verification["manifest"].get("files", [])) - len(imported), "manifest": verification["manifest"]}


__all__ = ["ReplicaBundleError", "export_bundle", "verify_bundle", "import_bundle"]
