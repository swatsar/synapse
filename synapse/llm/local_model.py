"""Local Transformers causal-LM provider for on-device task planning and chat.

The model is loaded lazily and only used when a downloaded registry manifest is
explicitly activated. No cloud fallback is hidden inside this provider.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


class LocalModelUnavailable(RuntimeError):
    """Raised when the local model runtime cannot be loaded."""


class LocalTransformersProvider:
    name = "local_transformers"

    def __init__(self, model_path: str | Path, *, device: str | None = None):
        self.model_path = Path(model_path).expanduser().resolve()
        self.device = device or ("cuda" if self._cuda_available() else "cpu")
        self._tokenizer = None
        self._model = None
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
        ).to(self.device)
        model.eval()
        self._tokenizer, self._model = tokenizer, model
        return tokenizer, model

    def _generate_sync(self, prompt: str, max_new_tokens: int = 512) -> dict[str, Any]:
        import torch
        tokenizer, model = self._load()
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        generated = output[0, inputs["input_ids"].shape[1]:]
        return {
            "content": tokenizer.decode(generated, skip_special_tokens=True).strip(),
            "provider": self.name,
            "model": self.model_path.name,
            "device": self.device,
            "usage": {"input_tokens": int(inputs["input_ids"].shape[1]), "output_tokens": int(generated.shape[0])},
        }

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not prompt or not prompt.strip():
            raise ValueError("local model prompt is empty")
        async with self._lock:
            return await asyncio.to_thread(
                self._generate_sync, prompt, int(kwargs.get("max_new_tokens", 512))
            )


__all__ = ["LocalModelUnavailable", "LocalTransformersProvider"]
