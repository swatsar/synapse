"""Mycelial growth network for Synapse.

The network is the persistent, growing substrate behind the cognitive cycle.
Every execution sprouts or strengthens paths between what was attempted
(``task``), what executed it (``skill``) and what answered (``provider`` /
``model``). Successful paths are myelinated (fast paths), failures inhibit
them, unused paths decay and are pruned during consolidation — the same
forget/consolidate rhythm the brain uses and the same branching/merging
structure a mycelium uses.

This module is intentionally dependency-free (SQLite only) so it works in the
main process, in workers and in tests.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import hashlib
import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Hebbian plasticity: repeated co-activation strengthens a path, failure
# inhibits it. Numbers are deliberately conservative so one lucky run cannot
# permanently dominate routing.
_SUCCESS_DELTA = 0.25
_FAILURE_DELTA = -0.35
_MIN_WEIGHT = 0.01
_MAX_WEIGHT = 10.0
_MYELINATE_SUCCESSES = 3
_MYELINATE_WEIGHT = 0.8
_PRUNE_WEIGHT = 0.05
_DECAY = 0.97
_REPLAY_GAIN = 1.05
_AUTO_CONSOLIDATE_EVERY = 25


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize(label: str, *, limit: int = 240) -> str:
    return " ".join(str(label or "").strip().lower().split())[:limit]


def _node_id(kind: str, label: str) -> str:
    digest = hashlib.sha256(f"{kind}\x00{label}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)
_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "task", "step",
    "для", "что", "как", "это", "или", "при", "над", "под", "все", "его",
}


def _tokens(label: str) -> set[str]:
    return {
        word for word in _WORD_RE.findall(str(label or "").lower())
        if len(word) > 2 and word not in _STOPWORDS
    }


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


class GrowthNetwork:
    """Durable graph of tasks, skills, providers and their learned paths."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        # An in-memory database lives exactly as long as its connection, so it
        # must be cached. File-backed databases are opened per operation: on
        # Windows an idle cached handle locks the file and prevents workspace
        # cleanup (and SQLite connections must not be shared across threads).
        if self.db_path == ":memory:" and self._db is not None:
            return self._db
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        db.row_factory = sqlite3.Row
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0.0,
                activations INTEGER NOT NULL DEFAULT 0,
                successes INTEGER NOT NULL DEFAULT 0,
                failures INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
                src TEXT NOT NULL,
                dst TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0.1,
                successes INTEGER NOT NULL DEFAULT 0,
                failures INTEGER NOT NULL DEFAULT 0,
                myelinated INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT NOT NULL,
                PRIMARY KEY (src, dst, relation)
            );
            CREATE TABLE IF NOT EXISTS consolidations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                summary_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        db.commit()
        if self.db_path == ":memory:":
            self._db = db
        return db

    @contextmanager
    def _session(self):
        """Yield a connection and always release it (except for :memory:)."""
        db = self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            if self.db_path != ":memory:":
                db.close()

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def _counter(self, db: sqlite3.Connection, key: str) -> int:
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return int(row[0]) if row else 0

    def _set_counter(self, db: sqlite3.Connection, key: str, value: int) -> None:
        db.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    def _upsert_node(
        self,
        db: sqlite3.Connection,
        kind: str,
        label: str,
        *,
        success: bool | None = None,
    ) -> str:
        normalized = _normalize(label)
        node_id = _node_id(kind, normalized)
        timestamp = _now()
        db.execute(
            """INSERT INTO nodes(node_id, kind, label, weight, activations, successes, failures, created_at, last_seen)
               VALUES(?, ?, ?, 0.1, 1, ?, ?, ?, ?)
               ON CONFLICT(node_id) DO UPDATE SET
                   activations = activations + 1,
                   successes = successes + ?,
                   failures = failures + ?,
                   last_seen = ?
            """,
            (
                node_id, kind, normalized,
                int(success is True), int(success is False),
                timestamp, timestamp,
                int(success is True), int(success is False), timestamp,
            ),
        )
        return node_id

    def _upsert_edge(
        self,
        db: sqlite3.Connection,
        src: str,
        dst: str,
        relation: str,
        *,
        success: bool,
    ) -> None:
        delta = _SUCCESS_DELTA if success else _FAILURE_DELTA
        timestamp = _now()
        row = db.execute(
            "SELECT weight, successes, failures FROM edges WHERE src=? AND dst=? AND relation=?",
            (src, dst, relation),
        ).fetchone()
        if row is None:
            weight = max(_MIN_WEIGHT, min(_MAX_WEIGHT, 0.1 + delta))
            successes = int(success)
            failures = int(not success)
        else:
            weight = max(_MIN_WEIGHT, min(_MAX_WEIGHT, float(row["weight"]) + delta))
            successes = int(row["successes"]) + int(success)
            failures = int(row["failures"]) + int(not success)
        myelinated = int(successes >= _MYELINATE_SUCCESSES and weight >= _MYELINATE_WEIGHT)
        db.execute(
            """INSERT INTO edges(src, dst, relation, weight, successes, failures, myelinated, last_seen)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(src, dst, relation) DO UPDATE SET
                   weight=excluded.weight,
                   successes=excluded.successes,
                   failures=excluded.failures,
                   myelinated=excluded.myelinated,
                   last_seen=excluded.last_seen
            """,
            (src, dst, relation, weight, successes, failures, myelinated, timestamp),
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def record_execution(
        self,
        *,
        task: str,
        skill: str,
        provider: str | None = None,
        model: str | None = None,
        success: bool,
        error: str | None = None,
        latency_ms: float | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Sprout/strengthen the paths activated by one execution."""
        if not str(task or "").strip():
            task = "unspecified task"
        if not str(skill or "").strip():
            skill = "unknown_skill"
        record = {
            "task": str(task)[:1000],
            "skill": str(skill),
            "provider": str(provider) if provider else "",
            "model": str(model) if model else "",
            "success": bool(success),
            "error": (str(error)[:1000] if error else None),
            "latency_ms": float(latency_ms) if latency_ms is not None else None,
            "session_id": session_id,
        }
        with self._lock, self._session() as db:
            task_id = self._upsert_node(db, "task", record["task"], success=success)
            skill_id = self._upsert_node(db, "skill", record["skill"], success=success)
            self._upsert_edge(db, task_id, skill_id, "activates", success=success)
            provider_id = None
            if record["provider"]:
                provider_id = self._upsert_node(db, "provider", record["provider"], success=success)
                self._upsert_edge(db, skill_id, provider_id, "runs_on", success=success)
                self._upsert_edge(db, task_id, provider_id, "answered_by", success=success)
            if record["model"]:
                model_id = self._upsert_node(db, "model", record["model"], success=success)
                if provider_id:
                    self._upsert_edge(db, provider_id, model_id, "serves", success=success)
                self._upsert_edge(db, task_id, model_id, "answered_by", success=success)
            events = self._counter(db, "events") + 1
            self._set_counter(db, "events", events)
            summary = self._summarize_row(db, task_id)

        try:
            from synapse.observability.logger import audit

            audit(
                event="growth_path_recorded",
                task=record["task"][:120],
                skill=record["skill"],
                provider=record["provider"] or None,
                success=record["success"],
                mycelial_events=events,
            )
        except Exception:
            pass

        if events % _AUTO_CONSOLIDATE_EVERY == 0:
            try:
                self.consolidate()
            except Exception:
                pass
        return {
            "success": True,
            "task_node": task_id,
            "skill_node": skill_id,
            "events": events,
            "task_node_state": summary,
            "protocol_version": PROTOCOL_VERSION,
        }

    def record_coactivation(
        self,
        *,
        task: str,
        skills: list[str],
        success: bool = True,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Link skills that fired together in one task (associative mycelium).

        Co-activation is the skill-level analogue of Hebbian learning: paths
        that participate in the same successful task are connected, so recalling
        one skill can suggest its partners even when the planner names neither.
        """
        unique = list(dict.fromkeys(
            str(item or "").strip() for item in skills if str(item or "").strip()
        ))
        if len(unique) < 2:
            return {
                "success": True,
                "coactivations": 0,
                "events": self.status().get("events", 0),
                "protocol_version": PROTOCOL_VERSION,
            }
        with self._lock, self._session() as db:
            node_ids = {
                skill: self._upsert_node(db, "skill", skill, success=success)
                for skill in unique
            }
            coactivations = 0
            for index, source in enumerate(unique):
                for target in unique[index + 1:]:
                    self._upsert_edge(
                        db, node_ids[source], node_ids[target],
                        "co_activates", success=success,
                    )
                    self._upsert_edge(
                        db, node_ids[target], node_ids[source],
                        "co_activates", success=success,
                    )
                    coactivations += 1
            events = self._counter(db, "events") + 1
            self._set_counter(db, "events", events)
        try:
            from synapse.observability.logger import audit

            audit(
                event="growth_coactivation_recorded",
                task=str(task or "")[:120],
                skills=unique,
                coactivations=coactivations,
                success=bool(success),
                session_id=session_id,
            )
        except Exception:
            pass
        if events % _AUTO_CONSOLIDATE_EVERY == 0:
            try:
                self.consolidate()
            except Exception:
                pass
        return {
            "success": True,
            "skills": unique,
            "coactivations": coactivations,
            "events": events,
            "protocol_version": PROTOCOL_VERSION,
        }

    @staticmethod
    def _summarize_row(db: sqlite3.Connection, node_id: str) -> dict[str, Any]:
        row = db.execute(
            "SELECT kind, label, weight, activations, successes, failures FROM nodes WHERE node_id=?",
            (node_id,),
        ).fetchone()
        if row is None:
            return {}
        return {
            "kind": row["kind"],
            "label": row["label"],
            "weight": round(float(row["weight"]), 4),
            "activations": int(row["activations"]),
            "successes": int(row["successes"]),
            "failures": int(row["failures"]),
        }

    # ------------------------------------------------------------------
    # Consolidation: decay, prune, myelinate, summarise
    # ------------------------------------------------------------------

    def consolidate(self) -> dict[str, Any]:
        """One sleep-like consolidation pass over the whole network."""
        with self._lock, self._session() as db:
            now = _now()
            # 1. Replay learned fast paths. This is the consolidation half of
            #    memory: success-dominated myelinated paths are re-activated
            #    before decay, so repeated use keeps them strong while unused
            #    paths still fade.
            replayed = int(db.execute(
                "SELECT COUNT(*) FROM edges WHERE myelinated=1 AND successes > failures"
            ).fetchone()[0])
            db.execute(
                "UPDATE edges SET weight = MIN(?, weight * ?) "
                "WHERE myelinated=1 AND successes > failures",
                (_MAX_WEIGHT, _REPLAY_GAIN),
            )
            # 2. Decay every edge; unused paths fade.
            db.execute("UPDATE edges SET weight = MAX(?, weight * ?)", (_MIN_WEIGHT, _DECAY))
            # 3. Prune paths that are both weak and failure-dominated.
            db.execute(
                "DELETE FROM edges WHERE weight <= ? AND failures > successes",
                (_PRUNE_WEIGHT,),
            )
            # 4. Recompute node weights from incident edges.
            db.execute(
                """UPDATE nodes SET weight = COALESCE((
                       SELECT SUM(weight) FROM edges WHERE src=nodes.node_id OR dst=nodes.node_id
                   ), 0.0)"""
            )
            # 5. Read the consolidated state.
            hubs = self._query_nodes(db, order="hub", limit=10)
            fast_paths = self._query_edges(db, myelinated_only=True, limit=10)
            weak_paths = self._query_edges(db, weak_only=True, limit=10)
            edge_count = int(db.execute("SELECT COUNT(*) FROM edges").fetchone()[0])
            node_count = int(db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
            events = self._counter(db, "events")
            passes = self._counter(db, "consolidations") + 1
            self._set_counter(db, "consolidations", passes)
            summary = {
                "pass": passes,
                "events": events,
                "nodes": node_count,
                "edges": edge_count,
                "replayed_paths": replayed,
                "replay_gain": _REPLAY_GAIN,
                "hubs": hubs,
                "fast_paths": fast_paths,
                "weak_paths": weak_paths,
                "weak_paths_count": len(weak_paths),
                "created_at": now,
                "protocol_version": PROTOCOL_VERSION,
            }
            db.execute(
                "INSERT INTO consolidations(created_at, summary_json) VALUES(?, ?)",
                (now, json.dumps(summary, ensure_ascii=False, sort_keys=True)),
            )
            db.commit()
        try:
            from synapse.observability.logger import audit

            audit(
                event="growth_consolidated",
                pass_number=summary["pass"],
                nodes=summary["nodes"],
                edges=summary["edges"],
                fast_paths=len(summary["fast_paths"]),
                weak_paths=len(summary["weak_paths"]),
            )
        except Exception:
            pass
        return summary

    # ------------------------------------------------------------------
    # Read models
    # ------------------------------------------------------------------

    def _query_nodes(
        self,
        db: sqlite3.Connection,
        *,
        order: str = "hub",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        order_sql = (
            "weight * (1.0 + (successes * 2.0) / (failures + 1.0)) DESC"
            if order == "hub"
            else "last_seen DESC"
        )
        rows = db.execute(
            f"SELECT * FROM nodes ORDER BY {order_sql} LIMIT ?",  # noqa: S608
            (max(1, min(limit, 200)),),
        ).fetchall()
        return [
            {
                "id": row["node_id"],
                "kind": row["kind"],
                "label": row["label"],
                "weight": round(float(row["weight"]), 4),
                "activations": int(row["activations"]),
                "successes": int(row["successes"]),
                "failures": int(row["failures"]),
                "last_seen": row["last_seen"],
            }
            for row in rows
        ]

    def _query_edges(
        self,
        db: sqlite3.Connection,
        *,
        myelinated_only: bool = False,
        weak_only: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if myelinated_only:
            rows = db.execute(
                """SELECT e.*, s.label AS src_label, d.label AS dst_label
                   FROM edges e
                   JOIN nodes s ON s.node_id=e.src
                   JOIN nodes d ON d.node_id=e.dst
                   WHERE e.myelinated=1
                   ORDER BY e.weight DESC LIMIT ?""",
                (max(1, min(limit, 200)),),
            ).fetchall()
        elif weak_only:
            rows = db.execute(
                """SELECT e.*, s.label AS src_label, d.label AS dst_label
                   FROM edges e
                   JOIN nodes s ON s.node_id=e.src
                   JOIN nodes d ON d.node_id=e.dst
                   WHERE e.failures >= 2 AND e.failures > e.successes
                   ORDER BY e.failures DESC, e.weight ASC LIMIT ?""",
                (max(1, min(limit, 200)),),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT e.*, s.label AS src_label, d.label AS dst_label
                   FROM edges e
                   JOIN nodes s ON s.node_id=e.src
                   JOIN nodes d ON d.node_id=e.dst
                   ORDER BY e.weight DESC LIMIT ?""",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [
            {
                "source": row["src_label"],
                "target": row["dst_label"],
                "source_id": row["src"],
                "target_id": row["dst"],
                "relation": row["relation"],
                "weight": round(float(row["weight"]), 4),
                "successes": int(row["successes"]),
                "failures": int(row["failures"]),
                "myelinated": bool(row["myelinated"]),
                "last_seen": row["last_seen"],
            }
            for row in rows
        ]

    def status(self) -> dict[str, Any]:
        """Summarise the growing network without mutating it."""
        with self._lock, self._session() as db:
            node_count = int(db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
            edge_count = int(db.execute("SELECT COUNT(*) FROM edges").fetchone()[0])
            myelinated = int(
                db.execute("SELECT COUNT(*) FROM edges WHERE myelinated=1").fetchone()[0]
            )
            coactivations = int(
                db.execute(
                    "SELECT COUNT(*) FROM edges WHERE relation='co_activates'"
                ).fetchone()[0]
            )
            events = self._counter(db, "events")
            passes = self._counter(db, "consolidations")
            by_kind = {
                row["kind"]: int(row["count"])
                for row in db.execute(
                    "SELECT kind, COUNT(*) AS count FROM nodes GROUP BY kind"
                ).fetchall()
            }
            hubs = self._query_nodes(db, order="hub", limit=8)
            fast_paths = self._query_edges(db, myelinated_only=True, limit=8)
            weak_paths = self._query_edges(db, weak_only=True, limit=8)
            last_consolidation = db.execute(
                "SELECT summary_json FROM consolidations ORDER BY id DESC LIMIT 1"
            ).fetchone()
        last_summary = None
        if last_consolidation is not None:
            try:
                last_summary = json.loads(last_consolidation["summary_json"])
            except ValueError:
                last_summary = None
        return {
            "status": "growing" if node_count else "empty",
            "db_path": self.db_path,
            "events": events,
            "consolidation_passes": passes,
            "nodes": node_count,
            "edges": edge_count,
            "nodes_by_kind": by_kind,
            "myelinated_paths": myelinated,
            "coactivation_paths": coactivations,
            "hubs": hubs,
            "fast_paths": fast_paths,
            "weak_paths": weak_paths,
            "last_consolidation": last_summary,
            "protocol_version": PROTOCOL_VERSION,
        }

    def recent_paths(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._session() as db:
            return self._query_edges(db, limit=limit)

    def suggest_skill(
        self,
        task: str,
        *,
        candidates: list[str] | None = None,
        limit: int = 5,
        min_similarity: float = 0.2,
    ) -> list[dict[str, Any]]:
        """Recall skills that succeeded on similar tasks (mycelial fast paths).

        This is the read side of the network: the orchestrator asks which
        previously learned skill to try when the planner's vocabulary misses.
        Only success-dominated edges are considered; a failing path is never
        recommended.
        """
        wanted = {str(item) for item in candidates} if candidates else None
        task_tokens = _tokens(task)
        with self._lock, self._session() as db:
            rows = db.execute(
                """SELECT s.label AS task_label, d.label AS skill_label,
                          e.weight, e.successes, e.failures, e.myelinated
                   FROM edges e
                   JOIN nodes s ON s.node_id = e.src
                   JOIN nodes d ON d.node_id = e.dst
                   WHERE e.relation = 'activates'
                     AND s.kind = 'task'
                     AND d.kind = 'skill'
                   ORDER BY e.weight DESC LIMIT 500"""
            ).fetchall()
            co_rows = db.execute(
                """SELECT s.label AS source_skill, d.label AS target_skill,
                          e.weight, e.successes, e.failures, e.myelinated
                   FROM edges e
                   JOIN nodes s ON s.node_id = e.src
                   JOIN nodes d ON d.node_id = e.dst
                   WHERE e.relation = 'co_activates'
                     AND s.kind = 'skill'
                     AND d.kind = 'skill'
                   ORDER BY e.weight DESC LIMIT 500"""
            ).fetchall()

        best: dict[str, dict[str, Any]] = {}
        for row in rows:
            skill = str(row["skill_label"])
            if wanted is not None and skill not in wanted:
                continue
            successes = int(row["successes"])
            failures = int(row["failures"])
            if failures >= successes:
                continue
            similarity = _similarity(task_tokens, _tokens(row["task_label"]))
            if similarity < min_similarity:
                continue
            # Similarity dominates, reliability and myelination break ties.
            reliability = (successes + 1.0) / (successes + failures + 2.0)
            score = similarity * (0.5 + reliability) * (1.0 + float(row["weight"]))
            entry = {
                "skill": skill,
                "matched_task": row["task_label"],
                "similarity": round(similarity, 4),
                "weight": round(float(row["weight"]), 4),
                "successes": successes,
                "failures": failures,
                "myelinated": bool(row["myelinated"]),
                "score": round(score, 4),
                "relation": "activation",
            }
            if skill not in best or score > best[skill]["score"]:
                best[skill] = entry

        # Associative recall: skills that repeatedly fired together form a
        # mycelial link. When one of them is recalled for this task, its proven
        # partner becomes a candidate too, at a confidence discount. Only
        # success-dominated co-activations are followed, and the candidate must
        # still be registered, so this can never resurrect a failing path.
        for row in co_rows:
            source = str(row["source_skill"])
            target = str(row["target_skill"])
            origin = best.get(source)
            if origin is None or target in best:
                continue
            if wanted is not None and target not in wanted:
                continue
            successes = int(row["successes"])
            failures = int(row["failures"])
            if failures >= successes:
                continue
            reliability = (successes + 1.0) / (successes + failures + 2.0)
            score = origin["score"] * 0.75 * reliability
            if score <= 0:
                continue
            best[target] = {
                "skill": target,
                "matched_task": origin["matched_task"],
                "similarity": origin["similarity"],
                "weight": round(float(row["weight"]), 4),
                "successes": successes,
                "failures": failures,
                "myelinated": bool(row["myelinated"]),
                "score": round(score, 4),
                "relation": "co_activation",
                "via_skill": source,
            }

        ranked = sorted(best.values(), key=lambda item: item["score"], reverse=True)
        return ranked[: max(1, min(limit, 50))]

    def suggest_route(
        self,
        task: str,
        *,
        limit: int = 5,
        min_similarity: float = 0.45,
    ) -> list[dict[str, Any]]:
        """Recall provider/model paths that succeeded on similar tasks.

        This closes the mycelial loop: the graph does not only suggest a skill,
        it can also prefer the provider/model that previously answered a
        similar task successfully. Failure-dominated paths are never
        recommended, and a single lucky run does not dominate routing.
        """
        task_tokens = _tokens(task)
        with self._lock, self._session() as db:
            rows = db.execute(
                """SELECT t.label AS task_label,
                          d.kind AS target_kind,
                          d.label AS target_label,
                          e.weight, e.successes, e.failures, e.myelinated
                   FROM edges e
                   JOIN nodes t ON t.node_id = e.src
                   JOIN nodes d ON d.node_id = e.dst
                   WHERE e.relation = 'answered_by'
                     AND t.kind = 'task'
                     AND d.kind IN ('provider', 'model')
                   ORDER BY e.weight DESC LIMIT 1000"""
            ).fetchall()

        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for row in rows:
            label = str(row["task_label"])
            bucket = grouped.setdefault(label, {"providers": [], "models": []})
            item = {
                "label": str(row["target_label"]),
                "weight": float(row["weight"]),
                "successes": int(row["successes"]),
                "failures": int(row["failures"]),
                "myelinated": bool(row["myelinated"]),
            }
            if row["target_kind"] == "provider":
                bucket["providers"].append(item)
            else:
                bucket["models"].append(item)

        ranked: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for label, bucket in grouped.items():
            if not bucket["providers"] or not bucket["models"]:
                continue
            provider = max(bucket["providers"], key=lambda item: item["weight"])
            model = max(bucket["models"], key=lambda item: item["weight"])
            successes = model["successes"]
            failures = model["failures"]
            if failures >= successes:
                continue
            similarity = _similarity(task_tokens, _tokens(label))
            if similarity < min_similarity:
                continue
            key = (provider["label"], model["label"])
            if key in seen:
                continue
            seen.add(key)
            reliability = (successes + 1.0) / (successes + failures + 2.0)
            weight = max(provider["weight"], model["weight"])
            myelinated = provider["myelinated"] or model["myelinated"]
            score = (
                similarity
                * (0.5 + reliability)
                * (1.0 + weight)
                * (1.15 if myelinated else 1.0)
            )
            ranked.append({
                "provider": provider["label"],
                "model": model["label"],
                "matched_task": label,
                "similarity": round(similarity, 4),
                "weight": round(weight, 4),
                "successes": successes,
                "failures": failures,
                "myelinated": myelinated,
                "score": round(score, 4),
            })
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[: max(1, min(limit, 50))]


_default_networks: dict[str, GrowthNetwork] = {}
_default_lock = threading.Lock()


def get_growth_network(workspace_root: str | Path | None = None) -> GrowthNetwork:
    """Return the process-wide network for a workspace."""
    root = Path(workspace_root or os.getcwd()).expanduser().resolve()
    key = str(root)
    with _default_lock:
        network = _default_networks.get(key)
        if network is None:
            network = GrowthNetwork(root / ".synapse" / "growth.sqlite3")
            _default_networks[key] = network
        return network


__all__ = ["GrowthNetwork", "get_growth_network", "PROTOCOL_VERSION"]
