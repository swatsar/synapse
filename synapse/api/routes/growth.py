"""HTTP surface for the mycelial growth network.

The growth network is Synapse's persistent learning substrate: task → skill →
provider/model paths are strengthened by success, inhibited by failure and
decayed during consolidation. These endpoints expose it to the UI and to the
operator without mutating it on read.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from synapse.growth import get_autonomy_loop, get_growth_network

router = APIRouter()
PROTOCOL_VERSION = "1.0"


def _workspace() -> Path:
    return Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).expanduser().resolve()


def _network():
    return get_growth_network(_workspace())


def _autonomy():
    return get_autonomy_loop(_workspace(), growth_network=_network())


def _self_development() -> dict[str, Any]:
    """Evidence that training changed inference, not only files on disk."""
    from synapse.llm.local_model import adapter_status
    from synapse.models import get_model_registry

    manifests = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    if not manifests:
        return {
            "status": "no_local_model",
            "adapter_path": None,
            "applied": False,
            "protocol_version": PROTOCOL_VERSION,
        }
    manifest = manifests[0]
    status = adapter_status(manifest.local_path)
    status["base_model"] = manifest.model_id
    status["status"] = (
        "applied" if status.get("applied")
        else ("selected" if status.get("selected") else "none")
    )
    return status


@router.get("/teachers")
async def growth_teachers() -> dict[str, Any]:
    """Models that can teach the local model, including OpenCode models.

    OpenCode is the primary teacher runtime. The endpoint reports the real
    catalog and quota state, so the UI never offers a model that cannot answer.
    """
    from synapse.integrations.external_agents import detect_agents
    from synapse.integrations.opencode_bridge import (
        detect_models,
        quota_status,
    )
    from synapse.models import get_model_registry

    quota = quota_status()
    teachers: list[dict[str, Any]] = [{
        "id": "auto",
        "label": "Авто — лучший доступный учитель",
        "kind": "auto",
        "available": True,
    }]
    # Keep the OpenCode catalog visible even while the free quota is cooling
    # down. Hiding the models made the app look as if OpenCode teachers had
    # disappeared; the honest state is "listed, currently unavailable".
    opencode_models = detect_models()
    opencode_usable = not quota["exhausted"]
    for model in opencode_models:
        teachers.append({
            "id": model.model_id,
            "label": (
                f"OpenCode · {model.display_name}"
                if opencode_usable
                else f"OpenCode · {model.display_name} · лимит, локальный fallback"
            ),
            "kind": "opencode",
            "available": opencode_usable,
        })
    local_models = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    for manifest in local_models:
        teachers.append({
            "id": manifest.model_id,
            "label": f"Локальная · {manifest.model_id}",
            "kind": "local",
            "available": True,
        })
    external_agents = [
        agent for agent in detect_agents() if agent.available
    ]
    for agent in external_agents:
        teachers.append({
            "id": agent.agent_id,
            "label": f"Агент · {agent.display_name or agent.agent_id}",
            "kind": "external_agent",
            "available": True,
        })
    return {
        "teachers": teachers,
        "opencode": {
            "quota": quota,
            # `available_models` stays the usable count; `model_count` is the
            # full catalog so the UI can explain a quota cooldown without
            # pretending the runtime has no models.
            "available_models": len(opencode_models) if opencode_usable else 0,
            "model_count": len(opencode_models),
            "usable": opencode_usable,
        },
        "local_models": len(local_models),
        "external_agents": len(external_agents),
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/status")
async def growth_status() -> dict[str, Any]:
    """Nodes, edges, hubs, myelinated fast paths and weak paths."""
    payload = _network().status()
    payload["self_development"] = _self_development()
    payload["protocol_version"] = PROTOCOL_VERSION
    return payload


@router.get("/paths")
async def growth_paths(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Most recent/strongest learned paths."""
    return {
        "paths": _network().recent_paths(limit=limit),
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/suggest")
async def growth_suggest(
    task: str = Query(..., min_length=1, max_length=2000),
    limit: int = Query(default=5, ge=1, le=50),
) -> dict[str, Any]:
    """Mycelial recall: skills that succeeded on a similar task."""
    return {
        "task": task,
        "suggestions": _network().suggest_skill(task, limit=limit),
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/consolidate")
async def growth_consolidate() -> dict[str, Any]:
    """Run one sleep-like consolidation pass (decay, prune, summarise)."""
    summary = _network().consolidate()
    return {
        "consolidated": True,
        "summary": summary,
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/record")
async def growth_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Optional manual path recording for integrations outside the orchestrator."""
    task = str(payload.get("task") or "").strip()
    skill = str(payload.get("skill") or "").strip()
    if not task or not skill:
        return {
            "success": False,
            "error": "task and skill are required",
            "protocol_version": PROTOCOL_VERSION,
        }
    result = _network().record_execution(
        task=task,
        skill=skill,
        provider=payload.get("provider"),
        model=payload.get("model"),
        success=bool(payload.get("success", True)),
        error=payload.get("error"),
        latency_ms=payload.get("latency_ms"),
        session_id=payload.get("session_id"),
    )
    return {**result, "protocol_version": PROTOCOL_VERSION}


@router.get("/autonomy")
async def growth_autonomy() -> dict[str, Any]:
    """Autonomous maintenance state: consolidation rhythm and self-training."""
    return _autonomy().status()


@router.post("/autonomy/tick")
async def growth_autonomy_tick() -> dict[str, Any]:
    """Run one self-development cycle immediately (consolidate, maybe train)."""
    loop = _autonomy()
    cycle = await loop.tick()
    return {
        "cycle": cycle,
        "status": loop.status(),
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/autonomy/train")
async def growth_autonomy_train(
    force: bool = Query(default=False),
) -> dict[str, Any]:
    """Run one gated LoRA training attempt immediately.

    ``force`` bypasses only the cooldown; the verified-record threshold and the
    promotion gate still apply, so this cannot train on unverified data or keep
    a worse adapter.
    """
    loop = _autonomy()
    outcome = await loop.train_now(force=force)
    return {
        **outcome,
        "status": loop.status(),
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/autonomy/self-study")
async def growth_autonomy_self_study(
    max_records: int = Query(default=8, ge=1, le=64),
) -> dict[str, Any]:
    """Add grounded training experience from project documentation.

    Extracted facts are re-verified against the source file. This endpoint is
    the manual counterpart of the autonomous self-study step; it never calls a
    model and never creates unverified samples.
    """
    loop = _autonomy()
    result = await asyncio.to_thread(
        loop.self_study_now, max_records=max_records,
    )
    return {
        **result,
        "status": loop.status(),
        "protocol_version": PROTOCOL_VERSION,
    }


__all__ = ["router"]
