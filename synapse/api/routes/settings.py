"""Settings API Routes.

Protocol Version: 1.0
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, Any, List
from datetime import datetime
import os

PROTOCOL_VERSION: str = "1.0"

router = APIRouter()

# In-memory storage
system_settings: Dict[str, Any] = {
    "log_level": "INFO",
    "max_agents": 10,
    "protocol_version": PROTOCOL_VERSION
}

security_settings: Dict[str, Any] = {
    "require_approval_for_risk": 3,
    "rate_limit_per_minute": 60,
    "protocol_version": PROTOCOL_VERSION
}

memory_settings: Dict[str, Any] = {
    "vector_db": "chromadb",
    "sql_db": "postgresql",
    "protocol_version": PROTOCOL_VERSION
}

connector_settings: Dict[str, Any] = {
    "telegram": {"enabled": False, "token": ""},
    "discord": {"enabled": False, "token": ""},
    "protocol_version": PROTOCOL_VERSION
}

env_vars: Dict[str, str] = {}
backups: List[Dict] = []


# === Models ===

class SystemSettingsUpdate(BaseModel):
    log_level: Optional[str] = None
    max_agents: Optional[int] = None


class SecuritySettingsUpdate(BaseModel):
    require_approval_for_risk: Optional[int] = None
    rate_limit_per_minute: Optional[int] = None


class TelegramSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    token: Optional[str] = None


class EnvVarCreate(BaseModel):
    key: str
    value: str


# === System Settings ===

@router.get("/system")
async def get_system_settings():
    """Get system settings."""
    return {"settings": system_settings, "protocol_version": PROTOCOL_VERSION}


@router.put("/system")
async def update_system_settings(data: SystemSettingsUpdate):
    """Update system settings."""
    update_data = data.model_dump(exclude_unset=True)
    system_settings.update(update_data)
    return {"settings": system_settings, "protocol_version": PROTOCOL_VERSION}


# === Security Settings ===

@router.get("/security")
async def get_security_settings():
    """Get security settings."""
    return {"settings": security_settings, "protocol_version": PROTOCOL_VERSION}


@router.put("/security")
async def update_security_settings(data: SecuritySettingsUpdate):
    """Update security settings."""
    update_data = data.model_dump(exclude_unset=True)
    security_settings.update(update_data)
    return {"settings": security_settings, "protocol_version": PROTOCOL_VERSION}


# === Memory Settings ===

@router.get("/memory")
async def get_memory_settings():
    """Get memory settings."""
    return {"settings": memory_settings, "protocol_version": PROTOCOL_VERSION}


# === Connector Settings ===

@router.get("/connectors")
async def get_connector_settings():
    """Get connector settings."""
    return {"settings": connector_settings, "protocol_version": PROTOCOL_VERSION}


@router.put("/connectors/telegram")
async def update_telegram_settings(data: TelegramSettingsUpdate):
    """Update Telegram settings."""
    update_data = data.model_dump(exclude_unset=True)
    connector_settings["telegram"].update(update_data)
    return {"settings": connector_settings["telegram"], "protocol_version": PROTOCOL_VERSION}


# === Environment Variables ===

@router.get("/env")
async def list_env_vars():
    """List environment variables."""
    return {"variables": env_vars, "protocol_version": PROTOCOL_VERSION}


@router.post("/env")
async def set_env_var(data: EnvVarCreate):
    """Set an environment variable."""
    env_vars[data.key] = data.value
    os.environ[data.key] = data.value
    return {"key": data.key, "value": "***", "protocol_version": PROTOCOL_VERSION}


@router.delete("/env/{key}", status_code=204)
async def delete_env_var(key: str):
    """Delete an environment variable."""
    if key in env_vars:
        del env_vars[key]
    if key in os.environ:
        del os.environ[key]


# === Backup/Restore ===

@router.post("/backup")
async def create_backup():
    """Create a backup."""
    backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    backup = {
        "backup_id": backup_id,
        "created_at": datetime.utcnow().isoformat(),
        "protocol_version": PROTOCOL_VERSION
    }
    backups.append(backup)
    return backup


@router.get("/backups")
async def list_backups():
    """List backups."""
    return {"backups": backups, "protocol_version": PROTOCOL_VERSION}


@router.post("/restore/{backup_id}")
async def restore_backup(backup_id: str):
    """Restore from backup."""
    backup = next((b for b in backups if b["id"] == backup_id), None)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"status": "restored", "backup_id": backup_id, "protocol_version": PROTOCOL_VERSION}
