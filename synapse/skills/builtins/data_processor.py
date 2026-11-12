"""Built-in data analysis/transform skill backed by the routed model.

Mirrors :mod:`synapse.skills.builtins.code_generator`: the heuristic planner
can emit a ``data_processor`` step, so the skill must exist and do real work
instead of aborting the cycle with "Active skill not found".
"""
from __future__ import annotations

from synapse.core.models import ExecutionContext
from synapse.skills.builtins.local_executor import execute_local_task

PROTOCOL_VERSION: str = "1.0"

_DATA_PROMPT = (
    "You are a careful data analyst. Analyse or transform the supplied task "
    "and return a concise, structured answer. State assumptions explicitly, "
    "show the steps you used, and do not invent data that was not provided.\n\n"
    "TASK:\n{task}"
)


async def execute_data_processing(
    ctx: ExecutionContext,
    task: str = "",
    **params,
):
    payload = str(task or params.get("task_description") or "").strip()
    if not payload:
        return {"success": False, "error": "data_processor requires a task"}

    forward = {
        key: params[key]
        for key in ("model", "max_new_tokens", "max_tokens")
        if params.get(key)
    }
    result = await execute_local_task(ctx, task=_DATA_PROMPT.format(task=payload), **forward)
    if result.get("success"):
        result["skill"] = "data_processor"
        result["task"] = payload
    return result


__all__ = ["execute_data_processing"]
