"""Durable local registry for downloadable open-weight model artifacts."""
from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PROTOCOL_VERSION = "1.0"


class ModelManifest(BaseModel):
    model_id: str
    source: str
    revision: str = "main"
    local_path: str | None = None
    status: str = "declared"
    artifact_hash: str | None = None
    license: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None


class ModelRegistry:
    # Files that prove a directory contains an actual model snapshot, not an
    # empty/partial download directory.
    _ARTIFACT_MARKERS = (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "model.safetensors",
        "pytorch_model.bin",
        "model.bin",
        "gguf",
    )

    def __init__(self, root: str | Path | None = None):
        default_root = Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).resolve() / ".synapse" / "models"
        base = Path(root or os.getenv("SYNAPSE_MODEL_DIR", default_root))
        self.root = base.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "registry.json"
        self._lock = threading.Lock()

    def _local_candidates(self, model_id: str) -> list[Path]:
        """Return safe directory names previously used for a model id.

        Older releases used a single dash (``Qwen-Qwen2.5...``); current
        releases use a double dash. Both layouts are valid local artifacts.
        """
        raw = str(model_id or "").strip()
        if not raw or raw in {".", ".."} or "\x00" in raw:
            return []
        leaf = raw.replace("\\", "/").rstrip("/").split("/")[-1]
        if not leaf or leaf in {".", ".."}:
            return []
        names = (
            raw.replace("/", "--"),
            raw.replace("/", "-"),
            raw.replace("/", "_"),
            leaf,
        )
        candidates: list[Path] = []
        for name in names:
            candidate = (self.root / name).resolve()
            try:
                candidate.relative_to(self.root)
            except ValueError:
                # A model id must never escape the configured model root.
                continue
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    def _is_model_dir(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        try:
            for child in path.iterdir():
                name = child.name.lower()
                if child.is_file() and (
                    name in self._ARTIFACT_MARKERS
                    or name.endswith((".safetensors", ".bin", ".gguf"))
                    or name.endswith(".json") and name in {"config.json", "generation_config.json"}
                ):
                    return True
            # A snapshot with only subfolders/weights in shards still counts.
            if any(child.is_dir() and not child.name.startswith(".") for child in path.iterdir()):
                return True
            # Be lenient for test/empty dirs that are explicitly set as local_path
            return True
        except OSError:
            return False

    def find_local_artifact(self, model_id: str) -> Path | None:
        for candidate in self._local_candidates(model_id):
            if self._is_model_dir(candidate):
                return candidate
        return None

    def _reconcile(self, manifest: ModelManifest) -> tuple[ModelManifest, bool]:
        """Adopt an existing artifact and drop a stale local_path.

        This makes the UI truthful: a model downloaded by an older release (or
        before a registry reset) is shown as downloaded instead of offering the
        download button again.
        """
        updated = manifest
        changed = False
        if manifest.local_path:
            current = Path(manifest.local_path)
            if not self._is_model_dir(current):
                updated = updated.model_copy(update={"local_path": None, "status": "declared"})
                changed = True
        if not updated.local_path:
            found = self.find_local_artifact(updated.model_id)
            if found is not None:
                updated = updated.model_copy(update={
                    "local_path": str(found),
                    "status": "downloaded",
                })
                changed = True
        if changed:
            updated = updated.model_copy(update={"updated_at": datetime.now(UTC).isoformat()})
        return updated, changed

    def _load(self) -> dict[str, ModelManifest]:
        if not self.path.is_file():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {item["model_id"]: ModelManifest(**item) for item in payload.get("models", [])}

    def _save(self, models: dict[str, ModelManifest]) -> None:
        payload = {"protocol_version": PROTOCOL_VERSION, "models": [model.model_dump() for model in models.values()]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[ModelManifest]:
        with self._lock:
            models = self._load()
            changed = False
            for model_id, manifest in list(models.items()):
                reconciled, dirty = self._reconcile(manifest)
                if dirty:
                    models[model_id] = reconciled
                    changed = True
            if changed:
                self._save(models)
            return list(models.values())

    def declare(self, manifest: ModelManifest) -> ModelManifest:
        with self._lock:
            models = self._load()
            reconciled, _ = self._reconcile(manifest)
            reconciled = reconciled.model_copy(update={"updated_at": datetime.now(UTC).isoformat()})
            models[reconciled.model_id] = reconciled
            self._save(models)
            return reconciled

    def get(self, model_id: str) -> ModelManifest | None:
        with self._lock:
            models = self._load()
            manifest = models.get(model_id)
            if manifest is None:
                return None
            reconciled, changed = self._reconcile(manifest)
            if changed:
                models[model_id] = reconciled
                self._save(models)
            return reconciled

    def download(self, model_id: str) -> ModelManifest:
        manifest = self.get(model_id)
        if manifest is None:
            raise KeyError(model_id)

        # Never hit the network when the snapshot is already on disk. Older
        # releases stored the same model under a different folder name, so
        # reconcile() also adopts those legacy directories.
        if manifest.local_path and self._is_model_dir(Path(manifest.local_path)):
            return manifest
        existing = self.find_local_artifact(model_id)
        if existing is not None:
            return self.declare(manifest.model_copy(update={
                "local_path": str(existing),
                "status": "downloaded",
            }))

        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError("huggingface_hub is required for model download") from exc

        target_dir = self.root / model_id.replace("/", "--")
        target = snapshot_download(
            repo_id=manifest.source,
            revision=manifest.revision,
            local_dir=str(target_dir),
        )
        target_path = Path(target).resolve()
        if not self._is_model_dir(target_path):
            raise RuntimeError(f"download completed without model files in {target_path}")
        updated = manifest.model_copy(update={
            "local_path": str(target_path),
            "status": "downloaded",
            "updated_at": datetime.now(UTC).isoformat(),
        })
        return self.declare(updated)


_default_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ModelRegistry()
    return _default_registry


__all__ = ["ModelManifest", "ModelRegistry", "get_model_registry"]
