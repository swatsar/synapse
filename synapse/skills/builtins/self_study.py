"""Grounded self-study: turn project documentation into verified experience.

Autonomous training must not depend forever on an external teacher (which can
be quota-limited) or on a human approving every answer. It also must not train
on the model's own unverified generations -- that is how a model learns its own
mistakes. This module extracts short factual units from *trusted project
documentation* and re-verifies each unit against the source file before it is
written to the experience store.

The result is real instruction data with a provenance chain:

    document -> section/definition -> question + answer -> source containment

Only units that still exist in the source after re-reading are recorded as
eligible for training. Nothing here calls a model, so there is no hidden
self-distillation loop.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import hashlib
import re
from pathlib import Path
from typing import Any

from synapse.core.models import ExecutionContext

_MAX_SOURCE_BYTES = 1_000_000
_MAX_ANSWER_CHARS = 700
_MIN_ANSWER_CHARS = 40
_MIN_WORDS = 8
_MAX_TITLE_CHARS = 120

# Root documents that define the product are the most valuable teaching
# material; supporting docs follow. Release notes are deliberately excluded:
# they describe history, not current behaviour.
_ROOT_DOCS = ("README.md", "ARCHITECTURE.md", "SPECIFICATION.md", "SECURITY.md")
_DOC_DIRS = (
    "docs/user",
    "docs/developer",
    "docs/architecture",
    "docs/integrations",
    "docs/admin",
    "docs",
)
_SKIP_NAMES = {"CHANGELOG.md", "LICENSE.md", "CONTRIBUTING.md"}
_SKIP_PARTS = {".git", ".synapse", "node_modules", ".venv", "venv", "__pycache__"}

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_DEFINITION = re.compile(
    r"^\s*(?:[-*+]\s*)?\*\*(?P<term>[^*\n]{2,80})\*\*\s*[—–:-]\s*(?P<definition>.{20,})$"
)
_TABLE_RULE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]+\|?\s*$")
_BAD_HEADINGS = {
    "содержание", "оглавление", "table of contents", "contents", "toc",
    "лицензия", "license", "благодарности", "acknowledgements",
}


def _workspace(ctx: ExecutionContext, path: str = ".") -> Path:
    root = None
    if ctx.memory_store is not None:
        root = getattr(ctx.memory_store, "workspace_root", None)
    candidate = Path(path or ".").expanduser()
    if root is not None and not candidate.is_absolute():
        candidate = Path(root) / candidate
    return candidate.resolve()


def _clean(text: str) -> str:
    """Normalise markdown into stable prose while keeping sentence content."""
    text = _HTML_COMMENT.sub(" ", text)
    text = _FENCE.sub(" ", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    lines: list[str] = []
    for line in text.splitlines():
        if _HEADING.match(line) or _TABLE_RULE.match(line):
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith((">", "|")):
            stripped = stripped.lstrip(">|").strip()
        stripped = stripped.replace("**", "").replace("__", "").replace("`", "")
        if stripped:
            lines.append(stripped)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _truncate_at_sentence(text: str, limit: int = _MAX_ANSWER_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if boundary >= _MIN_ANSWER_CHARS:
        return cut[: boundary + 1].strip()
    return cut.rsplit(" ", 1)[0].strip()


def _looks_informative(text: str) -> bool:
    if not (_MIN_ANSWER_CHARS <= len(text) <= _MAX_ANSWER_CHARS * 4):
        return False
    words = [word for word in text.split() if any(ch.isalpha() for ch in word)]
    return len(words) >= _MIN_WORDS


def _sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) pairs, including a preamble."""
    sections: list[tuple[str, list[str]]] = [("Обзор", [])]
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            title = _clean(match.group(2))[:_MAX_TITLE_CHARS]
            if title:
                sections.append((title, []))
            continue
        sections[-1][1].append(line)
    return [(title, "\n".join(body)) for title, body in sections]


def _candidate_paths(workspace: Path, sources: list[str] | None) -> list[Path]:
    if sources:
        requested = [Path(item.strip()) for item in sources if str(item).strip()]
    else:
        requested = [Path(name) for name in _ROOT_DOCS]
        for directory in _DOC_DIRS:
            base = workspace / directory
            if base.is_dir():
                requested.extend(sorted(base.glob("*.md")))
    seen: set[str] = set()
    candidates: list[Path] = []
    for item in requested:
        candidate = item if item.is_absolute() else workspace / item
        try:
            resolved = candidate.resolve()
            resolved.relative_to(workspace)
        except (OSError, ValueError):
            continue
        key = str(resolved).casefold()
        if key in seen:
            continue
        seen.add(key)
        if not resolved.is_file() or resolved.suffix.lower() != ".md":
            continue
        if resolved.name in _SKIP_NAMES:
            continue
        if any(part in _SKIP_PARTS for part in resolved.parts):
            continue
        candidates.append(resolved)
    return candidates


def _source_units(relpath: str, text: str) -> list[dict[str, str]]:
    """Extract definitions first, then section summaries."""
    units: list[dict[str, str]] = []
    seen_questions: set[str] = set()
    sections = _sections(text)

    # Definitions are the highest-signal teaching units: a term and its
    # definition are exactly the shape of a good instruction/answer pair.
    for heading, body in sections:
        for line in body.splitlines():
            match = _DEFINITION.match(line)
            if not match:
                continue
            term = _clean(match.group("term"))
            definition = _clean(match.group("definition"))
            if not term or not _looks_informative(definition):
                continue
            question = f"Что такое «{term}» в проекте Synapse?"
            if question in seen_questions:
                continue
            seen_questions.add(question)
            units.append({
                "kind": "definition",
                "question": question,
                "answer": _truncate_at_sentence(definition),
                "heading": heading,
                "source": relpath,
            })

    for heading, body in sections:
        if heading.casefold() in _BAD_HEADINGS:
            continue
        cleaned = _clean(body)
        if not _looks_informative(cleaned):
            continue
        question = f"Что документация Synapse сообщает о разделе «{heading}»?"
        if question in seen_questions:
            continue
        seen_questions.add(question)
        units.append({
            "kind": "section",
            "question": question,
            "answer": _truncate_at_sentence(cleaned),
            "heading": heading,
            "source": relpath,
        })
    return units


def _verify_against_source(
    workspace: Path, relpath: str, answer: str, content_hash: str,
) -> tuple[bool, str | None]:
    """Re-read the document and prove the answer is still in it."""
    path = workspace / relpath
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, "source_unreadable"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if digest != content_hash:
        return False, "source_changed"
    if answer not in _clean(raw):
        return False, "answer_not_in_source"
    return True, None


def _record_id(relpath: str, content_hash: str, question: str) -> str:
    raw = f"{relpath}\x00{content_hash}\x00{question}"
    return "exp_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def collect_grounded_experience(
    workspace_root: str | Path,
    *,
    max_records: int = 8,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Create verified training experience from trusted documentation.

    Every returned record passed source re-reading and containment. Callers
    can run this repeatedly: records are content-addressed, so an unchanged
    document is never duplicated.
    """
    from synapse.experience import ExperienceRecord, ExperienceStore

    workspace = Path(workspace_root).expanduser().resolve()
    limit = max(1, min(int(max_records), 64))
    store = ExperienceStore(workspace / ".synapse" / "experience.sqlite3")
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    documents: list[str] = []
    try:
        for path in _candidate_paths(workspace, sources):
            if len(created) >= limit:
                break
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                skipped.append({"source": str(path), "reason": f"unreadable:{exc}"})
                continue
            if len(raw.encode("utf-8", errors="replace")) > _MAX_SOURCE_BYTES:
                skipped.append({"source": str(path), "reason": "source_too_large"})
                continue
            relpath = path.relative_to(workspace).as_posix()
            content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            documents.append(relpath)
            for unit in _source_units(relpath, raw):
                if len(created) >= limit:
                    break
                answer = unit["answer"]
                if not _looks_informative(answer):
                    skipped.append({"source": relpath, "reason": "answer_too_short"})
                    continue
                verified, reason = _verify_against_source(
                    workspace, relpath, answer, content_hash,
                )
                if not verified:
                    skipped.append({"source": relpath, "reason": str(reason)})
                    continue
                experience_id = _record_id(relpath, content_hash, unit["question"])
                try:
                    existing = store.get_records([experience_id])
                except Exception:
                    existing = []
                if existing:
                    skipped.append({"source": relpath, "reason": "duplicate"})
                    continue
                record = ExperienceRecord(
                    experience_id=experience_id,
                    task_id=f"self_study:{relpath}#{unit['kind']}",
                    run_id=f"self_study:{content_hash[:12]}",
                    session_id="autonomy:self_study",
                    objective=unit["question"],
                    inputs={
                        "source": relpath,
                        "heading": unit["heading"],
                        "kind": unit["kind"],
                        "content_sha256": content_hash,
                    },
                    executor="grounded_self_study",
                    provider="documentation",
                    model=None,
                    execution_success=True,
                    verifier_passed=True,
                    verifier_status="passed",
                    eligibility="eligible",
                    feedback={
                        "training_text": (
                            f"User: {unit['question']}\nAssistant: {answer}"
                        ),
                        "verification": {
                            "status": "passed",
                            "method": "source_containment",
                            "source": relpath,
                            "checks": [{
                                "criterion": f"source_contains:{relpath}",
                                "passed": True,
                            }],
                        },
                        "grounded": True,
                    },
                    provenance={
                        "source": "grounded_self_study",
                        "document": relpath,
                        "content_sha256": content_hash,
                        "generator": "extractive_v1",
                        "question_kind": unit["kind"],
                    },
                )
                store.append(record)
                created.append({
                    "experience_id": experience_id,
                    "source": relpath,
                    "kind": unit["kind"],
                    "question": unit["question"],
                    "answer_chars": len(answer),
                })
    finally:
        store.close()
    result = {
        "success": bool(created),
        "created": len(created),
        "skipped": len(skipped),
        "documents": documents,
        "records": created,
        "skipped_details": skipped[:20],
        "note": (
            "Records are extracted from project documentation and re-verified "
            "against the source file; no model generated them."
        ),
        "protocol_version": PROTOCOL_VERSION,
    }
    result["content"] = _narrative(result)
    return result


def _narrative(result: dict[str, Any]) -> str:
    """Human-readable summary shared by the API and the skill entry point."""
    created = int(result.get("created") or 0)
    if created:
        return (
            "Из документации извлечено и повторно проверено "
            f"{created} обучающих фактов из {len(result.get('documents') or [])} файлов. "
            f"Пропущено: {int(result.get('skipped') or 0)} "
            "(дубликаты или устаревший текст)."
        )
    return (
        "Новых проверенных фактов в документации не найдено: "
        "все извлечённые единицы уже изучены или не прошли проверку по источнику."
    )


async def execute_self_study(
    ctx: ExecutionContext,
    path: str = ".",
    max_records: int = 8,
    sources: list[str] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Skill entry point: learn grounded facts from the project's own docs."""
    if not any(value.startswith("fs:read") for value in ctx.capabilities):
        return {"success": False, "error": "Capability denied: fs:read"}
    workspace = _workspace(ctx, path)
    try:
        result = collect_grounded_experience(
            workspace, max_records=max_records, sources=sources,
        )
    except Exception as exc:  # pragma: no cover - defensive, surfaced honestly
        return {
            "success": False,
            "error": f"Self-study failed: {exc}",
            "protocol_version": PROTOCOL_VERSION,
        }
    return result


__all__ = ["collect_grounded_experience", "execute_self_study", "PROTOCOL_VERSION"]
