"""Immutable verified-only dataset snapshots built from ExperienceStore."""
from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synapse.experience.store import ExperienceRecord, ExperienceStore

PROTOCOL_VERSION = "1.0"


def _hash_payload(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DatasetSnapshot:
    snapshot_id: str
    schema_version: str
    source_record_ids: tuple[str, ...]
    train_ids: tuple[str, ...]
    dev_ids: tuple[str, ...]
    holdout_ids: tuple[str, ...]
    manifest_hash: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "schema_version": self.schema_version,
            "source_record_ids": list(self.source_record_ids),
            "train_ids": list(self.train_ids),
            "dev_ids": list(self.dev_ids),
            "holdout_ids": list(self.holdout_ids),
            "manifest_hash": self.manifest_hash,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "protocol_version": PROTOCOL_VERSION,
        }


class DatasetSnapshotStore:
    """Create and persist content-addressed snapshots without mutable splits."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        experience_store: ExperienceStore,
        *,
        seed: int = 0,
        train_ratio: float = 0.8,
        dev_ratio: float = 0.1,
        metadata: dict[str, Any] | None = None,
    ) -> DatasetSnapshot:
        if not 0 < train_ratio < 1 or not 0 <= dev_ratio < 1 or train_ratio + dev_ratio >= 1:
            raise ValueError("train_ratio and dev_ratio must leave a non-empty holdout split")
        records = experience_store.list_records(verified_only=True, limit=10000)
        if not records:
            raise ValueError("No verified experience records available for dataset snapshot")
        records = sorted(records, key=lambda record: record.record_hash)
        ids = [record.experience_id for record in records]
        shuffled = list(ids)
        random.Random(seed).shuffle(shuffled)
        train_end = max(1, int(len(shuffled) * train_ratio))
        dev_end = min(len(shuffled) - 1, train_end + max(1, int(len(shuffled) * dev_ratio)))
        train_ids = tuple(shuffled[:train_end])
        dev_ids = tuple(shuffled[train_end:dev_end])
        holdout_ids = tuple(shuffled[dev_end:])
        manifest = {
            "schema_version": "1.0",
            "source_record_ids": ids,
            "train_ids": list(train_ids),
            "dev_ids": list(dev_ids),
            "holdout_ids": list(holdout_ids),
            "seed": seed,
            "metadata": metadata or {},
        }
        snapshot = DatasetSnapshot(
            snapshot_id=f"ds_{uuid.uuid4().hex}",
            schema_version="1.0",
            source_record_ids=tuple(ids),
            train_ids=train_ids,
            dev_ids=dev_ids,
            holdout_ids=holdout_ids,
            manifest_hash=_hash_payload(manifest),
            created_at=datetime.now(UTC).isoformat(),
            metadata={**(metadata or {}), "seed": seed, "verified_record_count": len(records)},
        )
        path = self.root / f"{snapshot.snapshot_id}.json"
        path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot

    def list(self) -> list[dict[str, Any]]:
        """List persisted immutable snapshot manifests."""
        snapshots: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("ds_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                snapshots.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return snapshots

    def load(self, snapshot_id: str) -> DatasetSnapshot:
        path = self.root / f"{snapshot_id}.json"
        if not path.is_file():
            raise FileNotFoundError(snapshot_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.pop("protocol_version", None)
        return DatasetSnapshot(
            snapshot_id=payload["snapshot_id"],
            schema_version=payload["schema_version"],
            source_record_ids=tuple(payload["source_record_ids"]),
            train_ids=tuple(payload["train_ids"]),
            dev_ids=tuple(payload["dev_ids"]),
            holdout_ids=tuple(payload["holdout_ids"]),
            manifest_hash=payload["manifest_hash"],
            created_at=payload["created_at"],
            metadata=payload.get("metadata", {}),
        )


__all__ = ["DatasetSnapshot", "DatasetSnapshotStore", "PROTOCOL_VERSION"]
