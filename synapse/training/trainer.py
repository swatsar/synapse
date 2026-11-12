"""Real LoRA training over immutable verified experience snapshots.

The implementation deliberately uses a small explicit torch loop instead of
claiming that dataset export equals training. It loads a frozen base model,
wraps it with PEFT LoRA, performs optimizer/backprop steps, saves an adapter,
and reloads it for a forward-pass smoke. QLoRA is rejected unless the optional
bitsandbytes runtime is installed and explicitly requested.
"""
from __future__ import annotations

import gc
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
    holdout_loss_before: float | None = None
    holdout_loss_after: float | None = None
    holdout_metric: str = "causal_lm_loss"
    promotion_gate: str = "not_evaluated"
    promotion_status: str = "not_promoted"
    behavioral_probes: int = 0
    behavioral_passed_before: int | None = None
    behavioral_passed_after: int | None = None
    behavioral_gate: str = "not_evaluated"
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


def _masked_labels(input_ids: Any, attention_mask: Any) -> Any:
    """Ignore padding positions in the causal-LM loss."""
    labels = input_ids.clone()
    labels[attention_mask == 0] = -100
    return labels


def _text_batches(texts: list[str], batch_size: int) -> list[list[str]]:
    """Split texts into bounded batches.

    Tokenizing (and forwarding) every experience record at once allocates a
    ``batch × max_length × vocab`` logits tensor. With a realistic dataset that
    is several gigabytes and used to crash CPU training with an allocator
    error. Batches keep peak memory bounded regardless of dataset size.
    """
    size = max(1, int(batch_size))
    return [texts[start:start + size] for start in range(0, len(texts), size)]


def _loss_on_records(
    model: Any,
    tokenizer: Any,
    records: list[Any],
    device: str,
    max_length: int,
    *,
    batch_size: int = 8,
) -> float | None:
    texts = [_training_text(record) for record in records]
    if not texts:
        return None
    model.eval()
    import torch
    total_loss = 0.0
    total_tokens = 0
    with torch.no_grad():
        for batch in _text_batches(texts, batch_size):
            encoded = tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True,
                max_length=max_length,
            )
            input_ids = encoded["input_ids"].to(device)
            attention_mask = encoded["attention_mask"].to(device)
            output = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=_masked_labels(input_ids, attention_mask),
            )
            if not torch.isfinite(output.loss):
                return None
            tokens = max(1, int(attention_mask.sum().item()))
            total_loss += float(output.loss.detach().cpu().item()) * tokens
            total_tokens += tokens
    return total_loss / total_tokens if total_tokens else None


def _training_text(record: Any) -> str:
    if getattr(record, "training_text", None):
        return str(record.training_text)
    feedback = getattr(record, "feedback", {}) or {}
    value = feedback.get("training_text") or feedback.get("response")
    if value:
        return f"User: {record.objective}\nAssistant: {value}"
    return ""


def _behavior_probes(records: list[Any], *, limit: int = 4) -> list[dict[str, Any]]:
    """Build generation probes from holdout records with output criteria.

    A lower causal-LM loss does not by itself prove the model still answers
    correctly. These probes replay the deterministic output checks that
    verified the original experience, so an adapter that memorizes the
    training text while breaking basic behaviour cannot be promoted.
    """
    probes: list[dict[str, Any]] = []
    for record in records:
        objective = str(getattr(record, "objective", "") or "").strip()
        feedback = getattr(record, "feedback", {}) or {}
        verification = feedback.get("verification") or {}
        checks = verification.get("checks") or []
        criteria: list[str] = []
        for check in checks:
            criterion = str((check or {}).get("criterion") or "")
            if criterion.startswith("output_contains:") or criterion.startswith("output_not_contains:"):
                if len(criterion) > len("output_contains:"):
                    criteria.append(criterion)
        if objective and criteria:
            probes.append({"objective": objective, "criteria": criteria})
        if len(probes) >= limit:
            break
    return probes


def _fixed_behavior_probes() -> list[dict[str, Any]]:
    """Probes that do not depend on the current training records.

    Record-derived probes only exist when an earlier task had deterministic
    output criteria. A fresh store often has none, which used to promote an
    adapter on holdout loss alone. These fixed probes always exercise basic
    instruction-following and Synapse identity, so a catastrophic adapter is
    rejected even on the first run.
    """
    return [
        {
            "objective": "Повтори ровно одно слово: Synapse",
            "criteria": ["output_contains:Synapse"],
        },
        {
            "objective": "Повтори ровно одно слово: мицелий",
            "criteria": ["output_contains:мицелий"],
        },
        {
            "objective": "Напиши ровно два символа: OK",
            "criteria": ["output_contains:OK"],
        },
    ]


def _criterion_passes(criterion: str, text: str) -> bool:
    """Check one output criterion using the same semantics as the verifier."""
    if criterion.startswith("output_contains:"):
        return criterion[len("output_contains:"):] in text
    if criterion.startswith("output_not_contains:"):
        return criterion[len("output_not_contains:"):] not in text
    return False


def _generate_text(
    model: Any,
    tokenizer: Any,
    prompt: str,
    *,
    device: str,
    max_new_tokens: int = 24,
) -> str:
    import torch

    text = prompt
    template = getattr(tokenizer, "chat_template", None)
    if template:
        # Match inference: a checkpoint must receive the same Synapse identity
        # prompt during behavioural probes, otherwise the probe measures a
        # different agent than the one users talk to.
        try:
            from synapse.llm.local_model import _SYSTEM_PROMPT

            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            try:
                text = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                text = tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
        except Exception:
            text = prompt
    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)
    previous_cache = getattr(model.config, "use_cache", None)
    model.config.use_cache = True
    try:
        with torch.no_grad():
            generated = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
    finally:
        if previous_cache is not None:
            model.config.use_cache = previous_cache
    new_tokens = generated[0][input_ids.shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def _behavior_score(
    model: Any,
    tokenizer: Any,
    probes: list[dict[str, Any]],
    *,
    device: str,
) -> int:
    """Count probes whose deterministic criteria the model still satisfies."""
    passed = 0
    for probe in probes:
        try:
            text = _generate_text(
                model, tokenizer, probe["objective"], device=device,
            )
        except Exception:
            continue
        if all(_criterion_passes(item, text) for item in probe["criteria"]):
            passed += 1
    return passed


def _promotion_decision(
    *,
    holdout_loss_before: float,
    holdout_loss_after: float,
    behavioral_probes: int,
    behavioral_before: int | None,
    behavioral_after: int | None,
) -> tuple[bool, str, str]:
    """Decide promotion from holdout loss plus behavioural regression.

    Holdout loss must always improve. When deterministic probes exist, the
    adapter must additionally not answer fewer of them correctly than the base
    model did; otherwise the adapter is rejected even if its loss is lower.
    """
    if holdout_loss_after >= holdout_loss_before:
        return False, "holdout_loss_after_lt_before", "blocked_no_holdout_improvement"
    if behavioral_probes > 0:
        gate = "holdout_loss_and_no_behavioral_regression"
        if int(behavioral_after or 0) < int(behavioral_before or 0):
            return False, gate, "blocked_behavioral_regression"
        return True, gate, "promoted"
    return True, "holdout_loss_after_lt_before", "promoted"


def _select_device(torch: Any, *, require_gpu: bool) -> str:
    """Choose a training device without silently risking a CUDA OOM.

    Autonomous training passes ``require_gpu=False``; on workstations with a
    shared GPU that used to select CUDA anyway and fail with an out-of-memory
    error even though CPU was a valid fallback. An explicit
    ``SYNAPSE_TRAIN_DEVICE`` still overrides the default for operators.
    """
    requested = os.getenv("SYNAPSE_TRAIN_DEVICE", "").strip().lower()
    if requested in {"cpu", "cuda"}:
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("SYNAPSE_TRAIN_DEVICE=cuda but CUDA is unavailable")
        return requested
    if require_gpu:
        return "cuda"
    return "cpu"


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
    micro_batch_size: int | None = None,
    gradient_accumulation_steps: int = 0,
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
    holdout_records = experience_store.get_records(snapshot.holdout_ids)
    if len(records) != len(snapshot.train_ids) or len(holdout_records) != len(snapshot.holdout_ids):
        raise RuntimeError("snapshot references missing experience records")
    if any(not record.verified_for_training for record in records + holdout_records):
        raise RuntimeError("snapshot contains a record that is no longer verified")
    texts = [_training_text(record) for record in records]
    holdout_texts = [_training_text(record) for record in holdout_records]
    if not all(texts):
        return TrainingRunEvidence(
            status="blocked", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, blockers=("verified_records_require_non_empty_training_text",), mode=mode,
        )
    if not all(holdout_texts):
        return TrainingRunEvidence(
            status="blocked", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, blockers=("holdout_records_require_non_empty_training_text",), mode=mode,
        )

    torch, LoraConfig, PeftModel, TaskType, get_peft_model, AutoModelForCausalLM, AutoTokenizer = _load_runtime()
    device = _select_device(torch, require_gpu=require_gpu)
    dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(str(base_path), local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(base_path), local_files_only=True, dtype=dtype,
    ).to(device)
    model.config.use_cache = False
    holdout_loss_before = _loss_on_records(model, tokenizer, holdout_records, device, max_length)
    if holdout_loss_before is None:
        return TrainingRunEvidence(
            status="blocked", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, blockers=("holdout_metric_unavailable",), mode=mode,
        )
    # Measure real answering behaviour on deterministic holdout probes before
    # any weights change. Lower loss alone can hide memorization that breaks
    # basic answers, so promotion requires no behavioural regression.
    behavioral_probes = _behavior_probes(holdout_records)
    for probe in _fixed_behavior_probes():
        if probe not in behavioral_probes:
            behavioral_probes.append(probe)
    behavioral_before = (
        _behavior_score(model, tokenizer, behavioral_probes, device=device)
        if behavioral_probes else None
    )
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
    # Micro-batching keeps the forward/backward graph small. Gradient
    # accumulation preserves an effective full-dataset step, so this is a
    # memory fix, not a change in what the adapter learns.
    if micro_batch_size is None:
        try:
            micro_batch_size = int(os.getenv("SYNAPSE_TRAIN_MICRO_BATCH", "8"))
        except ValueError:
            micro_batch_size = 8
    micro_batch_size = max(1, min(int(micro_batch_size), 64))
    batches = _text_batches(texts, micro_batch_size)
    accumulate = int(gradient_accumulation_steps or 0)
    if accumulate <= 0:
        accumulate = len(batches)
    accumulate = max(1, min(accumulate, len(batches)))
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=learning_rate)
    model.train()
    final_loss: float | None = None
    cursor = 0
    try:
        for _ in range(max(1, steps)):
            optimizer.zero_grad(set_to_none=True)
            step_losses: list[float] = []
            for _ in range(accumulate):
                batch = batches[cursor % len(batches)]
                cursor += 1
                encoded = tokenizer(
                    batch, return_tensors="pt", padding=True, truncation=True,
                    max_length=max_length,
                )
                input_ids = encoded["input_ids"].to(device)
                attention_mask = encoded["attention_mask"].to(device)
                labels = _masked_labels(input_ids, attention_mask)
                output = model(
                    input_ids=input_ids, attention_mask=attention_mask, labels=labels,
                )
                loss = output.loss
                if not torch.isfinite(loss):
                    raise RuntimeError("non-finite training loss")
                (loss / accumulate).backward()
                step_losses.append(float(loss.detach().cpu().item()))
            optimizer.step()
            final_loss = sum(step_losses) / len(step_losses)
        output_path.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)
        adapter_hash = _sha256_tree(output_path)
        # The trainer runs inside the long-lived API process, and each copy of
        # a 0.5B checkpoint is ~2 GB in fp32. Release the trained copy before
        # loading the verification copy so peak RSS does not hold two base
        # models at once across repeated autonomous runs.
        del optimizer
        del model
        gc.collect()
        reload_base = AutoModelForCausalLM.from_pretrained(
            str(base_path), local_files_only=True, dtype=dtype,
        ).to(device)
        reloaded = PeftModel.from_pretrained(reload_base, str(output_path), is_trainable=False)
        reloaded.eval()
        probe_encoded = tokenizer(
            batches[0], return_tensors="pt", padding=True, truncation=True,
            max_length=max_length,
        )
        probe_ids = probe_encoded["input_ids"].to(device)[:, :8]
        probe_mask = probe_encoded["attention_mask"].to(device)[:, :8]
        with torch.no_grad():
            probe = reloaded(input_ids=probe_ids, attention_mask=probe_mask)
        if not torch.isfinite(probe.logits).all():
            raise RuntimeError("reloaded adapter produced non-finite logits")
        holdout_loss_after = _loss_on_records(reloaded, tokenizer, holdout_records, device, max_length)
        if holdout_loss_after is None:
            raise RuntimeError("holdout metric unavailable after reload")
        behavioral_after = (
            _behavior_score(reloaded, tokenizer, behavioral_probes, device=device)
            if behavioral_probes else None
        )
        promoted, promotion_gate, promotion_status = _promotion_decision(
            holdout_loss_before=holdout_loss_before,
            holdout_loss_after=holdout_loss_after,
            behavioral_probes=len(behavioral_probes),
            behavioral_before=behavioral_before,
            behavioral_after=behavioral_after,
        )
        behavioral_gate = (
            "not_available" if not behavioral_probes
            else (
                "behavioral_regression"
                if int(behavioral_after or 0) < int(behavioral_before or 0)
                else "no_behavioral_regression"
            )
        )
        manifest = {
            "run_id": run_id, "mode": mode, "base_model": str(base_path),
            "base_model_hash": base_hash, "adapter_hash": adapter_hash,
            "snapshot_id": snapshot.snapshot_id, "snapshot_manifest_hash": snapshot.manifest_hash,
            "trainable_parameter_count": trainable, "total_parameter_count": total,
            "steps": max(1, steps), "final_loss": final_loss,
            "micro_batch_size": micro_batch_size,
            "gradient_accumulation_steps": accumulate,
            "holdout_metric": "causal_lm_loss", "holdout_loss_before": holdout_loss_before,
            "holdout_loss_after": holdout_loss_after, "promotion_gate": promotion_gate,
            "promotion_status": promotion_status,
            "behavioral_probes": len(behavioral_probes),
            "behavioral_passed_before": behavioral_before,
            "behavioral_passed_after": behavioral_after,
            "behavioral_gate": behavioral_gate,
        }
        (output_path / "training_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return TrainingRunEvidence(
            status="completed", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=str(output_path), trainable_parameter_count=trainable,
            total_parameter_count=total, steps=max(1, steps), final_loss=final_loss,
            holdout_loss_before=holdout_loss_before, holdout_loss_after=holdout_loss_after,
            holdout_metric="causal_lm_loss", promotion_gate=promotion_gate,
            promotion_status=promotion_status,
            behavioral_probes=len(behavioral_probes),
            behavioral_passed_before=behavioral_before,
            behavioral_passed_after=behavioral_after,
            behavioral_gate=behavioral_gate,
            reload_forward_pass=True, mode=mode,
        )
    except Exception as exc:
        return TrainingRunEvidence(
            status="failed", run_id=run_id, base_model=str(base_path), base_model_hash=base_hash,
            snapshot_id=snapshot.snapshot_id, snapshot_manifest_hash=snapshot.manifest_hash,
            adapter_path=None, mode=mode, error=str(exc),
        )


__all__ = ["TrainingRunEvidence", "train_lora"]
