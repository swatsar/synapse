"""Server-side runtime configuration and open-weight model registry API."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from synapse.models import ModelManifest, get_model_registry

PROTOCOL_VERSION = "1.0"
router = APIRouter()


class RuntimeConfigUpdate(BaseModel):
    model_tier: str | None = Field(default=None, pattern="^(balanced|frontier|local|fast)$")
    latency_budget_ms: int | None = Field(default=None, ge=1000, le=120000)
    success_threshold: int | None = Field(default=None, ge=50, le=99)
    failure_trigger: int | None = Field(default=None, ge=1, le=10)
    export_format: str | None = Field(default=None, pattern="^(chatml|alpaca)$")
    sliding_window_days: int | None = Field(default=None, ge=1, le=30)
    # OmniRouter & Computer-Use preferences (persisted, consumed by the router/browser)
    fallback_order: str | None = Field(default=None, max_length=500)
    domain_autoselect: bool | None = None
    allowed_domains: str | None = Field(default=None, max_length=2000)
    approval_risk_level: int | None = Field(default=None, ge=1, le=5)
    sandbox_isolation: str | None = Field(default=None, max_length=200)


def _path() -> Path:
    configured = os.getenv("SYNAPSE_CONFIG_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).resolve() / ".synapse" / "config.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runtime_config (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, values_json TEXT NOT NULL)")
    if db.execute("SELECT 1 FROM runtime_config WHERE id=1").fetchone() is None:
        db.execute("INSERT INTO runtime_config VALUES (1, 0, ?)", (json.dumps({}),))
        db.commit()
    return db


def load_runtime_config_values() -> dict[str, Any]:
    """Read persisted runtime-config values for consumers (router, browser, approvals)."""
    try:
        db = _connect()
        try:
            row = db.execute("SELECT values_json FROM runtime_config WHERE id=1").fetchone()
            return json.loads(row["values_json"]) if row else {}
        finally:
            db.close()
    except Exception:  # pragma: no cover - best effort for read paths
        return {}


@router.get("")
async def get_runtime_config() -> dict[str, Any]:
    db = _connect()
    try:
        row = db.execute("SELECT revision, values_json FROM runtime_config WHERE id=1").fetchone()
        return {"revision": row["revision"], "values": json.loads(row["values_json"]), "restart_required": False, "protocol_version": PROTOCOL_VERSION}
    finally:
        db.close()


@router.put("")
async def update_runtime_config(data: RuntimeConfigUpdate) -> dict[str, Any]:
    values = {key: value for key, value in data.model_dump().items() if value is not None}
    db = _connect()
    try:
        row = db.execute("SELECT revision, values_json FROM runtime_config WHERE id=1").fetchone()
        current = json.loads(row["values_json"])
        current.update(values)
        revision = int(row["revision"]) + 1
        db.execute("UPDATE runtime_config SET revision=?, values_json=? WHERE id=1", (revision, json.dumps(current, sort_keys=True)))
        db.commit()
        return {"revision": revision, "values": current, "saved": True, "applied": True, "restart_required": False, "protocol_version": PROTOCOL_VERSION}
    finally:
        db.close()


class ModelDeclareRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=300)
    revision: str = Field(default="main", min_length=1, max_length=200)
    license: str | None = None


@router.get("/models")
async def list_models() -> dict[str, Any]:
    models = get_model_registry().list()
    return {"models": [model.model_dump() for model in models], "protocol_version": PROTOCOL_VERSION}


@router.post("/models")
async def declare_model(data: ModelDeclareRequest) -> dict[str, Any]:
    manifest = get_model_registry().declare(ModelManifest(**data.model_dump()))
    return {"model": manifest.model_dump(), "protocol_version": PROTOCOL_VERSION}


@router.post("/models/{model_id}/download")
async def download_model(model_id: str) -> dict[str, Any]:
    try:
        manifest = get_model_registry().download(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Model is not declared") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Model download unavailable: {exc}") from exc
    return {"model": manifest.model_dump(), "protocol_version": PROTOCOL_VERSION}
