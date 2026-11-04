"""HTTP controls for verified dataset snapshots and real training preflight/run."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from synapse.experience import DatasetSnapshotStore, ExperienceStore
from synapse.models import get_model_registry
from synapse.training import check_training_preflight, train_lora

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
    return {"training": result.to_dict(), "protocol_version": PROTOCOL_VERSION}


__all__ = ["router"]
