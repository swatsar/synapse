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
    def __init__(self, root: str | Path | None = None):
        default_root = Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).resolve() / ".synapse" / "models"
        base = Path(root or os.getenv("SYNAPSE_MODEL_DIR", default_root))
        self.root = base.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "registry.json"
        self._lock = threading.Lock()

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
            return list(self._load().values())

    def declare(self, manifest: ModelManifest) -> ModelManifest:
        with self._lock:
            models = self._load()
            models[manifest.model_id] = manifest.model_copy(update={"updated_at": datetime.now(UTC).isoformat()})
            self._save(models)
            return models[manifest.model_id]

    def get(self, model_id: str) -> ModelManifest | None:
        with self._lock:
            return self._load().get(model_id)

    def download(self, model_id: str) -> ModelManifest:
        manifest = self.get(model_id)
        if manifest is None:
            raise KeyError(model_id)
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError("huggingface_hub is required for model download") from exc
        target = snapshot_download(
            repo_id=manifest.source,
            revision=manifest.revision,
            local_dir=str(self.root / model_id.replace("/", "--")),
        )
        updated = manifest.model_copy(update={
            "local_path": str(Path(target).resolve()),
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
