"""Read-only runtime settings and consistent SQLite backups."""
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

PROTOCOL_VERSION = "1.0"
router = APIRouter()


class SystemSettingsUpdate(BaseModel):
    log_level: str | None = None
    max_agents: int | None = Field(default=None, ge=1, le=1000)


class SecuritySettingsUpdate(BaseModel):
    require_approval_for_risk: int | None = Field(default=None, ge=1, le=5)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=100000)


class TelegramSettingsUpdate(BaseModel):
    enabled: bool | None = None
    token: str | None = None


class EnvVarCreate(BaseModel):
    key: str
    value: str


def _not_runtime_configurable() -> None:
    raise HTTPException(
        status_code=501,
        detail="Runtime configuration is read-only; set environment variables and restart the service",
    )


def _memory(request: Request):
    runtime = request.app.state.orchestrator
    memory = getattr(runtime, "memory_store", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="Memory runtime is not initialized")
    return memory


def _backup_directory() -> Path:
    configured = os.getenv("SYNAPSE_BACKUP_DIR")
    return Path(configured).expanduser().resolve() if configured else (
        Path.home() / ".synapse" / "backups"
    )


def _backup_path(backup_id: str) -> Path:
    if not backup_id.startswith("backup_") or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for character in backup_id
    ):
        raise HTTPException(status_code=404, detail="Backup not found")
    return _backup_directory() / f"{backup_id}.sqlite3"


@router.get("/system")
async def get_system_settings():
    return {
        "settings": {"log_level": logging.getLevelName(logging.getLogger().level)},
        "protocol_version": PROTOCOL_VERSION,
    }


@router.put("/system")
async def update_system_settings(data: SystemSettingsUpdate):
    _not_runtime_configurable()


@router.get("/security")
async def get_security_settings():
    return {
        "settings": {"require_approval_for_risk": 3, "rate_limit_per_minute": 60},
        "protocol_version": PROTOCOL_VERSION,
    }


@router.put("/security")
async def update_security_settings(data: SecuritySettingsUpdate):
    _not_runtime_configurable()


@router.get("/memory")
async def get_memory_settings(request: Request):
    memory = _memory(request)
    vector = getattr(memory, "vector_store", None)
    return {
        "settings": {
            "sql_db": "sqlite",
            "persistent": memory.db_path != ":memory:",
            "vector_db": "chromadb" if vector is not None else None,
            "semantic_retrieval": bool(getattr(vector, "_collection", None)),
        },
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/connectors")
async def get_connector_settings():
    return {
        "settings": {"telegram": {"enabled": False, "token_configured": False}},
        "protocol_version": PROTOCOL_VERSION,
    }


@router.put("/connectors/telegram")
async def update_telegram_settings(data: TelegramSettingsUpdate):
    _not_runtime_configurable()


@router.get("/env")
async def list_env_vars():
    # Never expose process environment or persisted secret values through HTTP.
    return {"variables": {}, "protocol_version": PROTOCOL_VERSION}


@router.post("/env")
async def set_env_var(data: EnvVarCreate):
    _not_runtime_configurable()


@router.delete("/env/{key}")
async def delete_env_var(key: str):
    _not_runtime_configurable()


@router.post("/backup")
async def create_backup(request: Request):
    backup_id = f"backup_{uuid.uuid4().hex}"
    target = _backup_path(backup_id)
    try:
        await _memory(request).create_backup(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}") from exc
    stat = target.stat()
    return {
        "backup_id": backup_id,
        "id": backup_id,
        "created_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "size_bytes": stat.st_size,
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/backups")
async def list_backups():
    directory = _backup_directory()
    records = []
    if directory.is_dir():
        for path in sorted(directory.glob("backup_*.sqlite3"), reverse=True):
            stat = path.stat()
            records.append({
                "backup_id": path.stem,
                "id": path.stem,
                "created_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "size_bytes": stat.st_size,
                "protocol_version": PROTOCOL_VERSION,
            })
    return {"backups": records, "protocol_version": PROTOCOL_VERSION}


@router.post("/restore/{backup_id}")
async def restore_backup(backup_id: str):
    if not _backup_path(backup_id).is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
    raise HTTPException(
        status_code=501,
        detail="Online restore is not implemented; stop the service and restore the SQLite file manually",
    )
