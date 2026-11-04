"""Truthful preflight boundary for LoRA/QLoRA training.

This module intentionally does not emulate training. It reports whether the
local environment has the required runtime, model, dataset, and GPU evidence.
A caller must refuse training when any required condition is unavailable.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from synapse.experience import DatasetSnapshot


@dataclass(frozen=True)
class TrainingPreflight:
    ready: bool
    status: str
    blockers: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "status": self.status,
            "blockers": list(self.blockers),
            "evidence": self.evidence,
            "protocol_version": "1.0",
        }


def check_training_preflight(
    *,
    snapshot: DatasetSnapshot | None,
    base_model: str | Path | None,
    require_gpu: bool = True,
) -> TrainingPreflight:
    blockers: list[str] = []
    evidence: dict[str, Any] = {}
    required = ("torch", "transformers", "peft", "trl", "datasets")
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    evidence["missing_python_packages"] = missing
    if missing:
        blockers.append("missing_training_dependencies:" + ",".join(missing))

    if snapshot is None:
        blockers.append("verified_dataset_snapshot_required")
    else:
        evidence["snapshot_id"] = snapshot.snapshot_id
        evidence["snapshot_manifest_hash"] = snapshot.manifest_hash
        if not snapshot.holdout_ids:
            blockers.append("non_empty_holdout_required")

    if not base_model:
        blockers.append("frozen_open_weight_base_model_required")
    else:
        model_path = Path(base_model).expanduser()
        evidence["base_model"] = str(base_model)
        if not model_path.exists() or not model_path.is_dir():
            blockers.append("base_model_path_not_found")

    try:
        import torch  # type: ignore
        evidence["torch_version"] = torch.__version__
        evidence["cuda_available"] = bool(torch.cuda.is_available())
        if require_gpu and not torch.cuda.is_available():
            blockers.append("cuda_gpu_required")
    except ImportError:
        if require_gpu:
            blockers.append("torch_runtime_required_for_gpu_check")

    return TrainingPreflight(
        ready=not blockers,
        status="ready" if not blockers else "blocked",
        blockers=tuple(dict.fromkeys(blockers)),
        evidence=evidence,
    )


__all__ = ["TrainingPreflight", "check_training_preflight"]
