"""
Persistent Memory Vault for Synapse v3.4.1.

Adapted from claude-mem patterns (thedotmack/claude-mem).
Provides long-term episodic memory, context distillation, project convention retention,
and semantic/keyword recall for cognitive cycle orchestration.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.memory.vault")


class MemoryType(str, Enum):
    USER = "user"                    # User preferences, working style, role
    FEEDBACK = "feedback"            # Corrections, confirmed approaches, why and how to apply
    PROJECT = "project"              # Project architectural constraints, deadlines, tech stack
    CONVENTION = "convention"        # Code styling, naming conventions, test practices
    REFERENCE = "reference"          # Pointers to external docs, tickets, schemas


@dataclass
class MemoryEntry:
    id: str
    title: str
    content: str
    memory_type: MemoryType
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    use_count: int = 0
    confidence: float = 1.0
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "use_count": self.use_count,
            "confidence": round(self.confidence, 2),
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        mtype = MemoryType(data.get("memory_type", "project"))
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", "Untitled Memory"),
            content=data.get("content", ""),
            memory_type=mtype,
            tags=data.get("tags", []),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            use_count=data.get("use_count", 0),
            confidence=data.get("confidence", 1.0),
            protocol_version=data.get("protocol_version", PROTOCOL_VERSION),
        )


class MemoryVault:
    """Persistent storage and semantic/keyword retrieval for agent long-term memories."""

    def __init__(self, storage_path: Optional[str | Path] = None):
        if storage_path:
            self.file_path = Path(storage_path).resolve()
        else:
            base_dir = Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())) / ".synapse"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.file_path = base_dir / "memory_vault.json"

        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        if not self.file_path.exists():
            # Seed default project memory
            self.create_entry(
                title="Windows Test Execution Convention",
                content="Always invoke pytest with --basetemp='F:/synapse-main/.pytest-run-tmp' to avoid Windows permission error [WinError 5] on pytest-current symlink.",
                memory_type=MemoryType.CONVENTION,
                tags=["windows", "pytest", "tests"],
            )
            return

        try:
            raw = json.loads(self.file_path.read_text(encoding="utf-8"))
            for item in raw.get("entries", []):
                entry = MemoryEntry.from_dict(item)
                self._entries[entry.id] = entry
        except Exception as e:
            logger.error("Failed to load memory vault from %s: %s", self.file_path, e)

    def _save(self) -> None:
        """Persist memories to disk."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": PROTOCOL_VERSION,
                "updated_at": datetime.now(UTC).isoformat(),
                "entries": [e.to_dict() for e in self._entries.values()],
            }
            self.file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save memory vault: %s", e)

    def create_entry(
        self,
        title: str,
        content: str,
        memory_type: MemoryType = MemoryType.PROJECT,
        tags: Optional[list[str]] = None,
        confidence: float = 1.0,
    ) -> MemoryEntry:
        """Create and store a new memory note."""
        entry_id = f"mem_{uuid.uuid4().hex[:12]}"
        entry = MemoryEntry(
            id=entry_id,
            title=title.strip(),
            content=content.strip(),
            memory_type=memory_type,
            tags=tags or [],
            confidence=confidence,
        )
        self._entries[entry.id] = entry
        self._save()
        return entry

    def get_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._entries.get(entry_id)

    def list_entries(self, memory_type: Optional[MemoryType] = None) -> list[MemoryEntry]:
        entries = list(self._entries.values())
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        return sorted(entries, key=lambda x: x.updated_at, reverse=True)

    def update_entry(
        self,
        entry_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[MemoryEntry]:
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        if title is not None:
            entry.title = title.strip()
        if content is not None:
            entry.content = content.strip()
        if memory_type is not None:
            entry.memory_type = memory_type
        if tags is not None:
            entry.tags = tags
        entry.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return entry

    def delete_entry(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save()
            return True
        return False

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Hybrid keyword and token relevance search across memory entries."""
        if not query.strip():
            return self.list_entries()[:limit]

        q_terms = set(re.findall(r"\w+", query.lower()))
        scored: list[tuple[float, MemoryEntry]] = []

        for entry in self._entries.values():
            score = 0.0
            # Title match weight
            title_terms = set(re.findall(r"\w+", entry.title.lower()))
            common_title = q_terms.intersection(title_terms)
            score += len(common_title) * 3.0

            # Content match weight
            content_terms = set(re.findall(r"\w+", entry.content.lower()))
            common_content = q_terms.intersection(content_terms)
            score += len(common_content) * 1.0

            # Tag match weight
            for tag in entry.tags:
                if any(t in tag.lower() for t in q_terms):
                    score += 2.0

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored[:limit]]
        for r in results:
            r.use_count += 1
        if results:
            self._save()
        return results

    def distill_from_interaction(self, user_prompt: str, assistant_response: str) -> Optional[MemoryEntry]:
        """Analyze turn outcome and automatically extract lasting learnings."""
        text = f"{user_prompt}\n{assistant_response}".lower()

        # Check for explicit correction patterns
        if any(marker in text for marker in ["remember", "always use", "never use", "correction:", "запомни", "всегда используй"]):
            title = f"Distilled rule: {user_prompt[:50]}"
            entry = self.create_entry(
                title=title,
                content=assistant_response[:300],
                memory_type=MemoryType.FEEDBACK,
                tags=["distilled", "auto-learning"],
                confidence=0.9,
            )
            return entry
        return None


_default_vault: Optional[MemoryVault] = None


def get_memory_vault(storage_path: Optional[str | Path] = None) -> MemoryVault:
    global _default_vault
    if _default_vault is None:
        _default_vault = MemoryVault(storage_path)
    return _default_vault
