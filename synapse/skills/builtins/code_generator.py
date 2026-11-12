"""Built-in code generation skill backed by the routed model.

The planner historically emitted a ``code_generator`` step, but no such skill
was registered, so the cognitive cycle failed with "Active skill not found".
This module makes the step real: it turns the task into a code-generation
prompt and executes it through the same routed/local model path as chat.
"""
from __future__ import annotations

from synapse.core.models import ExecutionContext
from synapse.skills.builtins.local_executor import execute_local_task

PROTOCOL_VERSION: str = "1.0"

_CODE_PROMPT = (
    "You are a senior software engineer. Produce complete, runnable code for "
    "the requested task, including the imports and a short usage note. "
    "Prefer clarity and correctness over cleverness. Do not claim that files "
    "were changed unless the request explicitly asks for a patch.\n\n"
    "TASK:\n{task}"
)


async def execute_code_generation(
    ctx: ExecutionContext,
    task_description: str = "",
    **params,
):
    task = str(task_description or params.get("task") or "").strip()
    if not task:
        return {"success": False, "error": "code_generator requires task_description"}

    forward = {
        key: params[key]
        for key in ("model", "max_new_tokens", "max_tokens")
        if params.get(key)
    }
    result = await execute_local_task(ctx, task=_CODE_PROMPT.format(task=task), **forward)
    if result.get("success"):
        result["skill"] = "code_generator"
        result["task_description"] = task
    return result


__all__ = ["execute_code_generation"]
