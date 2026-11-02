"""
Multi-turn Trajectory Logger & Reasoning Trace Harness for Synapse v3.4.1.

Adapted from deepseek-ai/deepseek-harness patterns.
Captures structured cognitive trajectories (thoughts, tool calls, observations, evaluations)
for deterministic replay, audit verification, and SFT/DPO dataset generation.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.harnesses.trajectory")


@dataclass
class TrajectoryStep:
    step_number: int
    stage: str  # PERCEIVE, RECALL, PLAN, SECURITY, ACT, OBSERVE, EVALUATE, LEARN
    thought: Optional[str] = None
    action: Optional[dict[str, Any]] = None
    observation: Optional[str] = None
    evaluation: Optional[dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "stage": self.stage,
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
            "evaluation": self.evaluation,
            "timestamp": self.timestamp,
        }


@dataclass
class TrajectoryRecord:
    trajectory_id: str
    task_id: str
    session_id: str
    objective: str
    model: str
    success: bool
    total_steps: int
    duration_ms: float
    steps: list[TrajectoryStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "objective": self.objective,
            "model": self.model,
            "success": self.success,
            "total_steps": self.total_steps,
            "duration_ms": round(self.duration_ms, 2),
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "protocol_version": self.protocol_version,
        }


class TrajectoryHarness:
    """Records, replays, and exports cognitive trajectories for agent self-improvement."""

    def __init__(self, storage_dir: Optional[str | Path] = None):
        if storage_dir:
            self.storage_dir = Path(storage_dir).resolve()
        else:
            base = Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())) / ".synapse" / "trajectories"
            self.storage_dir = base
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._active_trajectories: dict[str, TrajectoryRecord] = {}

    def start_trajectory(
        self,
        task_id: str,
        session_id: str,
        objective: str,
        model: str = "claude-sonnet-5-5",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Initialize recording of a new agent run trajectory."""
        traj_id = f"traj_{uuid.uuid4().hex[:12]}"
        record = TrajectoryRecord(
            trajectory_id=traj_id,
            task_id=task_id,
            session_id=session_id,
            objective=objective,
            model=model,
            success=False,
            total_steps=0,
            duration_ms=0.0,
            steps=[],
            metadata=metadata or {},
        )
        self._active_trajectories[traj_id] = record
        return traj_id

    def record_step(
        self,
        trajectory_id: str,
        stage: str,
        thought: Optional[str] = None,
        action: Optional[dict[str, Any]] = None,
        observation: Optional[str] = None,
        evaluation: Optional[dict[str, Any]] = None,
    ) -> None:
        """Append an atomic cognitive step into the active trajectory."""
        record = self._active_trajectories.get(trajectory_id)
        if not record:
            return

        step = TrajectoryStep(
            step_number=len(record.steps) + 1,
            stage=stage,
            thought=thought,
            action=action,
            observation=observation,
            evaluation=evaluation,
        )
        record.steps.append(step)
        record.total_steps = len(record.steps)

    def finish_trajectory(
        self,
        trajectory_id: str,
        success: bool = True,
        duration_ms: float = 0.0,
    ) -> Optional[TrajectoryRecord]:
        """Finalize and persist trajectory record."""
        record = self._active_trajectories.pop(trajectory_id, None)
        if not record:
            return None

        record.success = success
        record.duration_ms = duration_ms

        # Persist to disk as JSON
        try:
            file_path = self.storage_dir / f"{trajectory_id}.json"
            file_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to write trajectory %s: %s", trajectory_id, e)

        return record

    def list_trajectories(self, limit: int = 50) -> list[dict[str, Any]]:
        """List historical trajectories from disk."""
        trajectories = []
        for file in sorted(self.storage_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                trajectories.append(data)
            except Exception:
                continue
        return trajectories

    def export_dataset_jsonl(self, output_file: Path) -> int:
        """Export completed successful trajectories as JSONL dataset for fine-tuning."""
        count = 0
        with open(output_file, "w", encoding="utf-8") as out:
            for item in self.list_trajectories(limit=1000):
                if item.get("success"):
                    out.write(json.dumps(item) + "\n")
                    count += 1
        return count


_default_trajectory_harness: Optional[TrajectoryHarness] = None


def get_trajectory_harness() -> TrajectoryHarness:
    global _default_trajectory_harness
    if _default_trajectory_harness is None:
        _default_trajectory_harness = TrajectoryHarness()
    return _default_trajectory_harness
