"""Agents API Routes.

Protocol Version: 1.0
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

PROTOCOL_VERSION: str = "1.0"

router = APIRouter()

# In-memory storage
agents_db: Dict[str, Dict] = {
    "planner": {
        "id": "planner",
        "name": "Planner Agent",
        "status": "idle",
        "type": "planner",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION
    },
    "critic": {
        "id": "critic",
        "name": "Critic Agent",
        "status": "idle",
        "type": "critic",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION
    },
    "developer": {
        "id": "developer",
        "name": "Developer Agent",
        "status": "idle",
        "type": "developer",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION
    },
    "guardian": {
        "id": "guardian",
        "name": "Guardian Agent",
        "status": "idle",
        "type": "guardian",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION
    }
}

agents_logs: Dict[str, List[Dict]] = {k: [] for k in agents_db}
agents_config: Dict[str, Dict] = {k: {"max_retries": 3, "timeout": 30} for k in agents_db}


# === Models ===

class AgentConfigUpdate(BaseModel):
    max_retries: Optional[int] = None
    timeout: Optional[int] = None


# === Routes ===

@router.get("")
async def list_agents():
    """List all agents."""
    return {
        "agents": list(agents_db.values()),
        "protocol_version": PROTOCOL_VERSION
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get a specific agent."""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agents_db[agent_id]


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str):
    """Get agent status."""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "status": agents_db[agent_id]["status"],
        "protocol_version": PROTOCOL_VERSION
    }


@router.post("/{agent_id}/start")
async def start_agent(agent_id: str):
    """Start an agent."""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    agents_db[agent_id]["status"] = "running"
    agents_db[agent_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    return agents_db[agent_id]


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str):
    """Stop an agent."""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    agents_db[agent_id]["status"] = "stopped"
    agents_db[agent_id]["stopped_at"] = datetime.now(timezone.utc).isoformat()
    return agents_db[agent_id]


@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 100):
    """Get agent logs."""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    logs = agents_logs.get(agent_id, [])
    return {
        "logs": logs[-limit:],
        "protocol_version": PROTOCOL_VERSION
    }


@router.get("/{agent_id}/config")
async def get_agent_config(agent_id: str):
    """Get agent configuration."""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "config": agents_config.get(agent_id, {}),
        "protocol_version": PROTOCOL_VERSION
    }


@router.put("/{agent_id}/config")
async def update_agent_config(agent_id: str, data: AgentConfigUpdate):
    """Update agent configuration."""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    config = agents_config.get(agent_id, {})
    update_data = data.model_dump(exclude_unset=True)
    config.update(update_data)
    agents_config[agent_id] = config
    return {
        "config": config,
        "protocol_version": PROTOCOL_VERSION
    }
