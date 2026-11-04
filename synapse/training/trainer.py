"""Real LoRA training over immutable verified experience snapshots.

The implementation deliberately uses a small explicit torch loop instead of
claiming that dataset export equals training. It loads a frozen base model,
wraps it with PEFT LoRA, performs optimizer/backprop steps, saves an adapter,
and reloads it for a forward-pass smoke. QLoRA is rejected unless the optional
bitsandbytes runtime is installed and explicitly requested.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from synapse.experience import DatasetSnapshot, ExperienceStore
from synapse.training.preflight import check_training_preflight


@dataclass(frozen=True)
class TrainingRunEvidence:
    status: str
    run_id: str
    base_model: str
    base_model_hash: str
    snapshot_id: str
    snapshot_manifest_hash: str
    adapter_path: str | None
    trainable_parameter_count: int = 0
    total_parameter_count: int = 0
    steps: int = 0
    final_loss: float | None = None
    reload_forward_pass: bool = False
    blockers: tuple[str, ...] = ()
    mode: str = "lora"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"protocol_version": "1.0"}


def _sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _training_text(record: Any) -> str:
    if getattr(record, "training_text", None):
        return str(record.training_text)
    feedback = getattr(record, "feedback", {}) or {}
    value = feedback.get("training_text") or feedback.get("response")
    if value:
        return f"User: {record.objective}\nAssistant: {value}"
    return ""


def _load_runtime():
    try:
        import torch
        from peft import LoraConfig, PeftModel, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(f"training runtime unavailable: {exc}") from exc
    return torch, LoraConfig, PeftModel, TaskType, get_peft_model, AutoModelForCausalLM, AutoTokenizer


def train_lora(
    *,
    experience_store: ExperienceStore,
    snapshot: DatasetSnapshot,
    base_model: str | Path,
    output_dir: str | Path,
    steps: int = 1,
    max_length: int = 256,
    learning_rate: float = 2e-4,
    mode: str = "lora",
    require_gpu: bool = True,
) -> TrainingRunEvidence:
    """Run real LoRA training and return machine-checkable evidence."""
    import uuid

    run_id = f"train_{uuid.uuid4().hex}"
    base_path = Path(base_model).expanduser().resolve()
    output_path = Path(output_dir).expanduser().resolve()
    base_hash = _sha256_tree(base_path) if base_path.is_dir() else ""
    preflight = check_training_preflight(
        snapshot=snapshot, base_model=base_path, require_gpu=require_gpu
    )
    if mode not in {"lora", "qlora"}:
        return TrainingRunEvidence(
            status="blocked", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, blockers=("unsupported_training_mode",), mode=mode,
        )
    if mode == "qlora":
        try:
            import bitsandbytes  # noqa: F401
        except ImportError:
            return TrainingRunEvidence(
                status="blocked", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
                snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
                adapter_path=None, blockers=("bitsandbytes_required_for_qlora",), mode=mode,
            )
    if not preflight.ready:
        return TrainingRunEvidence(
            status="blocked", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, blockers=preflight.blockers, mode=mode,
        )

    records = experience_store.get_records(snapshot.train_ids)
    if len(records) != len(snapshot.train_ids):
        raise RuntimeError("snapshot references missing experience records")
    if any(not record.verified_for_training for record in records):
        raise RuntimeError("snapshot contains a record that is no longer verified")
    texts = [_training_text(record) for record in records]
    if not all(texts):
        return TrainingRunEvidence(
            status="blocked", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, blockers=("verified_records_require_non_empty_training_text",), mode=mode,
        )

    torch, LoraConfig, PeftModel, TaskType, get_peft_model, AutoModelForCausalLM, AutoTokenizer = _load_runtime()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(str(base_path), local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(base_path), local_files_only=True, dtype=dtype,
    ).to(device)
    model.config.use_cache = False
    target_modules = ["q_proj", "v_proj"]
    available_names = {name.rsplit(".", 1)[-1] for name, _ in model.named_modules()}
    target_modules = [name for name in target_modules if name in available_names]
    if not target_modules:
        raise RuntimeError("could not identify q_proj/v_proj LoRA target modules")
    peft_config = LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, bias="none",
        task_type=TaskType.CAUSAL_LM, target_modules=target_modules,
    )
    model = get_peft_model(model, peft_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    encoded = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=max_length)
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded["attention_mask"].to(device)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=learning_rate)
    model.train()
    final_loss: float | None = None
    try:
        for _ in range(max(1, steps)):
            optimizer.zero_grad(set_to_none=True)
            output = model(input_ids=input_ids, attention_mask=attention_mask, labels=input_ids)
            loss = output.loss
            if not torch.isfinite(loss):
                raise RuntimeError("non-finite training loss")
            loss.backward()
            optimizer.step()
            final_loss = float(loss.detach().cpu().item())
        output_path.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)
        adapter_hash = _sha256_tree(output_path)
        reload_base = AutoModelForCausalLM.from_pretrained(
            str(base_path), local_files_only=True, dtype=dtype,
        ).to(device)
        reloaded = PeftModel.from_pretrained(reload_base, str(output_path), is_trainable=False)
        reloaded.eval()
        with torch.no_grad():
            probe = reloaded(input_ids=input_ids[:, : min(8, input_ids.shape[1])],
                             attention_mask=attention_mask[:, : min(8, attention_mask.shape[1])])
        if not torch.isfinite(probe.logits).all():
            raise RuntimeError("reloaded adapter produced non-finite logits")
        manifest = {
            "run_id": run_id, "mode": mode, "base_model": str(base_path),
            "base_model_hash": base_hash, "adapter_hash": adapter_hash,
            "snapshot_id": snapshot.snapshot_id, "snapshot_manifest_hash": snapshot.manifest_hash,
            "trainable_parameter_count": trainable, "total_parameter_count": total,
            "steps": max(1, steps), "final_loss": final_loss,
        }
        (output_path / "training_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return TrainingRunEvidence(
            status="completed", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=str(output_path), trainable_parameter_count=trainable,
            total_parameter_count=total, steps=max(1, steps), final_loss=final_loss,
            reload_forward_pass=True, mode=mode,
        )
    except Exception as exc:
        return TrainingRunEvidence(
            status="failed", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, mode=mode, error=str(exc),
        )


__all__ = ["TrainingRunEvidence", "train_lora"]
