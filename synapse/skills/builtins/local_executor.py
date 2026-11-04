"""Built-in local-model generic executor skill."""
from __future__ import annotations

from synapse.core.models import ExecutionContext


async def execute_local_task(ctx: ExecutionContext, task: str = "", **_params):
    """Answer ordinary chat/general tasks with the downloaded local model."""
    from synapse.llm.local_model import LocalModelUnavailable, LocalTransformersProvider
    from synapse.models import get_model_registry

    manifests = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    if not manifests:
        return {"success": False, "error": "No downloaded local model is available"}

    manifest = manifests[0]
    provider = LocalTransformersProvider(manifest.local_path)
    try:
        response = await provider.generate(task, max_new_tokens=256)
    except (LocalModelUnavailable, RuntimeError, ValueError) as exc:
        return {"success": False, "error": str(exc), "provider": "local_transformers"}
    return {
        "success": True,
        "content": response.get("content", ""),
        "provider": response.get("provider", "local_transformers"),
        "model": manifest.model_id,
        "usage": response.get("usage", {}),
    }


__all__ = ["execute_local_task"]
