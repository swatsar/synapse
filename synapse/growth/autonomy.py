"""Autonomous maintenance loop for Synapse's self-development.

Two rhythms run without operator input:

* **Consolidation** — every ``SYNAPSE_AUTONOMY_CONSOLIDATE_EVENTS`` learned
  paths the network runs a sleep-like pass: decay, prune, recompute hubs. This
  is the forgetting/consolidation half of the mycelial + brain model.
* **Self-training** — when enough *verified* experience has accumulated and the
  cooldown has elapsed, a real LoRA training run is executed on the downloaded
  checkpoint. The promotion gate still decides whether the adapter is kept, so
  autonomous training cannot silently replace a better model.

Training is skipped under pytest and can be disabled with
``SYNAPSE_AUTONOMY_AUTO_TRAIN=0``. Every decision and outcome is persisted in
``.synapse/autonomy_state.json`` and exposed through ``/growth/autonomy``.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import asyncio
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synapse.growth.network import GrowthNetwork, get_growth_network
from synapse.training.locking import TrainingLock


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else default
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, float(default)))


def _now() -> str:
    return datetime.now(UTC).isoformat()


# Workspace ownership registry: guards against two AutonomyLoop instances in
# the same process, complementing the OS file lock used across processes.
_owned_paths: set[str] = set()
_owned_paths_lock = threading.Lock()

# Fields that belong to one training attempt or one self-study pass. They are
# merged from disk before saving so a follower's manual run is not erased by
# the owner's older in-memory copy.
_TRAINING_STATE_KEYS = (
    "last_train_at",
    "last_train_checked_at",
    "last_train_attempt",
    "last_train_status",
    "last_train_result",
    "last_train_verified_records",
)
_STUDY_STATE_KEYS = (
    "last_self_study_at",
    "last_self_study_attempt",
    "last_self_study_result",
)


class AutonomyLoop:
    """Periodic self-development: consolidate the network, then train if due."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        growth_network: GrowthNetwork | None = None,
        interval_seconds: float | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.network = growth_network or get_growth_network(self.workspace_root)
        self.interval_seconds = interval_seconds or _env_float(
            "SYNAPSE_AUTONOMY_INTERVAL", 300.0
        )
        self.consolidate_every = max(
            1, _env_int("SYNAPSE_AUTONOMY_CONSOLIDATE_EVENTS", 25)
        )
        # A small bootstrap set is enough to start the self-development spiral;
        # the training promotion gate rejects adapters that make the holdout
        # worse, so growth is always evidence-gated rather than unconditional.
        self.min_records = max(4, _env_int("SYNAPSE_AUTONOMY_MIN_RECORDS", 16))
        self.min_new_records = max(1, _env_int("SYNAPSE_AUTONOMY_MIN_NEW_RECORDS", 8))
        self.train_cooldown = max(
            60.0, _env_float("SYNAPSE_AUTONOMY_TRAIN_COOLDOWN", 86_400.0)
        )
        self.train_steps = max(1, _env_int("SYNAPSE_AUTONOMY_TRAIN_STEPS", 8))
        # When there is not enough new experience, the loop can study the
        # project's own documentation. Extracted facts are verified against the
        # source file before they enter the experience store, so this is
        # grounded study rather than self-distillation.
        self.self_study_enabled = (
            os.getenv("SYNAPSE_AUTONOMY_SELF_STUDY", "1").strip() != "0"
            and "pytest" not in sys.modules
        )
        self.self_study_batch = max(
            1, _env_int("SYNAPSE_AUTONOMY_SELF_STUDY_BATCH", self.min_new_records)
        )
        self.self_study_cooldown = max(
            60.0, _env_float("SYNAPSE_AUTONOMY_SELF_STUDY_COOLDOWN", 3600.0)
        )
        # Automatic weight training is a real, expensive action. It is enabled
        # by default for the production server but never during the test suite,
        # and any operator can opt out explicitly.
        self.auto_train_enabled = (
            os.getenv("SYNAPSE_AUTONOMY_AUTO_TRAIN", "1").strip() != "0"
            and "pytest" not in sys.modules
        )
        self._lock = threading.Lock()
        self._training = False
        self.state = self._load_state()
        self._task: asyncio.Task | None = None
        # Cross-process ownership: two servers (e.g. dev ports 8001/8002) may
        # share one workspace. Only the owner may consolidate or train; the
        # other process follows the same state file instead of racing it.
        self._lock_path = self.workspace_root / ".synapse" / "autonomy.lock"
        self._lock_handle = None
        self._lock_key: str | None = None
        self._owner = False
        # Shared with chat-driven learning and the operator training endpoint:
        # every real LoRA run must pass through this lock.
        self._training_lock = TrainingLock(
            self.workspace_root / ".synapse" / "training.lock"
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _state_path(self) -> Path:
        return self.workspace_root / ".synapse" / "autonomy_state.json"

    def _load_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self._state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return data if isinstance(data, dict) else {}

    def _sync_shared_state(self) -> None:
        """Import newer training/study evidence written by another process.

        Two API processes may share one workspace. The cadence owner keeps its
        own snapshot in memory, while an operator-forced run can complete in
        the follower. Without this merge the owner's next save would overwrite
        that completed run with stale values.
        """
        disk = self._load_state()
        if not disk:
            return

        def newer(marker: str) -> bool:
            try:
                return float(disk.get(marker) or 0) > float(
                    self.state.get(marker) or 0
                )
            except (TypeError, ValueError):
                return False

        if newer("last_train_attempt"):
            for key in _TRAINING_STATE_KEYS:
                if key in disk:
                    self.state[key] = disk[key]
        if newer("last_self_study_attempt"):
            for key in _STUDY_STATE_KEYS:
                if key in disk:
                    self.state[key] = disk[key]
        # Pause is an operator switch, not training evidence. Whichever process
        # changed it last wins, so pausing through the follower API also stops
        # the owner's cadence instead of being overwritten on the next save.
        try:
            disk_paused_at = float(disk.get("paused_changed_at") or 0)
            mine_paused_at = float(self.state.get("paused_changed_at") or 0)
        except (TypeError, ValueError):
            disk_paused_at = mine_paused_at = 0.0
        if disk_paused_at > mine_paused_at:
            self.state["paused"] = bool(disk.get("paused"))
            self.state["paused_at"] = disk.get("paused_at")
            self.state["paused_changed_at"] = disk_paused_at

    def _save_state(self) -> None:
        try:
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            self._sync_shared_state()
            path.write_text(
                json.dumps(self.state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Cross-process ownership
    # ------------------------------------------------------------------

    def _acquire_process_lock(self) -> bool:
        """Become the single autonomy owner for this workspace.

        Uses an in-process registry and an OS file lock. The file lock is
        released automatically when the process exits, so a crashed owner
        never leaves the workspace permanently locked.
        """
        if self._owner:
            return True
        key = str(self._lock_path)
        with _owned_paths_lock:
            if key in _owned_paths:
                return False
        handle = None
        try:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = self._lock_path.open("a+b")
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"lock")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            return False
        with _owned_paths_lock:
            if key in _owned_paths:
                try:
                    handle.close()
                except OSError:
                    pass
                return False
            _owned_paths.add(key)
        self._lock_handle = handle
        self._lock_key = key
        self._owner = True
        self.state["process_role"] = "owner"
        return True

    def _release_process_lock(self) -> None:
        handle = self._lock_handle
        key = self._lock_key
        self._lock_handle = None
        self._lock_key = None
        self._owner = False
        if key is not None:
            with _owned_paths_lock:
                _owned_paths.discard(key)
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            try:
                handle.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Training lock (operator runs and automatic runs share this)
    # ------------------------------------------------------------------

    def _acquire_training_lock(self) -> bool:
        """Ensure only one training run touches the workspace at a time.

        This is deliberately narrower than cadence ownership: either server
        process may execute a one-off operator command, but two simultaneous
        LoRA runs over the same adapter directory must never happen. The same
        lock is used by chat-driven learning and the operator training route.
        """
        return self._training_lock.acquire()

    def _release_training_lock(self) -> None:
        self._training_lock.release()

    # ------------------------------------------------------------------
    # Cycle
    # ------------------------------------------------------------------

    async def tick(self) -> dict[str, Any]:
        """Run one maintenance cycle; safe to call manually or on schedule."""
        self._sync_shared_state()
        if self.state.get("paused"):
            # Pause is a global operator switch: no consolidation, no training.
            # It is persisted in autonomy_state.json so followers and restarts
            # honour it too.
            return {
                "tick": int(self.state.get("ticks") or 0),
                "consolidated": False,
                "training": None,
                "auto_train_enabled": self.auto_train_enabled,
                "paused": True,
                "skipped": "autonomy_paused",
                "protocol_version": PROTOCOL_VERSION,
            }
        if not self._owner and not self._acquire_process_lock():
            return {
                "tick": int(self.state.get("ticks") or 0),
                "consolidated": False,
                "training": None,
                "auto_train_enabled": self.auto_train_enabled,
                "skipped": "autonomy_owned_by_another_process",
                "protocol_version": PROTOCOL_VERSION,
            }
        ticks = int(self.state.get("ticks") or 0) + 1
        self.state["ticks"] = ticks
        self.state["last_tick_at"] = _now()
        result: dict[str, Any] = {
            "tick": ticks,
            "consolidated": False,
            "training": None,
            "auto_train_enabled": self.auto_train_enabled,
            "protocol_version": PROTOCOL_VERSION,
        }

        status = self.network.status()
        events = int(status.get("events") or 0)
        last_events = int(self.state.get("last_consolidated_events") or 0)
        if events and events - last_events >= self.consolidate_every:
            try:
                summary = self.network.consolidate()
                self.state["last_consolidated_events"] = events
                self.state["last_consolidation_pass"] = summary.get("pass")
                self.state["last_consolidation_at"] = summary.get("created_at")
                result["consolidated"] = True
                result["consolidation"] = summary
            except Exception as exc:
                result["consolidation_error"] = str(exc)

        if self.auto_train_enabled:
            training = await self._maybe_train()
            if training is not None:
                result["training"] = training

        self._save_state()
        try:
            from synapse.observability.logger import audit

            audit(
                event="autonomy_tick",
                tick=ticks,
                consolidated=result["consolidated"],
                training=(result["training"] or {}).get("status"),
            )
        except Exception:
            pass
        return result

    async def _maybe_train(self, *, force: bool = False) -> dict[str, Any] | None:
        if self.state.get("paused") and not force:
            return {"status": "skipped", "reason": "autonomy_paused"}
        if self._training:
            return {"status": "skipped", "reason": "training_already_running"}
        # Cadence ownership only elects who ticks. A manual run may arrive on
        # any API process, so training uses its own cross-process lock instead
        # of refusing the request with "owned_by_another_process".
        if not self._acquire_training_lock():
            return {
                "status": "skipped",
                "reason": "training_running_in_another_process",
            }
        try:
            study: dict[str, Any] | None = None
            readiness = self.training_readiness()
            # Grounded self-study is the autonomous source of new experience. It
            # runs only when training is blocked by a data shortage, so the loop
            # never scans documentation while there is already enough to learn.
            if (
                self._needs_experience(readiness)
                and self.auto_train_enabled
                and self.self_study_enabled
            ):
                study = await asyncio.to_thread(self._self_study_if_needed, force=force)
                readiness = self.training_readiness()
            # A "skipped" outcome means no training actually happened (not enough
            # experience yet). It must not start the cooldown, otherwise new
            # verified experience would sit unused for a whole day. A completed run
            # also stops blocking once genuinely new records have arrived: the
            # new-data gate already prevents reusing the same dataset.
            if not force and "cooldown" in (readiness.get("blockers") or ()):
                return None
            self._training = True
            try:
                outcome = await asyncio.to_thread(self._train_once)
            except Exception as exc:
                outcome = {"status": "error", "error": str(exc)}
            finally:
                self._training = False
            if study is not None:
                outcome["self_study"] = {
                    key: study.get(key)
                    for key in ("success", "created", "skipped", "documents", "error")
                    if study.get(key) is not None
                }
            self.state["last_train_checked_at"] = _now()
            if outcome.get("status") not in {"skipped"}:
                self.state["last_train_attempt"] = time.time()
                self.state["last_train_at"] = _now()
            self.state["last_train_status"] = outcome.get("status")
            self.state["last_train_result"] = {
                key: outcome.get(key)
                for key in (
                    "status", "verified_records", "final_loss",
                    "holdout_loss_before", "holdout_loss_after",
                    "promotion_gate", "promotion_status",
                    "behavioral_probes", "behavioral_passed_before",
                    "behavioral_passed_after", "behavioral_gate",
                    "adapter_path", "reason", "error", "self_study",
                )
                if outcome.get(key) is not None
            }
            self._save_state()
            return outcome
        finally:
            self._release_training_lock()

    @staticmethod
    def _needs_experience(readiness: dict[str, Any]) -> bool:
        blockers = set(readiness.get("blockers") or ())
        return bool(
            {"no_new_verified_experience", "not_enough_verified_experience"}
            & blockers
        )

    def _self_study_if_needed(self, *, force: bool = False) -> dict[str, Any] | None:
        """Add grounded experience from documentation when data is missing.

        The study cooldown is separate from the training cooldown: it prevents
        rescanning unchanged docs every tick, while a manual forced run can
        still refresh the store immediately.
        """
        readiness = self.training_readiness()
        if not self._needs_experience(readiness):
            return None
        last_attempt = float(self.state.get("last_self_study_attempt") or 0.0)
        if (
            not force
            and last_attempt > 0
            and time.time() - last_attempt < self.self_study_cooldown
        ):
            return None
        return self.self_study_now()

    def self_study_now(self, *, max_records: int | None = None) -> dict[str, Any]:
        """Run grounded self-study immediately and persist its outcome.

        Manual study must be visible in ``status()`` and in the self-report, so
        both the autonomous loop and the API share this single path.
        """
        from synapse.skills.builtins.self_study import collect_grounded_experience

        limit = max(1, min(int(max_records or self.self_study_batch), 64))
        try:
            result = collect_grounded_experience(
                self.workspace_root, max_records=limit,
            )
        except Exception as exc:
            result = {"success": False, "created": 0, "error": str(exc)}
        self.state["last_self_study_at"] = _now()
        self.state["last_self_study_attempt"] = time.time()
        self.state["last_self_study_result"] = {
            key: result.get(key)
            for key in ("success", "created", "skipped", "documents", "error", "note")
            if result.get(key) is not None
        }
        self._save_state()
        # A study pass is real work on the agent's knowledge base, so it must
        # leave a trace in the mycelial network too. Repeated passes strengthen
        # the self_study -> documentation route; a hard error inhibits it.
        try:
            if result.get("created") or result.get("documents"):
                self.network.record_execution(
                    task="grounded self-study of project documentation",
                    skill="self_study",
                    provider="documentation",
                    model=None,
                    success=not result.get("error"),
                    error=result.get("error"),
                )
        except Exception:
            pass
        return result

    def training_readiness(self) -> dict[str, Any]:
        """Report whether another real LoRA run can start now."""
        from synapse.experience import ExperienceStore

        # A follower can observe a run completed by another process; merge the
        # newer evidence before deciding whether the cooldown still applies.
        self._sync_shared_state()
        store = ExperienceStore(
            self.workspace_root / ".synapse" / "experience.sqlite3"
        )
        try:
            verified_rows = store.count(verified_only=True)
            verified = store.count_distinct_training(verified_only=True)
        finally:
            store.close()
        trained = int(self.state.get("last_train_verified_records") or 0)
        new_records = max(0, verified - trained)
        last_attempt = float(self.state.get("last_train_attempt") or 0.0)
        last_status = self.state.get("last_train_status")
        new_enough = new_records >= self.min_new_records
        last_failed = last_status in {"error", "blocked", "failed"}
        # Cooldown protects against retry storms and against retraining the
        # exact same dataset. Once genuinely new verified experience exists,
        # waiting a full day would only delay learning that is already gated by
        # the new-data requirement.
        cooling = (
            last_status != "skipped"
            and last_attempt > 0
            and time.time() - last_attempt < self.train_cooldown
            and (not new_enough or last_failed)
        )
        cooldown_remaining = (
            max(0.0, self.train_cooldown - (time.time() - last_attempt))
            if cooling else 0.0
        )
        blockers: list[str] = []
        if self.state.get("paused"):
            blockers.append("autonomy_paused")
        if not self.auto_train_enabled:
            blockers.append("auto_train_disabled")
        if verified < self.min_records:
            blockers.append("not_enough_verified_experience")
        if new_records < self.min_new_records:
            blockers.append("no_new_verified_experience")
        if cooling:
            blockers.append("cooldown")
        if self._training or (
            not self._training_lock.held
            and self._training_lock.is_held_elsewhere()
        ):
            blockers.append("training_already_running")
        return {
            "ready": not blockers,
            "verified_records": verified,
            "verified_record_rows": verified_rows,
            "trained_verified_records": trained,
            "new_verified_records": new_records,
            "required_records": self.min_records,
            "required_new_records": self.min_new_records,
            "cooldown_remaining_seconds": round(cooldown_remaining, 1),
            "last_train_status": last_status,
            "blockers": blockers,
            "protocol_version": PROTOCOL_VERSION,
        }

    async def train_now(self, *, force: bool = False) -> dict[str, Any]:
        """Run one gated training attempt immediately (operator control).

        The response shape is stable for every outcome, including early
        refusals, so callers never have to guess whether ``training`` exists.
        """
        def _refused(reason: str) -> dict[str, Any]:
            return {
                "training": {"status": "skipped", "reason": reason},
                "readiness": self.training_readiness(),
                "protocol_version": PROTOCOL_VERSION,
            }

        if not self.auto_train_enabled:
            return _refused("auto_train_disabled")
        if self.state.get("paused") and not force:
            return _refused("autonomy_paused")
        # No cadence-ownership requirement here: a one-off operator command is
        # allowed on a follower API process. `_maybe_train` serializes actual
        # runs with the cross-process training lock.
        outcome = await self._maybe_train(force=force)
        if outcome is None:
            readiness = self.training_readiness()
            reason = (
                "cooldown" if "cooldown" in (readiness.get("blockers") or ())
                else "training_not_due"
            )
            outcome = {"status": "skipped", "reason": reason}
        return {
            "training": outcome,
            "readiness": self.training_readiness(),
            "protocol_version": PROTOCOL_VERSION,
        }

    def _train_once(self) -> dict[str, Any]:
        """Train a real adapter over verified experience, if there is enough."""
        from synapse.experience import DatasetSnapshotStore, ExperienceStore
        from synapse.models import get_model_registry
        from synapse.training import train_lora

        store = ExperienceStore(self.workspace_root / ".synapse" / "experience.sqlite3")
        try:
            verified = store.count_distinct_training(verified_only=True)
            already_trained = int(self.state.get("last_train_verified_records") or 0)
            if verified < self.min_records:
                return {
                    "status": "skipped",
                    "reason": "not_enough_verified_experience",
                    "verified_records": verified,
                    "required": self.min_records,
                }
            if verified - already_trained < self.min_new_records:
                return {
                    "status": "skipped",
                    "reason": "no_new_verified_experience",
                    "verified_records": verified,
                    "required_new": self.min_new_records,
                }
            manifests = [
                manifest for manifest in get_model_registry().list()
                if manifest.status == "downloaded" and manifest.local_path
            ]
            if not manifests:
                return {"status": "skipped", "reason": "no_downloaded_local_model"}
            manifest = manifests[0]
            snapshots = DatasetSnapshotStore(self.workspace_root / ".synapse" / "datasets")
            try:
                snapshot = snapshots.create(store, seed=int(time.time()))
            except ValueError as exc:
                return {"status": "skipped", "reason": str(exc)}
            output_dir = (
                self.workspace_root / ".synapse" / "adapters"
                / f"auto_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            )
            result = train_lora(
                experience_store=store,
                snapshot=snapshot,
                base_model=manifest.local_path,
                output_dir=output_dir,
                steps=self.train_steps,
                require_gpu=False,
                metadata={
                    "origin": "autonomy",
                    "topic": "autonomous self-training",
                    "teacher": "verified_experience",
                },
            )
            evidence = result.to_dict()
            success = evidence.get("status") == "completed"
            self.network.record_execution(
                task="autonomous self-training",
                skill="training",
                provider="local_transformers",
                model=manifest.model_id,
                success=success,
                error=evidence.get("error"),
            )
            if evidence.get("promotion_status") == "promoted":
                self.network.consolidate()
            if success:
                # Only count the records as trained when the run completed.
                self.state["last_train_verified_records"] = verified
            return {
                "status": evidence.get("status"),
                "verified_records": verified,
                "final_loss": evidence.get("final_loss"),
                "holdout_loss_before": evidence.get("holdout_loss_before"),
                "holdout_loss_after": evidence.get("holdout_loss_after"),
                "promotion_gate": evidence.get("promotion_gate"),
                "promotion_status": evidence.get("promotion_status"),
                "behavioral_probes": evidence.get("behavioral_probes"),
                "behavioral_passed_before": evidence.get("behavioral_passed_before"),
                "behavioral_passed_after": evidence.get("behavioral_passed_after"),
                "behavioral_gate": evidence.get("behavioral_gate"),
                "adapter_path": evidence.get("adapter_path"),
                "error": evidence.get("error"),
            }
        finally:
            store.close()

    async def run_forever(self) -> None:
        """Background cadence used by the API lifespan."""
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                try:
                    from synapse.observability.logger import audit

                    audit(event="autonomy_tick_error", error=str(exc))
                except Exception:
                    pass
            await asyncio.sleep(max(30.0, self.interval_seconds))

    async def _run_guarded(self) -> None:
        """Wait for workspace ownership, then run the maintenance cadence."""
        while True:
            if self._acquire_process_lock():
                await self.run_forever()
                return
            # Another process owns this workspace; follow its state rather
            # than racing training. Retry so ownership can be taken over if
            # the owner exits.
            self.state["process_role"] = "follower"
            await asyncio.sleep(max(30.0, self.interval_seconds))

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run_guarded(), name="synapse:autonomy"
            )
        return self._task

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._release_process_lock()

    def pause(self) -> dict[str, Any]:
        """Stop consolidation and automatic training until resumed."""
        self.state["paused"] = True
        self.state["paused_at"] = _now()
        self.state["paused_changed_at"] = time.time()
        self._save_state()
        return self.status()

    def resume(self) -> dict[str, Any]:
        self.state["paused"] = False
        self.state["resumed_at"] = _now()
        self.state["paused_changed_at"] = time.time()
        self._save_state()
        return self.status()

    def status(self) -> dict[str, Any]:
        # A follower does not tick, so show the owner's persisted state
        # instead of a stale in-memory snapshot. The owner also merges newer
        # manual-run evidence written by a follower.
        if not self._owner:
            disk_state = self._load_state()
            if disk_state:
                self.state = disk_state
        else:
            self._sync_shared_state()
        return {
            "status": "running" if self._task and not self._task.done() else "idle",
            "process_role": "owner" if self._owner else "follower",
            "auto_train_enabled": self.auto_train_enabled,
            "paused": bool(self.state.get("paused")),
            "paused_at": self.state.get("paused_at"),
            "interval_seconds": self.interval_seconds,
            "consolidate_every_events": self.consolidate_every,
            "min_verified_records": self.min_records,
            "min_new_records": self.min_new_records,
            "train_cooldown_seconds": self.train_cooldown,
            "train_steps": self.train_steps,
            "self_study_enabled": self.self_study_enabled,
            "self_study_batch": self.self_study_batch,
            "self_study_cooldown_seconds": self.self_study_cooldown,
            "last_self_study_at": self.state.get("last_self_study_at"),
            "last_self_study_result": self.state.get("last_self_study_result"),
            "last_tick_at": self.state.get("last_tick_at"),
            "ticks": int(self.state.get("ticks") or 0),
            "last_consolidation_at": self.state.get("last_consolidation_at"),
            "last_consolidation_pass": self.state.get("last_consolidation_pass"),
            "last_train_at": self.state.get("last_train_at"),
            "last_train_checked_at": self.state.get("last_train_checked_at"),
            "last_train_status": self.state.get("last_train_status"),
            "last_train_result": self.state.get("last_train_result"),
            "training_readiness": self.training_readiness(),
            "protocol_version": PROTOCOL_VERSION,
        }


_loops: dict[str, AutonomyLoop] = {}
_loops_lock = threading.Lock()


def get_autonomy_loop(
    workspace_root: str | Path | None = None,
    *,
    growth_network: GrowthNetwork | None = None,
) -> AutonomyLoop:
    root = Path(workspace_root or os.getcwd()).expanduser().resolve()
    key = str(root)
    with _loops_lock:
        loop = _loops.get(key)
        if loop is None:
            loop = AutonomyLoop(root, growth_network=growth_network)
            _loops[key] = loop
        return loop


__all__ = ["AutonomyLoop", "get_autonomy_loop", "PROTOCOL_VERSION"]
