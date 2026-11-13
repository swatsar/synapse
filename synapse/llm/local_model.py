"""Local Transformers causal-LM provider for on-device task planning and chat.

The model is loaded lazily and only used when a downloaded registry manifest is
explicitly activated. No cloud fallback is hidden inside this provider.

Promoted LoRA adapters (the self-development output) are discovered next to the
checkpoint and applied before generation, so training changes inference instead
of only producing files on disk.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("synapse.llm.local_model")

# The checkpoint is a generic instruct model; without an identity it answers
# questions about "you" as if it were a stranger and gives generic advice to the
# user. This prompt is part of inference, not training data, and is kept short
# so a 0.5B model can follow it reliably.
_SYSTEM_PROMPT = (
    "Ты — Synapse, автономный ИИ-агент для программирования и разработки. "
    "Ты работаешь в локальном workspace, выполняешь задачи, проверяешь результаты, "
    "обучаешься на проверенном опыте и развиваешь собственную сеть навыков. "
    "Отвечай на языке пользователя. Если спрашивают о тебе, говори о своей "
    "архитектуре, текущем состоянии и ограничениях, а не давай общие советы человеку. "
    "Не утверждай, что выполнил действие, если инструмент не вернул результат."
)


def discover_promoted_adapter(
    model_path: str | Path,
    workspace_root: str | Path | None = None,
) -> Path | None:
    """Return the adapter inference must load for this model.

    A valid explicit pin (``<adapters>/active.json``) wins, then the newest
    promoted adapter of the same base model. Only adapters with a matching
    ``training_manifest.json`` promotion status are eligible; a rejected or
    unrelated adapter must never silently alter inference. An explicit
    ``SYNAPSE_ADAPTER_PATH`` environment variable wins over both for manual
    pinning.
    """
    explicit = os.getenv("SYNAPSE_ADAPTER_PATH", "").strip()
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        return candidate if (candidate / "adapter_config.json").is_file() else None
    if os.getenv("SYNAPSE_DISABLE_ADAPTERS", "").strip() in {"1", "true", "yes"}:
        return None

    from synapse.training.adapters import discover_promoted_adapter as _discover

    return _discover(model_path, workspace_root)


class LocalModelUnavailable(RuntimeError):
    """Raised when the local model runtime cannot be loaded."""


class LocalTransformersProvider:
    name = "local_transformers"

    def __init__(
        self,
        model_path: str | Path,
        *,
        device: str | None = None,
        adapter_path: str | Path | None = None,
    ):
        self.model_path = Path(model_path).expanduser().resolve()
        self.device = device or ("cuda" if self._cuda_available() else "cpu")
        self.adapter_path: Path | None = (
            Path(adapter_path).expanduser().resolve()
            if adapter_path
            else discover_promoted_adapter(self.model_path)
        )
        self._tokenizer = None
        self._model = None
        self._adapter_applied = False
        self._adapter_error: str | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch
            return bool(torch.cuda.is_available())
        except ImportError:
            return False

    def _load(self) -> tuple[Any, Any]:
        if self._model is not None and self._tokenizer is not None:
            return self._tokenizer, self._model
        if not self.model_path.is_dir():
            raise LocalModelUnavailable(f"local model path does not exist: {self.model_path}")
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise LocalModelUnavailable(f"local transformers runtime unavailable: {exc}") from exc
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        tokenizer = AutoTokenizer.from_pretrained(str(self.model_path), local_files_only=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path), local_files_only=True, dtype=dtype,
        )
        if self.adapter_path is not None:
            try:
                from peft import PeftModel

                model = PeftModel.from_pretrained(
                    model, str(self.adapter_path), is_trainable=False,
                )
                self._adapter_applied = True
            except Exception as exc:  # a broken adapter must not kill base inference
                self._adapter_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Promoted adapter could not be applied (%s): %s",
                    self.adapter_path, exc,
                )
        model = model.to(self.device)
        model.eval()
        self._tokenizer, self._model = tokenizer, model
        return tokenizer, model

    def _generate_sync(self, prompt: str, max_new_tokens: int = 2048) -> dict[str, Any]:
        import torch
        tokenizer, model = self._load()
        text = self._format_prompt(tokenizer, prompt)
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        generated = output[0, inputs["input_ids"].shape[1]:]
        output_tokens = int(generated.shape[0])
        # A length-limited generation is reported honestly so callers can warn
        # the user instead of presenting a cut-off sentence as complete.
        finish_reason = "length" if output_tokens >= max_new_tokens else "stop"
        return {
            "content": tokenizer.decode(generated, skip_special_tokens=True).strip(),
            "provider": self.name,
            "model": self.model_path.name,
            "device": self.device,
            "finish_reason": finish_reason,
            "truncated": finish_reason == "length",
            "adapter_path": str(self.adapter_path) if self.adapter_path else None,
            "adapter_applied": self._adapter_applied,
            "adapter_error": self._adapter_error,
            "usage": {"input_tokens": int(inputs["input_ids"].shape[1]), "output_tokens": output_tokens},
        }

    @staticmethod
    def _format_prompt(tokenizer: Any, prompt: str) -> str:
        """Use the instruct chat template when the checkpoint ships one.

        Raw completion prompts make instruct models ramble until the token cap
        and then look truncated mid-sentence. The chat template teaches the
        model where its turn ends, so generation stops at the real EOS token.
        """
        template = getattr(tokenizer, "chat_template", None)
        if not template:
            return prompt
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except (TypeError, ValueError, AttributeError):
            # Some older templates reject the system role; keep the user turn
            # rather than failing inference entirely.
            try:
                return tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except (TypeError, ValueError, AttributeError):
                return prompt

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not prompt or not prompt.strip():
            raise ValueError("local model prompt is empty")
        async with self._lock:
            return await asyncio.to_thread(
                self._generate_sync, prompt, int(kwargs.get("max_new_tokens", 2048))
            )


_PROVIDER_CACHE: dict[tuple[str, str, str], LocalTransformersProvider] = {}
_PROVIDER_CACHE_LOCK = threading.Lock()


def _adapter_cache_key(adapter_path: Path | None) -> str:
    if adapter_path is None:
        return ""
    try:
        return f"{adapter_path}:{adapter_path.stat().st_mtime_ns}"
    except OSError:
        return str(adapter_path)


def get_local_provider(model_path: str | Path, *, device: str | None = None) -> LocalTransformersProvider:
    """Return a process-wide provider so the weights are loaded once.

    Loading a local checkpoint from disk takes tens of seconds on CPU. Reusing
    the provider keeps subsequent chat turns responsive without changing the
    security boundary of the trusted built-in executor.

    The cache key includes the promoted adapter identity and mtime, so a new
    self-training run is picked up on the next request instead of serving the
    previous adapter until restart.
    """
    resolved = str(Path(model_path).expanduser().resolve())
    adapter = discover_promoted_adapter(resolved)
    key = (resolved, device or "", _adapter_cache_key(adapter))
    with _PROVIDER_CACHE_LOCK:
        provider = _PROVIDER_CACHE.get(key)
        if provider is None:
            # Drop providers for the same checkpoint that were loaded with an
            # older adapter. Otherwise every training run would leave a full
            # copy of the base weights alive in memory.
            stale = [
                existing
                for existing in _PROVIDER_CACHE
                if existing[0] == resolved
                and existing[1] == (device or "")
                and existing != key
            ]
            for existing in stale:
                _PROVIDER_CACHE.pop(existing, None)
            provider = LocalTransformersProvider(
                resolved, device=device, adapter_path=adapter,
            )
            _PROVIDER_CACHE[key] = provider
        return provider


def clear_local_provider_cache() -> None:
    """Drop cached checkpoints (used by tests and explicit runtime reloads)."""
    with _PROVIDER_CACHE_LOCK:
        _PROVIDER_CACHE.clear()


def adapter_status(model_path: str | Path) -> dict[str, Any]:
    """Report which promoted adapter inference will use for a checkpoint.

    This never loads weights. When a provider for the checkpoint is already
    cached, its real load result (``adapter_applied``/``adapter_error``) is
    returned; otherwise the discovered adapter is reported as selected and
    pending the next inference.
    """
    resolved = str(Path(model_path).expanduser().resolve())
    selected = discover_promoted_adapter(resolved)
    loaded: LocalTransformersProvider | None = None
    with _PROVIDER_CACHE_LOCK:
        for (cached_path, _device, _adapter), provider in _PROVIDER_CACHE.items():
            if cached_path == resolved:
                loaded = provider
                break
    return {
        "base_model_path": resolved,
        "adapter_path": str(selected) if selected else None,
        "adapter_name": selected.name if selected else None,
        "selected": selected is not None,
        "loaded": loaded is not None,
        "applied": bool(loaded is not None and loaded._adapter_applied),
        "error": loaded._adapter_error if loaded is not None else None,
        "protocol_version": PROTOCOL_VERSION,
    }


__all__ = [
    "LocalModelUnavailable",
    "LocalTransformersProvider",
    "adapter_status",
    "clear_local_provider_cache",
    "discover_promoted_adapter",
    "get_local_provider",
]
