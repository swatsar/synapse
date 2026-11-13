"""HTTP controls for verified dataset snapshots and real training preflight/run."""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from synapse.experience import DatasetSnapshotStore, ExperienceStore
from synapse.growth import get_growth_network
from synapse.models import get_model_registry
from synapse.training import TrainingRunEvidence, check_training_preflight, train_lora
from synapse.training.adapters import (
    discover_promoted_adapter,
    list_adapters,
    pin_adapter,
    read_pin,
    unpin_adapter,
)
from synapse.training.jobs import TrainingJobs
from synapse.training.locking import TrainingLock
from synapse.training.trainer import _sha256_tree

router = APIRouter()
PROTOCOL_VERSION = "1.0"


def _workspace() -> Path:
    return Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).expanduser().resolve()


def _experience_store() -> ExperienceStore:
    return ExperienceStore(_workspace() / ".synapse" / "experience.sqlite3")


def _snapshots() -> DatasetSnapshotStore:
    return DatasetSnapshotStore(_workspace() / ".synapse" / "datasets")


class SnapshotRequest(BaseModel):
    seed: int = 0
    train_ratio: float = Field(default=0.8, gt=0, lt=1)
    dev_ratio: float = Field(default=0.1, ge=0, lt=1)


class TrainingRequest(BaseModel):
    model_id: str
    snapshot_id: str
    output_dir: str = ".synapse/adapters"
    steps: int = Field(default=1, ge=1, le=10000)
    max_length: int = Field(default=256, ge=32, le=4096)
    mode: str = Field(default="lora", pattern="^(lora|qlora)$")
    require_gpu: bool = True


def _resolve_model(model_id: str) -> str:
    manifest = get_model_registry().get(model_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Model manifest not found")
    if manifest.status != "downloaded" or not manifest.local_path:
        raise HTTPException(status_code=409, detail="Model is not downloaded")
    return manifest.local_path


def _active_model_path() -> str | None:
    try:
        manifests = [
            manifest for manifest in get_model_registry().list()
            if manifest.status == "downloaded" and manifest.local_path
        ]
    except Exception:
        return None
    return manifests[0].local_path if manifests else None


def _clear_adapter_cache() -> None:
    try:
        from synapse.llm.local_model import clear_local_provider_cache

        clear_local_provider_cache()
    except Exception:
        pass


@router.get("/snapshots")
async def list_snapshots() -> dict[str, Any]:
    return {"snapshots": _snapshots().list(), "protocol_version": PROTOCOL_VERSION}


@router.post("/snapshots")
async def create_snapshot(request: SnapshotRequest) -> dict[str, Any]:
    store = _experience_store()
    try:
        snapshot = _snapshots().create(
            store, seed=request.seed, train_ratio=request.train_ratio, dev_ratio=request.dev_ratio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        store.close()
    return {"snapshot": snapshot.to_dict(), "protocol_version": PROTOCOL_VERSION}


@router.post("/preflight")
async def training_preflight(request: TrainingRequest) -> dict[str, Any]:
    base_model = _resolve_model(request.model_id)
    try:
        snapshot = _snapshots().load(request.snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dataset snapshot not found") from exc
    result = check_training_preflight(snapshot=snapshot, base_model=base_model, require_gpu=request.require_gpu)
    return result.to_dict()


@router.post("/run")
async def run_training(request: TrainingRequest) -> dict[str, Any]:
    base_model = _resolve_model(request.model_id)
    try:
        snapshot = _snapshots().load(request.snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dataset snapshot not found") from exc
    lock = TrainingLock(_workspace() / ".synapse" / "training.lock")
    if not lock.acquire():
        # Return the same evidence contract as a rejected run instead of
        # queueing a second full training job behind the autonomous loop.
        base_path = Path(base_model)
        base_hash = (
            await asyncio.to_thread(_sha256_tree, base_path)
            if base_path.is_dir() else ""
        )
        blocked = TrainingRunEvidence(
            status="blocked",
            run_id=f"train_{uuid.uuid4().hex}",
            base_model=str(base_model),
            base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id,
            snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None,
            blockers=("training_running_in_another_process",),
            mode=request.mode,
        ).to_dict()
        return {"training": blocked, "protocol_version": PROTOCOL_VERSION}
    store = _experience_store()
    output_dir = _workspace() / request.output_dir
    try:
        result = await asyncio.to_thread(
            train_lora,
            experience_store=store,
            snapshot=snapshot,
            base_model=base_model,
            output_dir=output_dir,
            steps=request.steps,
            max_length=request.max_length,
            mode=request.mode,
            require_gpu=request.require_gpu,
        )
    finally:
        store.close()
        lock.release()
    evidence = result.to_dict()
    network = get_growth_network(_workspace())
    network.record_execution(
        task=f"train:{request.snapshot_id}",
        skill="training",
        provider="local_transformers",
        model=request.model_id,
        success=evidence.get("status") == "completed",
        error=evidence.get("error"),
    )
    if evidence.get("promotion_status") == "promoted":
        # Training is a consolidation event: sleep-like decay/prune runs after
        # a promoted adapter, so the network is not only additive.
        network.consolidate()
    return {"training": evidence, "protocol_version": PROTOCOL_VERSION}


# ----------------------------------------------------------------------
# Adapter history, pinning and rollback
# ----------------------------------------------------------------------
def _adapter_payload() -> dict[str, Any]:
    workspace = _workspace()
    model_path = _active_model_path()
    selected = discover_promoted_adapter(model_path, workspace) if model_path else None
    pinned = read_pin(workspace / ".synapse" / "adapters")
    return {
        "adapters": list_adapters(workspace, model_path=model_path),
        "selected": str(selected) if selected else None,
        "pinned": pinned,
        "model_path": model_path,
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/adapters")
async def adapters_history() -> dict[str, Any]:
    """Full adapter history with pin/selection state for rollback."""
    return _adapter_payload()


@router.post("/adapters/{name}/activate")
async def activate_adapter(name: str) -> dict[str, Any]:
    """Pin a promoted adapter; inference loads it on the next response."""
    try:
        payload = pin_adapter(_workspace(), name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _clear_adapter_cache()
    return _adapter_payload() | {"activation": payload}


@router.post("/adapters/auto")
async def activate_newest_adapter() -> dict[str, Any]:
    """Drop the pin and return to newest-promoted selection."""
    unpin_adapter(_workspace())
    _clear_adapter_cache()
    return _adapter_payload() | {"activation": {"pinned": None}}


# ----------------------------------------------------------------------
# Background training jobs: progress, status, cancellation
# ----------------------------------------------------------------------
def _blocked_evidence(
    *, base_model: str, snapshot: Any, mode: str,
) -> TrainingRunEvidence:
    base_path = Path(base_model)
    base_hash = _sha256_tree(base_path) if base_path.is_dir() else ""
    return TrainingRunEvidence(
        status="blocked",
        run_id=f"train_{uuid.uuid4().hex}",
        base_model=str(base_model),
        base_model_hash=base_hash,
        snapshot_id=snapshot.snapshot_id,
        snapshot_manifest_hash=snapshot.manifest_hash,
        adapter_path=None,
        blockers=("training_running_in_another_process",),
        mode=mode,
    )


@router.post("/runs", status_code=202)
async def start_training_job(request: TrainingRequest) -> dict[str, Any]:
    """Queue a real training run and return immediately with a job id."""
    base_model = _resolve_model(request.model_id)
    try:
        snapshot = _snapshots().load(request.snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dataset snapshot not found") from exc
    jobs = TrainingJobs(_workspace())
    for existing in jobs.list(limit=50):
        if existing.get("status") in {"queued", "running"}:
            raise HTTPException(
                status_code=409,
                detail="A training job is already queued or running",
            )
    from datetime import UTC, datetime

    adapter_dir = f"manual_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    output_dir = Path(request.output_dir) / adapter_dir
    metadata = {"origin": "api_job", "topic": f"manual training {request.snapshot_id}"}

    def runner(run_id: str, cancel_event, progress) -> dict[str, Any]:
        lock = TrainingLock(_workspace() / ".synapse" / "training.lock")
        if not lock.acquire():
            return {"training": _blocked_evidence(
                base_model=base_model, snapshot=snapshot, mode=request.mode,
            ).to_dict()}
        store = _experience_store()
        try:
            result = train_lora(
                experience_store=store,
                snapshot=snapshot,
                base_model=base_model,
                output_dir=_workspace() / output_dir,
                steps=request.steps,
                max_length=request.max_length,
                mode=request.mode,
                require_gpu=request.require_gpu,
                metadata=metadata | {"job_id": run_id},
                should_cancel=cancel_event.is_set,
                progress_callback=progress,
            )
        finally:
            store.close()
            lock.release()
        evidence = result.to_dict()
        network = get_growth_network(_workspace())
        network.record_execution(
            task=f"train_job:{request.snapshot_id}",
            skill="training",
            provider="local_transformers",
            model=request.model_id,
            success=evidence.get("status") == "completed",
            error=evidence.get("error"),
        )
        if evidence.get("promotion_status") == "promoted":
            network.consolidate()
        return {"training": evidence}

    job = jobs.submit(runner, request=request.model_dump())
    return {
        "job": job,
        "adapter_output_dir": str(output_dir),
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/runs")
async def list_training_jobs(limit: int = 20) -> dict[str, Any]:
    return {"jobs": TrainingJobs(_workspace()).list(limit=limit),
            "protocol_version": PROTOCOL_VERSION}


@router.get("/runs/{run_id}")
async def get_training_job(run_id: str) -> dict[str, Any]:
    job = TrainingJobs(_workspace()).get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return {"job": job, "protocol_version": PROTOCOL_VERSION}


@router.post("/runs/{run_id}/cancel")
async def cancel_training_job(run_id: str) -> dict[str, Any]:
    jobs = TrainingJobs(_workspace())
    job = jobs.get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    cancelled = jobs.cancel(run_id)
    return {
        "cancelled": cancelled,
        "job": jobs.get(run_id),
        "reason": None if cancelled else "job_unknown_or_terminal",
        "protocol_version": PROTOCOL_VERSION,
    }


__all__ = ["router"]
