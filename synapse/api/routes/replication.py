from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from synapse.replication import ReplicaBundleError, export_bundle, import_bundle, verify_bundle

router = APIRouter()


class BundleImportRequest(BaseModel):
    path: str
    overwrite: bool = False


def _bundle_dir() -> Path:
    path = Path(os.getenv("SYNAPSE_REPLICA_DIR", Path.home() / ".synapse" / "replicas"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.get("/status")
async def replication_status() -> dict[str, Any]:
    return {
        "status": "portable_bundle",
        "description": "Экспорт и проверка переносимого snapshot bundle; live peer sync ещё не включён.",
        "directory": str(_bundle_dir()),
        "protocol_version": "1.0",
    }


@router.get("/bundles")
async def list_bundles() -> dict[str, Any]:
    bundles = []
    for path in sorted(_bundle_dir().glob("*.zip"), key=lambda item: item.stat().st_mtime, reverse=True):
        bundles.append({"name": path.name, "path": str(path), "size_bytes": path.stat().st_size})
    return {"bundles": bundles, "protocol_version": "1.0"}


@router.post("/export")
async def export_replica() -> dict[str, Any]:
    target = _bundle_dir() / f"replica_{__import__('uuid').uuid4().hex}.zip"
    return {"bundle": export_bundle(target), "path": str(target), "protocol_version": "1.0"}


@router.post("/verify")
async def verify_replica(path: str) -> dict[str, Any]:
    try:
        return {"verification": verify_bundle(path), "protocol_version": "1.0"}
    except ReplicaBundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import")
async def import_replica(request: BundleImportRequest) -> dict[str, Any]:
    try:
        return {"result": import_bundle(request.path, overwrite=request.overwrite), "protocol_version": "1.0"}
    except ReplicaBundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = ["router"]
