"""Built-in local-model generic executor skill."""
from __future__ import annotations

from synapse.core.models import ExecutionContext


async def execute_local_task(ctx: ExecutionContext, task: str = "", **params):
    """Answer ordinary chat/general tasks with the downloaded local model.

    The caller may raise the output budget explicitly, but the default is large
    enough for reports and audits instead of silently truncating at 256 tokens.
    """
    from synapse.llm.local_model import LocalModelUnavailable, LocalTransformersProvider
    from synapse.models import get_model_registry

    safety_boundary = params.get("safety_boundary")
    if safety_boundary == "no_self_modification":
        manifests = [
            manifest for manifest in get_model_registry().list()
            if manifest.status == "downloaded" and manifest.local_path
        ]
        model_id = manifests[0].model_id if manifests else "не загружена"
        return {
            "success": True,
            "content": (
                "Я не могу честно изменить собственные нейросетевые веса или базовую модель из чата. "
                "В этой системе я могу изучить workspace, предложить изменения prompt/skills, "
                "собрать verified dataset и запустить отдельный LoRA/QLoRA pipeline с holdout-метрикой "
                "и promotion gate. Изменение файлов проекта выполняется только отдельным write-режимом "
                "с явным подтверждением и workspace-scope."
            ),
            "provider": "synapse_boundary",
            "model": model_id,
            "capabilities": ["workspace_audit", "prompt_proposal", "verified_dataset", "adapter_training"],
            "weights_modified": False,
        }

    manifests = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    if not manifests:
        return {"success": False, "error": "No downloaded local model is available"}

    manifest = manifests[0]
    provider = LocalTransformersProvider(manifest.local_path)
    prompt = task
    if params.get("read_only"):
        prompt = "Отвечай только по фактам из предоставленного read-only результата. Не утверждай, что выполнял действия, которых не было.\n\n" + task
    try:
        max_new_tokens = int(params.get("max_new_tokens", params.get("max_tokens", 2048)))
        max_new_tokens = max(128, min(max_new_tokens, 16_384))
        response = await provider.generate(prompt, max_new_tokens=max_new_tokens)
    except (LocalModelUnavailable, RuntimeError, ValueError) as exc:
        return {"success": False, "error": str(exc), "provider": "local_transformers"}
    return {
        "success": True,
        "content": response.get("content", ""),
        "provider": response.get("provider", "local_transformers"),
        "model": manifest.model_id,
        "usage": response.get("usage", {}),
        "max_new_tokens": max_new_tokens,
    }


__all__ = ["execute_local_task"]
