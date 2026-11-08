"""
OmniRouter API Routes for Synapse v3.4.1.

Exposes model catalog, automatic routing engine, provider health checks,
telemetry, and execution endpoints.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from synapse.api.routes.runtime_config import load_runtime_config_values
from synapse.llm.omnirouter import OmniRouter, RouteDecision, get_omnirouter

PROTOCOL_VERSION: str = "1.0"
router = APIRouter()


class RouteRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20_000, description="Task prompt or description to analyze")
    requirements: Optional[dict[str, Any]] = Field(default=None, description="Optional constraints (local_only, model, provider, latency)")
    protocol_version: str = PROTOCOL_VERSION


class ExecuteRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20_000, description="Task prompt or description")
    prompt: Optional[str] = Field(default=None, description="Specific prompt if different from task")
    requirements: Optional[dict[str, Any]] = Field(default=None, description="Routing constraints")
    parameters: Optional[dict[str, Any]] = Field(default=None, description="Model generation parameters (temperature, max_tokens, etc.)")
    protocol_version: str = PROTOCOL_VERSION


def _get_router(request: Request) -> OmniRouter:
    """Retrieve application OmniRouter instance or default singleton."""
    app_router = getattr(request.app.state, "omnirouter", None)
    router = app_router or get_omnirouter()
    router.apply_preferences(load_runtime_config_values())
    return router


@router.get("/catalog")
async def get_model_catalog(request: Request) -> dict[str, Any]:
    """Return all supported models with capabilities, context windows, and cost tiers."""
    r = _get_router(request)
    return {
        "catalog": r.get_catalog(),
        "total_models": len(r.catalog),
        "default_model": r.default_model,
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/health")
async def get_router_health(request: Request) -> dict[str, Any]:
    """Return provider readiness and availability status."""
    r = _get_router(request)
    return await r.health_check_async()


@router.get("/stats")
async def get_router_stats(request: Request) -> dict[str, Any]:
    """Return routing telemetry, domain distribution, and call counts."""
    r = _get_router(request)
    return r.get_stats()


@router.post("/route")
async def route_task(request: Request, body: RouteRequest) -> dict[str, Any]:
    """Analyze task requirements and compute the optimal model routing decision."""
    r = _get_router(request)
    decision = await r.route_async(body.task, body.requirements)
    return {
        "decision": decision.to_dict(),
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/execute")
async def execute_task(request: Request, body: ExecuteRequest) -> dict[str, Any]:
    """Route and execute completion through LiteLLM with automatic multi-tier fallback."""
    r = _get_router(request)
    params = body.parameters or {}
    result = await r.execute(
        task_description=body.task,
        prompt=body.prompt,
        requirements=body.requirements,
        **params,
    )
    return result
