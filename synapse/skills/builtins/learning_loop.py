"""Chat-driven learning loop for the local model.

Given a skill/topic from chat ("научи меня русскому языку"), the loop:
1. Generates instruction/response training pairs with the strongest available
   teacher (an enabled external agent CLI, else the configured LLM provider,
   else the local model itself).
2. Persists the pairs as verified experience records.
3. Creates a verified dataset snapshot and runs real LoRA training.
4. Repeats while the holdout loss improves, up to a bounded cycle count.

Every number in the result comes from an actual tool run; nothing is claimed
as trained unless a training run completed with evidence.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from synapse.core.models import ExecutionContext
from synapse.training.locking import TrainingLock

_PAIR_HINT = (
    "Generate {count} diverse instruction/response training pairs for the topic: {topic}. "
    "Target language for the pairs: {language}. "
    "Return ONLY a JSON array of objects with keys \"prompt\" and \"response\". No markdown, no commentary."
)

# Fallback hint for weak local teachers that cannot follow strict JSON schema.
_PAIR_HINT_PLAIN = (
    "Write {count} short training dialogues about: {topic} in {language}. "
    "Format each exactly as two lines:\n"
    "Q: <instruction>\n"
    "A: <response>\n"
    "Separate dialogues with a blank line."
)

_MIN_PROMPT_CHARS = 3
_MIN_RESPONSE_CHARS = 2

_REFUSAL_PREFIXES = (
    "i can't",
    "i cannot",
    "i'm sorry",
    "i am sorry",
    "sorry,",
    "as an ai",
    "as a language model",
    "i am unable",
    "i'm unable",
    "unfortunately, i",
    "не могу",
    "не получится",
    "извините",
    "к сожалению, я",
    "я не могу",
    "как искусственный интеллект",
    "как языковая модель",
)

_ERROR_PREFIXES = (
    "traceback (most recent call last)",
    "error:",
    "exception:",
)

_PLACEHOLDER_RESPONSES = {
    "...", "…", "-", "–", "—", "n/a", "none", "null", "undefined", "todo",
}


def _teacher_argv(teacher: str) -> list[str] | None:
    try:
        from synapse.integrations.external_agents import detect_agents

        for agent in detect_agents():
            if agent.agent_id == teacher and agent.available:
                return list(agent.argv)
    except (OSError, ValueError):
        pass
    return None


def _opencode_teacher_models(teacher: str) -> list[str]:
    """Resolve a teacher name to concrete OpenCode model ids.

    ``teacher="opencode"`` picks the preferred free model and one alternate;
    ``teacher="opencode/<model>"`` uses exactly that model. Quota cooldown is
    honoured so the learning loop does not hammer an exhausted free tier.
    """
    from synapse.integrations.opencode_bridge import (
        detect_models,
        is_opencode_quota_exhausted,
        preferred_model,
    )

    if is_opencode_quota_exhausted():
        return []
    requested = str(teacher or "").strip()
    available = [model.model_id for model in detect_models()]
    if requested.startswith("opencode/"):
        return [requested]
    if not available:
        return []
    preferred = preferred_model()
    ordered = ([preferred] if preferred in available else []) + [
        model for model in available if model != preferred
    ]
    try:
        attempts = max(
            1,
            min(
                int(os.getenv("SYNAPSE_OPENCODE_TEACHER_ATTEMPTS", "2")),
                len(ordered),
            ),
        )
    except ValueError:
        attempts = 2
    return ordered[:attempts]


async def _generate_pairs_opencode(model_id: str, prompt: str) -> str:
    """Ask one OpenCode model for training pairs (no tools, no workspace edits)."""
    from synapse.llm.opencode_provider import OpenCodeCLIProvider

    response = await OpenCodeCLIProvider(model_id).generate(prompt)
    return str(response.get("content") or "")


def _local_teacher_id() -> str:
    from synapse.models import get_model_registry

    manifests = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    return manifests[0].model_id if manifests else ""


async def _generate_pairs(
    teacher: str, topic: str, language: str, count: int, workspace_root: Path,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Generate training pairs via the strongest available teacher.

    Teacher precedence: an explicitly requested external coding agent, then
    OpenCode models (the primary model runtime), then the local checkpoint.
    The returned evidence names the teacher that actually produced the pairs,
    so the app never claims an OpenCode teacher when the local model answered.
    """
    prompt = _PAIR_HINT.format(count=count, topic=topic, language=language)
    raw = ""
    attempts: list[dict[str, Any]] = []

    teacher_mode = str(teacher or "auto").strip().lower()
    if teacher_mode in {"auto", "codex", "claude_code"}:
        from synapse.harnesses import CodexHarness, ClaudeCodeHarness, HarnessRequest

        order = ["codex", "claude_code"] if teacher_mode == "auto" else [teacher_mode]
        for agent_id in order:
            argv = _teacher_argv(agent_id)
            if not argv:
                continue
            harness_cls = CodexHarness if agent_id == "codex" else ClaudeCodeHarness
            harness = harness_cls(command=argv, enabled=True, timeout_seconds=300.0)
            result = await harness.execute(HarnessRequest(
                task_id="learning_loop_teacher",
                run_id="learning_loop_teacher",
                prompt=prompt,
                workspace_id=str(workspace_root),
                metadata={"workspace_root": str(workspace_root)},
            ))
            if result.success and result.output:
                raw = result.output
                break
            attempts.append({
                "teacher": agent_id, "kind": "external_agent",
                "result": "no_answer" if not result.output else "failed",
            })
        pairs = _parse_pairs(raw)
        if pairs:
            return pairs, {"teacher": agent_id, "kind": "external_agent"}

    opencode_requested = (
        teacher_mode == "auto"
        or teacher_mode == "opencode"
        or teacher_mode.startswith("opencode/")
    )
    if opencode_requested:
        models = _opencode_teacher_models(teacher)
        if not models:
            from synapse.integrations.opencode_bridge import quota_status

            quota = quota_status()
            attempt: dict[str, Any] = {
                "teacher": teacher if teacher_mode != "auto" else "opencode",
                "kind": "opencode",
                "result": "unavailable_or_quota_exhausted",
            }
            if quota.get("exhausted") or quota.get("retry_after_seconds"):
                attempt["quota_status"] = quota
            attempts.append(attempt)
        for model_id in models:
            try:
                raw = await _generate_pairs_opencode(model_id, prompt)
            except Exception as exc:
                from synapse.integrations.opencode_bridge import quota_status

                quota = quota_status()
                attempt = {
                    "teacher": model_id, "kind": "opencode",
                    "error": str(exc)[:500],
                }
                retry_after = getattr(exc, "retry_after_seconds", 0)
                if retry_after:
                    attempt["retry_after_seconds"] = int(retry_after)
                if quota.get("exhausted"):
                    # Surface the real cooldown instead of an opaque failure:
                    # the UI and self-report can then say when to retry.
                    attempt["quota_status"] = quota
                    attempts.append(attempt)
                    break
                attempts.append(attempt)
                continue
            pairs = _parse_pairs(raw)
            if pairs:
                return pairs, {"teacher": model_id, "kind": "opencode"}
            attempts.append({
                "teacher": model_id, "kind": "opencode",
                "result": "no_valid_pairs",
            })
    elif teacher_mode not in {"codex", "claude_code"}:
        attempts.append({
            "teacher": teacher, "kind": "requested",
            "result": "unrecognized_teacher",
        })

    # Weak local teachers rarely emit strict JSON; give them the plain format.
    raw = await _generate_pairs_locally(
        _PAIR_HINT_PLAIN.format(count=count, topic=topic, language=language)
    )
    pairs = _parse_pairs_plain(raw)
    evidence: dict[str, Any] = {
        "teacher": _local_teacher_id() or "local_model",
        "kind": "local",
    }
    if attempts:
        evidence["attempts"] = attempts
        if any(attempt.get("kind") == "opencode" for attempt in attempts):
            from synapse.integrations.opencode_bridge import quota_status

            evidence["opencode_quota"] = quota_status()
    return pairs, evidence


async def _generate_pairs_locally(prompt: str) -> str:
    from synapse.llm.local_model import LocalTransformersProvider, LocalModelUnavailable
    from synapse.models import get_model_registry

    manifests = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    if not manifests:
        raise RuntimeError("no teacher available: external agents disabled and no local model downloaded")
    provider = LocalTransformersProvider(manifests[0].local_path)
    response = await provider.generate(prompt, max_new_tokens=1024)
    return response.get("content", "")


def _parse_pairs(raw: str) -> list[dict[str, str]]:
    """Extract a JSON array of prompt/response pairs from teacher output."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    pairs: list[dict[str, str]] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        prompt_text = str(item.get("prompt", "")).strip()
        response_text = str(item.get("response", item.get("completion", ""))).strip()
        if prompt_text and response_text:
            pairs.append({"prompt": prompt_text, "response": response_text})
    return pairs


def _parse_pairs_plain(raw: str) -> list[dict[str, str]]:
    """Extract Q:/A: formatted pairs from a weak local teacher's output."""
    pairs: list[dict[str, str]] = []
    current_prompt: str | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        q_match = re.match(r"^(?:Q|Вопрос|Instruction)\s*[:.)-]\s*(.+)$", line, re.IGNORECASE)
        a_match = re.match(r"^(?:A|Ответ|Response)\s*[:.)-]\s*(.+)$", line, re.IGNORECASE)
        if q_match:
            current_prompt = q_match.group(1).strip()
        elif a_match and current_prompt:
            response_text = a_match.group(1).strip()
            if len(current_prompt) >= 3 and len(response_text) >= 1:
                pairs.append({"prompt": current_prompt, "response": response_text})
            current_prompt = None
    return pairs


def _normalize_pair_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _verify_pairs(
    pairs: list[dict[str, str]],
    *,
    existing_identities: set[str] | None = None,
    min_pairs: int = 2,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Independently check teacher output before it becomes training data.

    A teacher response is not evidence by itself. Each pair must be non-empty,
    non-refusing, non-placeholder and novel compared with the store and with
    the rest of the batch. Only pairs that survive are allowed to be written
    with ``verifier_passed=True``.
    """
    from synapse.experience.store import training_fingerprint

    existing = set(existing_identities or ())
    accepted: list[dict[str, str]] = []
    seen_prompts: set[str] = set()
    seen_identities: set[str] = set()
    dropped = {
        "too_short": 0,
        "refusal": 0,
        "error_output": 0,
        "placeholder": 0,
        "echo": 0,
        "duplicate_prompt": 0,
        "duplicate_pair": 0,
        "already_learned": 0,
    }
    for raw_pair in pairs:
        if not isinstance(raw_pair, dict):
            dropped["too_short"] += 1
            continue
        prompt = _normalize_pair_text(raw_pair.get("prompt"))
        response = _normalize_pair_text(raw_pair.get("response"))
        if len(prompt) < _MIN_PROMPT_CHARS or len(response) < _MIN_RESPONSE_CHARS:
            dropped["too_short"] += 1
            continue
        lowered = response.casefold()
        if lowered in _PLACEHOLDER_RESPONSES:
            dropped["placeholder"] += 1
            continue
        if lowered.startswith(_REFUSAL_PREFIXES):
            dropped["refusal"] += 1
            continue
        if lowered.startswith(_ERROR_PREFIXES):
            dropped["error_output"] += 1
            continue
        if prompt.casefold() == response.casefold():
            dropped["echo"] += 1
            continue
        prompt_key = prompt.casefold()
        if prompt_key in seen_prompts:
            dropped["duplicate_prompt"] += 1
            continue
        identity = "text:" + training_fingerprint(
            f"User: {prompt}\nAssistant: {response}"
        )
        if identity in existing:
            dropped["already_learned"] += 1
            continue
        if identity in seen_identities:
            dropped["duplicate_pair"] += 1
            continue
        seen_prompts.add(prompt_key)
        seen_identities.add(identity)
        accepted.append({"prompt": prompt, "response": response, "identity": identity})

    report: dict[str, Any] = {
        "received": len(pairs),
        "accepted": len(accepted),
        "min_required": max(1, int(min_pairs)),
        "passed": len(accepted) >= max(1, int(min_pairs)),
        "dropped": {key: value for key, value in dropped.items() if value},
        "method": "learning_loop_pair_verifier",
    }
    return accepted, report


async def execute_learning_loop(ctx: ExecutionContext, topic: str = "", **params):
    """Run generate → snapshot → train cycles while the holdout loss improves."""
    from synapse.experience import DatasetSnapshotStore, ExperienceRecord, ExperienceStore
    from synapse.training import train_lora

    topic = str(topic or params.get("topic", "")).strip()
    if not topic:
        return {"success": False, "error": "learning topic is empty"}

    language = str(params.get("language", "Russian"))
    pairs_per_cycle = max(2, min(int(params.get("pairs_per_cycle", 8)), 64))
    max_cycles = max(1, min(int(params.get("max_cycles", 3)), 10))
    steps = max(1, min(int(params.get("steps", 4)), 200))
    require_gpu = bool(params.get("require_gpu", False))
    model_id = str(params.get("model_id", ""))
    teacher = str(params.get("teacher", "auto"))

    workspace_root = Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).expanduser().resolve()
    store = ExperienceStore(workspace_root / ".synapse" / "experience.sqlite3")
    snapshots = DatasetSnapshotStore(workspace_root / ".synapse" / "datasets")

    cycles: list[dict[str, Any]] = []
    adapter_path: str | None = None
    # One directory per learning session. The old fixed ``loop_01`` name made
    # every chat-driven run overwrite the previous adapter, erasing audit
    # evidence and replacing a promoted adapter with an unaudited one.
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    training_lock = TrainingLock(workspace_root / ".synapse" / "training.lock")
    try:
        for cycle_index in range(1, max_cycles + 1):
            pairs, teacher_evidence = await _generate_pairs(
                teacher, topic, language, pairs_per_cycle, workspace_root,
            )
            if not pairs:
                cycles.append({
                    "cycle": cycle_index,
                    "status": "blocked",
                    "blocker": "teacher_returned_no_valid_pairs",
                    "teacher": teacher_evidence,
                })
                break

            # Teacher output is a candidate, not verified experience. Pairs are
            # checked for emptiness, refusals, placeholders, duplicates and
            # novelty against the store before any record is marked passed.
            pairs, verification = _verify_pairs(
                pairs,
                existing_identities=store.training_identities(verified_only=False),
                min_pairs=min(2, pairs_per_cycle),
            )
            if not verification["passed"]:
                cycles.append({
                    "cycle": cycle_index,
                    "status": "blocked",
                    "blocker": "pairs_failed_verification",
                    "teacher": teacher_evidence,
                    "verification": verification,
                })
                break

            actual_teacher = str(teacher_evidence.get("teacher") or teacher)
            teacher_kind = str(teacher_evidence.get("kind") or "unknown")
            checks = [
                "non_empty", "not_refusal", "not_placeholder",
                "not_error_output", "not_echo", "novel", "unique_prompt",
            ]
            records = [
                ExperienceRecord(
                    task_id=f"learning_loop:{topic[:40]}",
                    run_id=f"cycle_{cycle_index}",
                    session_id=str(ctx.session_id or "learning_loop"),
                    objective=f"{topic} [{language}]",
                    inputs={
                        "cycle": cycle_index,
                        "teacher_requested": teacher,
                        "teacher_actual": actual_teacher,
                        "teacher_kind": teacher_kind,
                        "teacher_evidence": teacher_evidence,
                    },
                    executor="learning_loop",
                    model=f"teacher:{actual_teacher}",
                    execution_success=True,
                    verifier_passed=True,
                    verifier_status="passed",
                    eligibility="eligible",
                    feedback={
                        "training_text": f"User: {pair['prompt']}\nAssistant: {pair['response']}",
                        "learning_loop_verification": {
                            "method": verification["method"],
                            "checks": checks,
                            "identity": pair.get("identity"),
                        },
                    },
                    provenance={
                        "source": "chat_learning_loop",
                        "cycle": cycle_index,
                        "teacher": actual_teacher,
                        "teacher_kind": teacher_kind,
                        "pair_verification": {
                            "method": verification["method"],
                            "checks": checks,
                            "received": verification["received"],
                            "accepted": verification["accepted"],
                        },
                    },
                )
                for pair in pairs
            ]
            records, skipped_pairs = store.append_unique(records)
            if not records:
                cycles.append({
                    "cycle": cycle_index,
                    "status": "blocked",
                    "blocker": "all_pairs_already_learned",
                    "teacher": teacher_evidence,
                    "verification": verification,
                    "skipped_pairs": len(skipped_pairs),
                })
                break

            try:
                snapshot = snapshots.create(store, seed=cycle_index)
            except ValueError as exc:
                cycles.append({"cycle": cycle_index, "status": "blocked", "blocker": str(exc)})
                break

            resolved_model = model_id or _default_model_id()
            if not resolved_model:
                cycles.append({"cycle": cycle_index, "status": "blocked", "blocker": "no_downloaded_local_model"})
                break

            # A chat-driven loop must not start a second full training run
            # while the autonomous loop (or an operator endpoint) is already
            # training: two checkpoints in one process double peak memory and
            # race over adapter state. The learning pairs are already stored as
            # verified experience, so a blocked cycle loses no data.
            if not training_lock.acquire():
                cycles.append({
                    "cycle": cycle_index,
                    "status": "blocked",
                    "blocker": "training_running_in_another_process",
                    "teacher": teacher_evidence,
                    "pairs": len(pairs),
                })
                break
            try:
                result = train_lora(
                    experience_store=store,
                    snapshot=snapshot,
                    base_model=_model_local_path(resolved_model),
                    output_dir=(
                        workspace_root / ".synapse" / "adapters"
                        / f"loop_{run_stamp}_{cycle_index:02d}"
                    ),
                    steps=steps,
                    require_gpu=require_gpu,
                    metadata={
                        "origin": "learning_loop",
                        "topic": topic,
                        "teacher": actual_teacher,
                        "teacher_requested": teacher,
                        "teacher_kind": teacher_kind,
                        "cycle": cycle_index,
                    },
                )
            finally:
                training_lock.release()
            evidence = result.to_dict()
            cycles.append({
                "cycle": cycle_index,
                "teacher": teacher_evidence,
                "pairs": len(pairs),
                "stored_pairs": len(records),
                "skipped_pairs": len(skipped_pairs),
                "verification": verification,
                "status": evidence["status"],
                "final_loss": evidence.get("final_loss"),
                "holdout_loss_before": evidence.get("holdout_loss_before"),
                "holdout_loss_after": evidence.get("holdout_loss_after"),
                "promotion_status": evidence.get("promotion_status"),
                "blockers": list(evidence.get("blockers", ())),
                "error": evidence.get("error"),
            })
            if evidence["status"] != "completed":
                break
            adapter_path = evidence.get("adapter_path")
            if evidence.get("promotion_status") != "promoted":
                break  # holdout no longer improves; stop instead of overfitting

        completed = [item for item in cycles if item["status"] == "completed"]
        promoted = [item for item in completed if item.get("promotion_status") == "promoted"]
        payload = {
            "success": bool(completed),
            "topic": topic,
            "language": language,
            "cycles_run": len(cycles),
            "cycles_completed": len(completed),
            "cycles_promoted": len(promoted),
            "adapter_path": adapter_path,
            "cycles": cycles,
            "weights_modified": bool(promoted),
            "note": "LoRA adapter trained over verified snapshots; base weights are never altered.",
        }
        if not completed:
            # A blocked cycle (concurrent training, no valid teacher pairs, or
            # a snapshot that is too small) is not a crash. Preserve the real
            # blocker in the error field: the orchestrator otherwise replaces
            # it with a generic "Skill failed: learning_loop" and the evidence
            # in ``cycles`` is lost.
            blocked = next(
                (item for item in cycles if item.get("blocker") or item.get("error")),
                None,
            )
            blocker = (blocked or {}).get("blocker") or (blocked or {}).get("error")
            if blocker:
                payload["error"] = str(blocker)
        try:
            from synapse.growth import get_growth_network

            network = get_growth_network(workspace_root)
            network.record_execution(
                task=f"learn:{topic}",
                skill="learning_loop",
                provider="local_transformers",
                model=_default_model_id() or None,
                success=bool(completed),
                error=next(
                    (str(item.get("blocker") or item.get("error")) for item in cycles
                     if item.get("blocker") or item.get("error")),
                    None,
                ),
            )
            if promoted:
                network.consolidate()
        except Exception:
            # Learning evidence is already returned; growth bookkeeping must
            # not turn a successful training run into a failure.
            pass
        return payload
    finally:
        store.close()


def _default_model_id() -> str:
    from synapse.models import get_model_registry

    manifests = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    return manifests[0].model_id if manifests else ""


def _model_local_path(model_id: str) -> str:
    from synapse.models import get_model_registry

    manifest = get_model_registry().get(model_id)
    if manifest is None or not manifest.local_path:
        raise RuntimeError(f"model '{model_id}' is not downloaded")
    return manifest.local_path


__all__ = ["execute_learning_loop"]
