"""Built-in generic executor: local weights, configured models, OpenCode.

The local checkpoint is the dependable floor of the system. OpenCode is the
preferred external runtime, but free-model quotas and network failures are
real, so an explicit OpenCode request degrades to the downloaded model instead
of failing the whole chat. The fallback is always reported honestly.
"""
from __future__ import annotations

from typing import Any

from synapse.core.models import ExecutionContext

_MAX_NEW_TOKENS_DEFAULT = 2048
_MAX_NEW_TOKENS_CEILING = 8_192


def _downloaded_manifests() -> list[Any]:
    from synapse.models import get_model_registry

    return [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]


def _requested_tokens(params: dict[str, Any]) -> int:
    requested = params.get("max_new_tokens") or params.get("max_tokens")
    try:
        value = int(requested) if requested else _MAX_NEW_TOKENS_DEFAULT
    except (TypeError, ValueError):
        value = _MAX_NEW_TOKENS_DEFAULT
    return max(64, min(value, _MAX_NEW_TOKENS_CEILING))


async def _router_result(task: str, prompt: str, model_id: str) -> dict:
    from synapse.llm.omnirouter import get_omnirouter

    result = await get_omnirouter().execute(
        task_description=task,
        prompt=prompt,
        requirements={"model": model_id},
    )
    if result.get("success"):
        payload = {
            "success": True,
            "content": result.get("content", ""),
            "provider": result.get("provider_used", "omnirouter"),
            "model": result.get("model_used", model_id),
            "usage": result.get("usage", {}),
        }
        for key in ("fallback_from", "fallback_reason", "quota_exhausted"):
            if result.get(key) is not None:
                payload[key] = result[key]
        for key in (
            "finish_reason", "truncated", "max_new_tokens",
            "adapter_path", "adapter_applied", "adapter_error",
        ):
            if key in result:
                payload[key] = result[key]
        return payload
    return {
        "success": False,
        "error": result.get("error") or "All model providers failed",
        "provider": result.get("provider_used"),
        "model": model_id,
        "attempts": result.get("attempts", []),
    }


def _preferred_external_model() -> str | None:
    try:
        from synapse.integrations.opencode_bridge import preferred_model
        return preferred_model()
    except Exception:
        return None


def _quota_summary() -> dict[str, Any]:
    try:
        from synapse.integrations.opencode_bridge import quota_status
        return quota_status()
    except Exception:
        return {"exhausted": False, "message": None, "retry_after_seconds": 0}


def _quota_error_message(quota: dict[str, Any]) -> str:
    message = (
        "Бесплатный лимит OpenCode исчерпан. Подпишитесь на OpenCode Go, "
        "настройте другого провайдера или загрузите локальную модель — "
        "тогда Synapse сможет отвечать без OpenCode."
    )
    retry = int(quota.get("retry_after_seconds") or 0)
    if retry:
        message += f" Повторная попытка возможна примерно через {retry} с."
    if quota.get("message"):
        message += f" Ответ OpenCode: {str(quota['message'])[:300]}"
    return message


def _is_opencode_model(model_id: str) -> bool:
    return str(model_id or "").strip().lower().startswith("opencode/")


def _primary_error(result: dict[str, Any]) -> str:
    attempts = result.get("attempts") or []
    for attempt in attempts:
        error = str(attempt.get("error") or "").strip()
        if error:
            return error[:500]
    return str(result.get("error") or "OpenCode request failed")[:500]


async def _local_response(manifest: Any, prompt: str, max_new_tokens: int) -> dict:
    from synapse.llm.local_model import get_local_provider

    provider = get_local_provider(manifest.local_path)
    response = await provider.generate(prompt, max_new_tokens=max_new_tokens)
    return {
        "success": True,
        "content": response.get("content", ""),
        "provider": response.get("provider", "local_transformers"),
        "model": manifest.model_id,
        "usage": response.get("usage", {}),
        "max_new_tokens": max_new_tokens,
        "finish_reason": response.get("finish_reason"),
        "truncated": bool(response.get("truncated", False)),
        "adapter_path": response.get("adapter_path"),
        "adapter_applied": bool(response.get("adapter_applied", False)),
        "adapter_error": response.get("adapter_error"),
    }


async def _fallback_to_local(
    prompt: str,
    max_new_tokens: int,
    primary: dict[str, Any],
    source_model: str,
) -> dict | None:
    """Answer with the downloaded checkpoint after an external failure.

    Returns ``None`` when no local model is available, so the caller can keep
    the external error instead of inventing a success.
    """
    manifests = _downloaded_manifests()
    if not manifests:
        return None
    quota = _quota_summary()
    reason = _primary_error(primary)
    try:
        result = await _local_response(manifests[0], prompt, max_new_tokens)
    except Exception:
        return None
    result.update({
        "fallback_from": source_model,
        "fallback_reason": reason,
        "quota_exhausted": bool(quota.get("exhausted")),
    })
    return result


async def execute_local_task(ctx: ExecutionContext, task: str = "", **params):
    """Answer ordinary chat/general tasks with the selected or local model.

    An explicitly selected model is routed through OmniRouter, which supports
    downloaded Transformers artifacts, configured providers and OpenCode
    models. Without a selection the existing local-model behaviour is kept;
    when no weights are downloaded, the first usable OpenCode model is tried
    instead of failing the whole chat with "no local model".
    """
    safety_boundary = params.get("safety_boundary")
    if safety_boundary == "no_self_modification":
        manifests = _downloaded_manifests()
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

    prompt = task
    if params.get("read_only"):
        prompt = "Отвечай только по фактам из предоставленного read-only результата. Не утверждай, что выполнял действия, которых не было.\n\n" + task

    max_new_tokens = _requested_tokens(params)
    requested_model = str(params.get("model") or "").strip()
    if requested_model:
        result = await _router_result(task, prompt, requested_model)
        if result.get("success") or not _is_opencode_model(requested_model):
            return result
        fallback = await _fallback_to_local(
            prompt, max_new_tokens, result, requested_model,
        )
        if fallback is not None:
            return fallback
        quota = _quota_summary()
        if quota.get("exhausted"):
            result = dict(result)
            result["error"] = _quota_error_message(quota)
            result["quota_exhausted"] = True
        return result

    manifests = _downloaded_manifests()
    if not manifests:
        quota = _quota_summary()
        if quota.get("exhausted"):
            return {
                "success": False,
                "error": _quota_error_message(quota),
                "provider": "opencode",
                "quota_exhausted": True,
            }
        external_model = _preferred_external_model()
        if external_model:
            return await _router_result(task, prompt, external_model)
        return {
            "success": False,
            "error": (
                "No downloaded local model is available and no OpenCode model was discovered. "
                "Download weights in Settings or configure a model provider."
            ),
        }

    from synapse.llm.local_model import LocalModelUnavailable

    manifest = manifests[0]
    try:
        return await _local_response(manifest, prompt, max_new_tokens)
    except (LocalModelUnavailable, RuntimeError, ValueError) as exc:
        external_model = _preferred_external_model()
        if external_model:
            return await _router_result(task, prompt, external_model)
        return {"success": False, "error": str(exc), "provider": "local_transformers"}


__all__ = ["execute_local_task"]
