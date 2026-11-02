"""Read-only views of the components embedded in the task runtime."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

PROTOCOL_VERSION = "1.0"
router = APIRouter()


class AgentConfigUpdate(BaseModel):
    max_retries: int | None = Field(default=None, ge=0, le=100)
    timeout: int | None = Field(default=None, gt=0, le=3600)


def _components(request: Request) -> dict[str, dict]:
    runtime = request.app.state.orchestrator
    components = {
        "planner": ("Planner Agent", getattr(runtime, "planner", None)),
        "critic": ("Critic Agent", getattr(runtime, "critic", None)),
        "developer": (
            "Developer Agent",
            getattr(getattr(runtime, "learning_engine", None), "developer", None),
        ),
        "guardian": ("Security Manager", getattr(runtime, "security_manager", None)),
    }
    return {
        component_id: {
            "id": component_id,
            "name": name,
            "type": component_id,
            "status": "embedded" if implementation is not None else "unavailable",
            "protocol_version": PROTOCOL_VERSION,
        }
        for component_id, (name, implementation) in components.items()
    }


def _get_component(request: Request, agent_id: str) -> dict:
    component = _components(request).get(agent_id)
    if component is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return component


@router.get("")
async def list_agents(request: Request):
    return {"agents": list(_components(request).values()), "protocol_version": PROTOCOL_VERSION}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, request: Request):
    return _get_component(request, agent_id)


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str, request: Request):
    return {
        "status": _get_component(request, agent_id)["status"],
        "protocol_version": PROTOCOL_VERSION,
    }


def _independent_lifecycle_not_supported() -> None:
    raise HTTPException(
        status_code=501,
        detail="Components run inside the shared runtime; independent start/stop is not implemented",
    )


@router.post("/{agent_id}/start")
async def start_agent(agent_id: str, request: Request):
    _get_component(request, agent_id)
    _independent_lifecycle_not_supported()


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str, request: Request):
    _get_component(request, agent_id)
    _independent_lifecycle_not_supported()


@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: str, request: Request):
    _get_component(request, agent_id)
    # Task-level logs are real; no separate per-component log store exists.
    return {"logs": [], "protocol_version": PROTOCOL_VERSION}


@router.get("/{agent_id}/config")
async def get_agent_config(agent_id: str, request: Request):
    _get_component(request, agent_id)
    return {"config": {}, "protocol_version": PROTOCOL_VERSION}


@router.put("/{agent_id}/config")
async def update_agent_config(agent_id: str, data: AgentConfigUpdate, request: Request):
    _get_component(request, agent_id)
    raise HTTPException(
        status_code=501,
        detail="Runtime component reconfiguration requires an application restart",
    )
