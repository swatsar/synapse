"""
Platform Tools & Integrations API Routes for Synapse v3.4.1.

Exposes REST endpoints for:
- Cloudflare Security Audit Scanner
- Claude-Mem Durable Memory Vault
- Matt Pocock Composable Skills Library
- Nutlope Hallmark Benchmark Harness
- DeepSeek Trajectory Recorder
- Claude Code Slash Command Engine
- OpenAI Codex Multi-File Patch Applicator

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from synapse.security.audit_scanner import get_security_auditor
from synapse.memory.vault import get_memory_vault, MemoryType
from synapse.skills.library import get_skill_library
from synapse.harnesses.hallmark import get_hallmark_harness
from synapse.harnesses.trajectory import get_trajectory_harness
from synapse.interfaces.slash_engine import get_slash_engine
from synapse.integrations.codex_engine import get_codex_engine, FilePatch

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.api.routes.tools_platform")

router = APIRouter()


# -------------------------------------------------------------
# 1. Cloudflare Security Audit Scanner Endpoints
# -------------------------------------------------------------
class AuditScanRequest(BaseModel):
    target_dir: str = Field(default=".", description="Target directory relative to workspace root")


@router.post("/security/audit")
async def run_security_audit(request: AuditScanRequest) -> dict[str, Any]:
    """Run security audit scan over the workspace."""
    try:
        auditor = get_security_auditor()
        report = auditor.run_audit(request.target_dir)
        return report.to_dict()
    except Exception as e:
        logger.error("Security audit failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------------
# 2. Claude-Mem Durable Memory Vault Endpoints
# -------------------------------------------------------------
class MemoryCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    memory_type: str = Field(default="project")
    tags: list[str] = Field(default_factory=list)


@router.get("/memory/entries")
async def list_memories(
    q: Optional[str] = Query(default=None, description="Search query"),
    memory_type: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    """List or search long-term memories."""
    vault = get_memory_vault()
    if q:
        entries = vault.search(q, limit=20)
    else:
        mtype = MemoryType(memory_type) if memory_type else None
        entries = vault.list_entries(mtype)
    return {
        "count": len(entries),
        "entries": [e.to_dict() for e in entries],
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/memory/entries")
async def create_memory(request: MemoryCreateRequest) -> dict[str, Any]:
    """Create a new persistent memory note."""
    vault = get_memory_vault()
    try:
        mtype = MemoryType(request.memory_type)
    except ValueError:
        mtype = MemoryType.PROJECT

    entry = vault.create_entry(
        title=request.title,
        content=request.content,
        memory_type=mtype,
        tags=request.tags,
    )
    return {"created": entry.to_dict(), "protocol_version": PROTOCOL_VERSION}


@router.delete("/memory/entries/{entry_id}")
async def delete_memory(entry_id: str) -> dict[str, Any]:
    """Delete a memory note by ID."""
    vault = get_memory_vault()
    success = vault.delete_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory note not found")
    return {"deleted": True, "id": entry_id, "protocol_version": PROTOCOL_VERSION}


# -------------------------------------------------------------
# 3. Matt Pocock Composable Skills Library Endpoints
# -------------------------------------------------------------
class SkillExecuteRequest(BaseModel):
    skill_id: str
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/skills")
@router.get("/skills/catalog")
async def list_skills() -> dict[str, Any]:
    """List all registered composable skills."""
    lib = get_skill_library()
    skills = lib.list_skills()
    return {
        "count": len(skills),
        "skills": [s.to_dict() for s in skills],
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/skills/execute")
async def execute_skill(request: SkillExecuteRequest) -> dict[str, Any]:
    """Execute a specific skill with parameters."""
    lib = get_skill_library()
    skill = lib.get(request.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{request.skill_id}' not found")
    try:
        return await skill.execute(request.params)
    except Exception as e:
        logger.error("Skill execution error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/skills/{skill_id}/execute")
async def execute_skill_by_id(skill_id: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Execute a specific skill by skill_id path parameter."""
    lib = get_skill_library()
    skill = lib.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    try:
        return await skill.execute(payload or {})
    except Exception as e:
        logger.error("Skill execution error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# 4. Nutlope Hallmark Benchmark Harness Endpoints
# -------------------------------------------------------------
class BenchmarkRunRequest(BaseModel):
    suite_id: str = Field(default="core_eval_v1")


@router.get("/benchmarks/history")
async def list_benchmark_history() -> dict[str, Any]:
    """List historical benchmark runs."""
    harness = get_hallmark_harness()
    runs = harness.list_historical_runs()
    return {"count": len(runs), "runs": runs, "protocol_version": PROTOCOL_VERSION}


@router.post("/benchmarks/run")
async def run_benchmark_suite(request: BenchmarkRunRequest) -> dict[str, Any]:
    """Run benchmark evaluation suite."""
    harness = get_hallmark_harness()
    report = await harness.run_benchmark(suite_id=request.suite_id)
    return report.to_dict()


# -------------------------------------------------------------
# 5. DeepSeek Trajectory Recorder Endpoints
# -------------------------------------------------------------
@router.get("/trajectories")
async def list_trajectories(limit: int = 50) -> dict[str, Any]:
    """List agent execution trajectories."""
    harness = get_trajectory_harness()
    trajectories = harness.list_trajectories(limit=limit)
    return {
        "count": len(trajectories),
        "trajectories": trajectories,
        "protocol_version": PROTOCOL_VERSION,
    }


# -------------------------------------------------------------
# 6. Claude Code Interactive Slash Commands
# -------------------------------------------------------------
class SlashCommandRequest(BaseModel):
    command: str = Field(description="Command string, e.g. /audit or /model 'test'")


@router.get("/slash/commands")
async def list_slash_commands() -> dict[str, Any]:
    """List available slash commands and usage metadata."""
    engine = get_slash_engine()
    cmds = engine.list_commands()
    return {
        "count": len(cmds),
        "commands": [c.to_dict() for c in cmds],
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/slash/execute")
async def execute_slash_command(request: SlashCommandRequest) -> dict[str, Any]:
    """Execute a slash command string."""
    engine = get_slash_engine()
    if not engine.is_slash_command(request.command):
        raise HTTPException(status_code=400, detail="Command must start with '/'")
    res = await engine.execute(request.command)
    return res.to_dict()


# -------------------------------------------------------------
# 7. OpenAI Codex Multi-File Patch Endpoints
# -------------------------------------------------------------
class PatchItem(BaseModel):
    file_path: str
    updated_content: str


class ApplyPatchesRequest(BaseModel):
    patches: list[PatchItem]


@router.post("/patches/apply")
async def apply_patches(request: ApplyPatchesRequest) -> dict[str, Any]:
    """Atomically apply a batch of patches with rollback on error."""
    codex = get_codex_engine()
    try:
        patch_objs = [codex.create_patch(p.file_path, p.updated_content) for p in request.patches]
        return codex.apply_patches_atomically(patch_objs)
    except Exception as e:
        logger.error("Failed to apply patches: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------
# 8. Fine-Tuning Dataset Export (SFT & DPO)
# -------------------------------------------------------------
@router.get("/trajectories/export/sft")
async def export_sft_dataset(
    format: str = Query(default="chatml", pattern="^(chatml|alpaca)$")
) -> dict[str, Any]:
    """Export successful trajectories formatted as SFT fine-tuning samples."""
    harness = get_trajectory_harness()
    samples = harness.export_sft_dataset(format=format)
    return {
        "count": len(samples),
        "format": format,
        "samples": samples,
        "protocol_version": PROTOCOL_VERSION,
    }


@router.get("/trajectories/export/dpo")
async def export_dpo_dataset() -> dict[str, Any]:
    """Export contrastive trajectory pairs formatted for Direct Preference Optimization."""
    harness = get_trajectory_harness()
    pairs = harness.export_dpo_dataset()
    return {
        "count": len(pairs),
        "pairs": pairs,
        "protocol_version": PROTOCOL_VERSION,
    }


# -------------------------------------------------------------
# 9. Computer-Use / Secure Browser Automation Endpoints
# -------------------------------------------------------------
class BrowserActionRequest(BaseModel):
    action: str = Field(description="Action name: navigate, screenshot, scrape, click, fill, wait, scroll, evaluate")
    url: Optional[str] = Field(default=None, description="URL for navigation or scraping")
    selector: Optional[str] = Field(default=None, description="CSS selector for element interaction")
    value: Optional[str] = Field(default=None, description="Value for fill operation")
    timeout: Optional[int] = Field(default=30000, description="Timeout in milliseconds")


@router.get("/browser/status")
async def get_browser_status() -> dict[str, Any]:
    """Get status, allowed domains, and statistics of browser controller."""
    from synapse.integrations.browser_controller import get_browser_controller

    controller = get_browser_controller()
    stats = controller.get_statistics()
    return {
        "status": "ready",
        "allowed_domains": controller.config.allowed_domains,
        "blocked_domains": controller.config.blocked_domains,
        "enforce_domain_whitelist": controller.config.enforce_domain_whitelist,
        "allow_localhost": controller.config.allow_localhost,
        "statistics": stats,
        "protocol_version": PROTOCOL_VERSION,
    }


@router.post("/browser/execute")
async def execute_browser_action(request: BrowserActionRequest) -> dict[str, Any]:
    """Execute a capability-gated browser action (Computer-Use protocol)."""
    from synapse.integrations.browser_controller import get_browser_controller

    controller = get_browser_controller()
    res = await controller.execute(
        action=request.action,
        url=request.url,
        selector=request.selector,
        value=request.value,
        timeout=request.timeout,
    )
    return res.to_dict()


# -------------------------------------------------------------
# 10. Metacognition & Continuous Learning Endpoints
# -------------------------------------------------------------
class OptimizePromptRequest(BaseModel):
    agent_name: str = Field(default="runtime_agent", description="Target agent name for prompt optimization")


@router.get("/learning/patterns")
async def get_learning_patterns() -> dict[str, Any]:
    """Analyze execution patterns and detect low-performing skills and bottlenecks."""
    from synapse.learning.engine import get_learning_engine

    engine = get_learning_engine()
    insights = await engine.analyze_patterns()
    return insights


@router.post("/learning/optimize-prompts")
async def optimize_agent_prompts(request: OptimizePromptRequest) -> dict[str, Any]:
    """Generate prompt improvements and system instruction updates for an agent."""
    from synapse.learning.engine import get_learning_engine

    engine = get_learning_engine()
    result = await engine.optimize_prompts(request.agent_name)
    return result

