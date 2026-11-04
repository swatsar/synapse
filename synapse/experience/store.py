"""Canonical, provenance-preserving execution experience records.

Experience is evidence for evaluation and dataset construction. A record is
eligible for training only when execution and independent verification are
both explicit; a successful executor receipt alone is not a verifier result.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
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


class ExperienceStore:
    """Durable SQLite store with verified-only query boundaries."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._db: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._db is None:
            if self.db_path != ":memory:":
                Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.db_path)
            self._db.row_factory = sqlite3.Row
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    record_hash TEXT NOT NULL UNIQUE,
                    execution_success INTEGER NOT NULL,
                    verifier_passed INTEGER,
                    verifier_status TEXT NOT NULL,
                    eligibility TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )"""
            )
            self._db.commit()
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def append(self, record: ExperienceRecord) -> ExperienceRecord:
        db = self._connect()
        db.execute(
            """INSERT INTO experiences(
                experience_id, record_hash, execution_success, verifier_passed,
                verifier_status, eligibility, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.experience_id,
                record.record_hash,
                int(record.execution_success),
                None if record.verifier_passed is None else int(record.verifier_passed),
                record.verifier_status,
                record.eligibility,
                record.created_at,
                json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True),
            ),
        )
        db.commit()
        return record

    def list_records(self, *, verified_only: bool = False, limit: int = 1000) -> list[ExperienceRecord]:
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

    def count(self, *, verified_only: bool = False) -> int:
        db = self._connect()
        query = "SELECT COUNT(*) FROM experiences"
        if verified_only:
            query += " WHERE execution_success=1 AND verifier_passed=1 AND verifier_status='passed' AND eligibility='eligible'"
        return int(db.execute(query).fetchone()[0])


__all__ = ["ExperienceRecord", "ExperienceStore", "PROTOCOL_VERSION"]
