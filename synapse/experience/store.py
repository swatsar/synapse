"""Canonical, provenance-preserving execution experience records.

Experience is evidence for evaluation and dataset construction. A record is
eligible for training only when execution and independent verification are
both explicit; a successful executor receipt alone is not a verifier result.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def training_fingerprint(text: str) -> str:
    """Stable fingerprint of a training text, insensitive to spacing/case.

    Repeated generations of the same instruction/response pair must not count
    as fresh experience: otherwise a looping teacher could keep the autonomy
    gate open with identical data.
    """
    normalized = " ".join(str(text or "").split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExperienceRecord:
    """Immutable-at-write evidence for one task/run execution."""

    experience_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex}")
    schema_version: str = "1.0"
    task_id: str = ""
    run_id: str = ""
    session_id: str = ""
    project_id: str | None = None
    objective: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    executor: str = ""
    provider: str | None = None
    model: str | None = None
    tool_versions: dict[str, str] = field(default_factory=dict)
    visible_events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    artifact_hashes: dict[str, str] = field(default_factory=dict)
    execution_success: bool = False
    verifier_passed: bool | None = None
    verifier_status: str = "inconclusive"
    feedback: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
    eligibility: str = "ineligible"
    provenance: dict[str, Any] = field(default_factory=dict)
    privacy: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    record_hash: str = ""

    def __post_init__(self) -> None:
        if not self.record_hash:
            payload = asdict(self)
            payload.pop("record_hash", None)
            object.__setattr__(self, "record_hash", _json_hash(payload))

    @property
    def verified_for_training(self) -> bool:
        return (
            self.execution_success
            and self.verifier_passed is True
            and self.verifier_status == "passed"
            and self.eligibility == "eligible"
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"verified_for_training": self.verified_for_training}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperienceRecord":
        values = dict(data)
        values.pop("verified_for_training", None)
        return cls(**values)


def training_text_of(record: ExperienceRecord) -> str:
    """Return the text a trainer would learn from, or an empty string."""
    feedback = record.feedback or {}
    for key in ("training_text", "candidate_training_text", "response"):
        value = feedback.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def training_identity(record: ExperienceRecord) -> str:
    """Identity used for novelty/dedup checks.

    Records without training text fall back to their immutable hash so they
    still count individually instead of collapsing into one empty text.
    """
    text = training_text_of(record)
    if text:
        return "text:" + training_fingerprint(text)
    return "record:" + str(record.record_hash or record.experience_id)


class ExperienceStore:
    """Durable SQLite store with verified-only query boundaries."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._db: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        if self._db is None:
            if self.db_path != ":memory:":
                Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            # The store is opened by the lifespan thread but written by HTTP
            # request threads and the autonomy worker.
            self._db = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=30.0,
            )
            self._db.row_factory = sqlite3.Row
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    record_hash TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL DEFAULT '',
                    execution_success INTEGER NOT NULL,
                    verifier_passed INTEGER,
                    verifier_status TEXT NOT NULL,
                    eligibility TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )"""
            )
            self._migrate_task_id_column()
            self._db.commit()
        return self._db

    def _migrate_task_id_column(self) -> None:
        """Add the indexed task_id column to stores created by older builds."""
        assert self._db is not None
        columns = {
            row[1] for row in self._db.execute("PRAGMA table_info(experiences)")
        }
        if "task_id" not in columns:
            self._db.execute(
                "ALTER TABLE experiences ADD COLUMN task_id TEXT NOT NULL DEFAULT ''"
            )
            rows = self._db.execute(
                "SELECT experience_id, payload_json FROM experiences"
            ).fetchall()
            for row in rows:
                try:
                    payload = json.loads(row[1])
                except ValueError:
                    continue
                self._db.execute(
                    "UPDATE experiences SET task_id=? WHERE experience_id=?",
                    (str(payload.get("task_id") or ""), row[0]),
                )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_experiences_task_id "
            "ON experiences(task_id)"
        )

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def _insert_locked(self, db: sqlite3.Connection, record: ExperienceRecord) -> None:
        db.execute(
            """INSERT INTO experiences(
                experience_id, record_hash, task_id, execution_success,
                verifier_passed, verifier_status, eligibility, created_at,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.experience_id,
                record.record_hash,
                record.task_id,
                int(record.execution_success),
                None if record.verifier_passed is None else int(record.verifier_passed),
                record.verifier_status,
                record.eligibility,
                record.created_at,
                json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True),
            ),
        )

    def append(self, record: ExperienceRecord) -> ExperienceRecord:
        with self._lock:
            db = self._connect()
            self._insert_locked(db, record)
            db.commit()
            return record

    def _training_identities_locked(
        self,
        db: sqlite3.Connection,
        *,
        verified_only: bool,
        limit: int = 10000,
    ) -> set[str]:
        query = "SELECT payload_json FROM experiences"
        if verified_only:
            query += " WHERE execution_success=1 AND verifier_passed=1 AND verifier_status='passed' AND eligibility='eligible'"
        query += " ORDER BY created_at DESC LIMIT ?"
        rows = db.execute(query, (max(1, min(limit, 100000)),)).fetchall()
        identities: set[str] = set()
        for row in rows:
            try:
                payload = json.loads(row[0])
            except ValueError:
                continue
            feedback = payload.get("feedback") or {}
            text = ""
            if isinstance(feedback, dict):
                for key in ("training_text", "candidate_training_text", "response"):
                    value = feedback.get(key)
                    if isinstance(value, str) and value.strip():
                        text = value.strip()
                        break
            if text:
                identities.add("text:" + training_fingerprint(text))
            else:
                identities.add(
                    "record:" + str(payload.get("record_hash") or payload.get("experience_id") or "")
                )
        return identities

    def training_identities(
        self, *, verified_only: bool = False, limit: int = 10000,
    ) -> set[str]:
        """Return dedup identities for stored training texts.

        The learning loop uses this before writing newly generated pairs so a
        cycle cannot re-add experience it has already learned.
        """
        with self._lock:
            return self._training_identities_locked(
                self._connect(), verified_only=verified_only, limit=limit,
            )

    def count_distinct_training(self, *, verified_only: bool = False) -> int:
        """Count unique training identities, not raw database rows."""
        return len(self.training_identities(verified_only=verified_only, limit=100000))

    def append_unique(
        self,
        records: list[ExperienceRecord],
        *,
        verified_only: bool = True,
    ) -> tuple[list[ExperienceRecord], list[ExperienceRecord]]:
        """Append only records whose training identity is not stored yet.

        Returns ``(accepted, skipped)``. The check and the inserts share one
        lock, so two writers cannot both add the same training text.
        """
        with self._lock:
            db = self._connect()
            existing = self._training_identities_locked(
                db, verified_only=verified_only, limit=100000,
            )
            accepted: list[ExperienceRecord] = []
            skipped: list[ExperienceRecord] = []
            for record in records:
                identity = training_identity(record)
                if identity in existing:
                    skipped.append(record)
                    continue
                existing.add(identity)
                self._insert_locked(db, record)
                accepted.append(record)
            db.commit()
            return accepted, skipped

    def list_records(self, *, verified_only: bool = False, limit: int = 1000) -> list[ExperienceRecord]:
        with self._lock:
            db = self._connect()
            query = "SELECT payload_json FROM experiences"
            params: list[Any] = []
            if verified_only:
                query += " WHERE execution_success=1 AND verifier_passed=1 AND verifier_status='passed' AND eligibility='eligible'"
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(max(1, min(limit, 10000)))
            rows = db.execute(query, params).fetchall()
            return [ExperienceRecord.from_dict(json.loads(row[0])) for row in rows]

    def get_records(self, experience_ids: list[str] | tuple[str, ...]) -> list[ExperienceRecord]:
        """Return records by immutable ids, preserving the requested order."""
        if not experience_ids:
            return []
        with self._lock:
            db = self._connect()
            placeholders = ",".join("?" for _ in experience_ids)
            rows = db.execute(
                f"SELECT payload_json FROM experiences WHERE experience_id IN ({placeholders})",  # noqa: S608
                list(experience_ids),
            ).fetchall()
            records = {record.experience_id: record for record in (
                ExperienceRecord.from_dict(json.loads(row[0])) for row in rows
            )}
            return [records[record_id] for record_id in experience_ids if record_id in records]

    def latest_for_task(self, task_id: str) -> ExperienceRecord | None:
        """Return the newest experience written for one task."""
        with self._lock:
            db = self._connect()
            row = db.execute(
                "SELECT payload_json FROM experiences WHERE task_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            return ExperienceRecord.from_dict(json.loads(row[0]))

    def apply_human_verification(
        self,
        task_id: str,
        *,
        passed: bool,
        note: str | None = None,
    ) -> ExperienceRecord | None:
        """Promote or reject the newest record for a task using human judgement.

        A human explicitly approving a real model answer is an independent
        verification signal. Rejection is recorded too, so the same answer is
        never reused as training data. Evidence is rewritten in place with a
        new content hash; the original record is not silently mutated.
        """
        from dataclasses import replace

        with self._lock:
            record = self.latest_for_task(task_id)
            if record is None:
                return None
            feedback = dict(record.feedback)
            candidate = (
                feedback.get("training_text")
                or feedback.get("candidate_training_text")
            )
            feedback["human_feedback"] = {
                "passed": bool(passed),
                "note": note or "",
            }
            if passed:
                if isinstance(candidate, str) and candidate.strip():
                    feedback["training_text"] = candidate
                verifier_passed = True
                verifier_status = "passed"
                eligible = bool(
                    record.execution_success
                    and isinstance(feedback.get("training_text"), str)
                    and feedback["training_text"].strip()
                )
                eligibility = "eligible" if eligible else "ineligible"
            else:
                feedback.pop("training_text", None)
                verifier_passed = False
                verifier_status = "failed"
                eligibility = "ineligible"
            provenance = dict(record.provenance)
            provenance["human_verification"] = {
                "passed": bool(passed),
                "note": note or "",
            }
            updated = replace(
                record,
                verifier_passed=verifier_passed,
                verifier_status=verifier_status,
                eligibility=eligibility,
                feedback=feedback,
                provenance=provenance,
                record_hash="",
            )
            db = self._connect()
            db.execute(
                """UPDATE experiences
                   SET record_hash=?, verifier_passed=?, verifier_status=?,
                       eligibility=?, payload_json=?
                   WHERE experience_id=?""",
                (
                    updated.record_hash,
                    int(updated.verifier_passed),
                    updated.verifier_status,
                    updated.eligibility,
                    json.dumps(updated.to_dict(), ensure_ascii=False, sort_keys=True),
                    updated.experience_id,
                ),
            )
            db.commit()
            return updated

    def count(self, *, verified_only: bool = False) -> int:
        with self._lock:
            db = self._connect()
            query = "SELECT COUNT(*) FROM experiences"
            if verified_only:
                query += " WHERE execution_success=1 AND verifier_passed=1 AND verifier_status='passed' AND eligibility='eligible'"
            return int(db.execute(query).fetchone()[0])


__all__ = [
    "ExperienceRecord",
    "ExperienceStore",
    "PROTOCOL_VERSION",
    "training_fingerprint",
    "training_identity",
    "training_text_of",
]
