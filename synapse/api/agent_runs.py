"""Operator-started agent jobs in the local workspace task ledger."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path
from time import monotonic
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from synapse.api.workspace_store import WorkspaceStore, utc_now
from synapse.config.settings import local_only_enabled, selected_opencode_enabled
from synapse.experience import ExperienceRecord, ExperienceStore, verify_task_outcome
from synapse.experience.verification import build_training_feedback
from synapse.harnesses import ClaudeCodeHarness, CodexHarness, HarnessRequest, HarnessResult
from synapse.integrations.opencode_bridge import detect_models

router = APIRouter()
logger = logging.getLogger(__name__)
TASK_PREFIX = "agent_task_"
_CLI_HARNESSES = {"codex": CodexHarness, "claude_code": ClaudeCodeHarness}
_EVENT_TYPES = {"step_finish", "tool_use", "item.completed", "result", "turn.completed"}
_ITEM_TYPES = {"command_execution", "file_change", "mcp_tool_call", "web_search", "todo_list"}
_CLAUDE_READ_TOOLS = {"Read": "read_file", "Glob": "find_files", "Grep": "search_text"}
Execute = Callable[[dict[str, Any]], Awaitable[HarnessResult]]


def _visible_steps(events: tuple[dict[str, Any], ...]) -> list[dict[str, str]]:
    steps = []
    for event in events:
        kind = event.get("type")
        if kind == "assistant":
            message = event.get("message")
            content = message.get("content", []) if isinstance(message, dict) else []
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "tool_use":
                        continue
                    name = item.get("name")
                    if isinstance(name, str) and name in _CLAUDE_READ_TOOLS:
                        steps.append({"type": "tool_use", "action": _CLAUDE_READ_TOOLS[name]})
                    if len(steps) == 100:
                        return steps
        if not isinstance(kind, str) or kind not in _EVENT_TYPES:
            continue
        step = {"type": kind}
        item = event.get("item")
        item_kind = item.get("type") if isinstance(item, dict) else None
        if isinstance(item_kind, str) and item_kind in _ITEM_TYPES:
            step["action"] = item_kind
        steps.append(step)
        if len(steps) == 100:
            break
    return steps


def _final_harness_result(agent: str, outcome: HarnessResult) -> HarnessResult:
    """Separate the final answer from CLI progress and structured errors."""
    if agent == "claude_code":
        for event in outcome.events:
            model = event.get("model")
            if event.get("type") == "system" and event.get("subtype") == "init" and isinstance(model, str) and model:
                outcome = replace(outcome, receipt={**outcome.receipt, "model": model})
                break
    codex_completed = outcome.success and any(event.get("type") == "turn.completed" for event in outcome.events)
    for event in reversed(outcome.events):
        if agent == "codex" and codex_completed and event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    return replace(outcome, output=text)
        if agent == "claude_code" and event.get("type") == "result":
            text = event.get("result")
            if event.get("is_error") is True:
                code = re.search(r"\bAPI Error:\s*(\d{3})\b", text) if isinstance(text, str) else None
                message = f"Claude Code: ошибка API {code[1]}." if code else "Claude Code сообщил об ошибке."
                return replace(outcome, success=False, error=message)
            if outcome.success and event.get("subtype") == "success" and isinstance(text, str) and text.strip():
                return replace(outcome, output=text)
    if outcome.success:
        return replace(outcome, success=False, error="Агент не подтвердил завершение задачи.")
    return outcome


class ManagedAgentRuns:
    def __init__(self, store: WorkspaceStore, experience: ExperienceStore, workspace: Path):
        self.store = store
        self.experience = experience
        self.workspace = workspace
        self.active: dict[str, asyncio.Task[None]] = {}
        self._last_recovery = float("-inf")

    def start(self, record: dict[str, Any], execute: Execute) -> asyncio.Task[None]:
        task_id = record["id"]
        job = asyncio.create_task(self._run(record, execute), name=task_id)
        self.active[task_id] = job
        job.add_done_callback(lambda completed: self._job_finished(record, completed))
        return job

    def _job_finished(self, record: dict[str, Any], job: asyncio.Task[None]) -> None:
        self.active.pop(record["id"], None)
        current = self.store.get_task(record["id"])
        if job.cancelled():
            if current["status"] == "cancelling":
                self._finish(record, "cancelled", "Задача остановлена.")
        elif (error := job.exception()) is not None:
            logger.error("Agent job %s failed", record["id"], exc_info=error)
            if current["status"] in {"queued", "running", "cancelling"}:
                self._finish(record, "failed", "Не удалось сохранить результат агента.")

    def recover_expired(self) -> None:
        # Another process could still own a fresh task. Only reconcile runs
        # past their execution deadline and never re-run an interrupted agent.
        tick = monotonic()
        if tick - self._last_recovery < 15:
            return
        self._last_recovery = tick
        now = datetime.now(UTC)
        for record in self.store.list_all_tasks():
            if not record["id"].startswith(TASK_PREFIX) or record["id"] in self.active:
                continue
            if record["status"] not in {"queued", "running", "cancelling"}:
                continue
            start = datetime.fromisoformat(record["started_at"] or record["created_at"])
            timeout = record["payload"]["timeout_seconds"]
            if now - start > timedelta(seconds=timeout + 30):
                self._finish(record, "failed", "Выполнение прервано. Запустите задачу повторно.")

    async def stop(self, record: dict[str, Any]) -> dict[str, Any]:
        job = self.active.get(record["id"])
        if job is None or job.done():
            current = self.store.get_task(record["id"])
            if current["status"] in {"queued", "running", "cancelling"}:
                raise HTTPException(409, "This worker does not own the agent task")
            return current
        if self.store.get_task(record["id"])["status"] != "cancelling":
            self.store.update_task(record["id"], status="cancelling")
            job.cancel()
        await asyncio.shield(asyncio.gather(job, return_exceptions=True))
        return self.store.get_task(record["id"])

    async def close(self) -> None:
        for task_id in tuple(self.active):
            record = self.store.get_task(task_id)
            if record is not None:
                await self.stop(record)

    def _finish(self, record: dict[str, Any], status: str, text: str, **fields: Any) -> dict[str, Any]:
        task_id, session = record["id"], record["session_id"]
        current = self.store.update_task(
            task_id, status=status, success=(status == "completed"), completed_at=utc_now(),
            error=text if status == "failed" else None, **fields,
        )
        self.store.add_message(session, "assistant", text, task_id)
        self.store.add_event(session, task_id, "task", {"status": status})
        return current

    async def _run(self, record: dict[str, Any], execute: Execute) -> None:
        started = monotonic()
        task_id, session = record["id"], record["session_id"]
        self.store.update_task(task_id, status="running", started_at=utc_now())
        self.store.add_event(session, task_id, "task", {"status": "running"})
        try:
            outcome = await execute(record)
        except asyncio.CancelledError:
            self._finish(record, "cancelled", "Задача остановлена.")
            raise
        except Exception:
            logger.exception("Agent execution failed for %s", task_id)
            self._finish(record, "failed", "Не удалось запустить агента.")
            return
        if not outcome.success or not outcome.output.strip():
            self._finish(record, "failed", outcome.error or "Агент не вернул результат.")
            return
        payload = record["payload"]
        steps = _visible_steps(outcome.events)
        actual_model = outcome.receipt.get("model")
        output = {
            "content": outcome.output, "provider": payload["managed_agent"],
            "model": actual_model or payload.get("model"),
            "model_source": "reported" if actual_model else ("requested" if payload.get("model") else "unknown"),
        }
        result = {"action_result": {"outputs": [output]}, "agent_steps": steps}
        verification = verify_task_outcome(payload, result, workspace_root=self.workspace)
        result["verification"] = verification
        training = build_training_feedback(record["task"], result)
        # Train on the verified public answer plus observed action categories.
        # Raw arguments, file contents and internal reasoning stay out of SFT.
        visible_actions = list(dict.fromkeys(step["action"] for step in steps if "action" in step))
        if visible_actions and training["training_text"]:
            training["training_text"] += "\n\nObserved agent actions: " + ", ".join(visible_actions)
        eligible = bool(verification["passed"] is True and training["training_ready"])
        feedback = {
            "model_backed": training["model_backed"], "training_ready": eligible,
            "candidate_training_text": training["training_text"], "verification": verification,
        }
        if eligible:
            feedback["training_text"] = training["training_text"]
        elapsed_ms = round((monotonic() - started) * 1000)
        result["learning"] = {"recorded": False, "eligible": False}
        self._finish(record, "completed", outcome.output, result=result, duration_ms=elapsed_ms)
        try:
            self.experience.append(ExperienceRecord(
                task_id=task_id, run_id=task_id, session_id=session, objective=record["task"],
                executor=f"agent:{output['provider']}", provider=output["provider"], model=output["model"],
                visible_events=steps, execution_success=True, verifier_passed=verification["passed"],
                verifier_status=verification["status"], eligibility="eligible" if eligible else "ineligible",
                feedback=feedback, latency_ms=elapsed_ms, provenance={"source": "managed_agent"},
            ))
            result["learning"] = {"recorded": True, "eligible": eligible}
            self.store.update_task(task_id, result=result)
        except Exception:
            logger.exception("Could not store learning evidence for %s", task_id)


class AgentTaskRequest(BaseModel):
    agent: str
    task: str = Field(min_length=1, max_length=20_000)
    model: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$")
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=16)
    timeout_seconds: float = Field(default=120, ge=1, le=600)


def _local_operator(request: Request) -> None:
    host = request.url.hostname
    try:
        local = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local = False
    origin = request.headers.get("origin")
    if not local or host not in {"127.0.0.1", "::1", "localhost"} or (
        origin and origin != f"{request.url.scheme}://{request.url.netloc}"
    ):
        raise HTTPException(403, "Agent tasks require the local Synapse interface")


def _manager(request: Request) -> ManagedAgentRuns:
    _local_operator(request)
    manager = getattr(request.app.state, "managed_agent_runs", None)
    if manager is None:
        raise HTTPException(503, "Agent tasks are not initialized")
    return manager


def _workspace_agents_allowed() -> bool:
    return not local_only_enabled() or os.getenv("SYNAPSE_ALLOW_WORKSPACE_AGENTS", "") == "1"


def _runner_available(runner: Any) -> bool:
    if not runner.enabled or not _workspace_agents_allowed():
        return False
    command = runner.command_argv[0] if runner.command_argv else runner.executable
    resolved = command if Path(command).is_file() else shutil.which(command)
    return bool(resolved) and not (
        os.name == "nt" and Path(resolved).suffix.lower() in {".cmd", ".bat"}
    )


async def _opencode_models() -> list[Any]:
    if local_only_enabled() and not selected_opencode_enabled():
        return []
    models = await asyncio.to_thread(detect_models)
    return [model for model in models if model.model_id.startswith("opencode/")]


@router.get("/agent-executors")
async def available_executors(request: Request) -> dict[str, Any]:
    _local_operator(request)
    manager = getattr(request.app.state, "managed_agent_runs", None)
    if manager is not None:
        manager.recover_expired()
    models = [model.to_dict() for model in await _opencode_models()]
    agents = [{"id": "opencode", "name": "OpenCode", "available": any(model["available"] for model in models), "models": models}]
    for name, cls in _CLI_HARNESSES.items():
        runner = cls(write_enabled=False)
        agents.append({
            "id": name, "name": "Codex" if name == "codex" else "Claude Code",
            "available": _runner_available(runner), "models": [],
        })
    return {"agents": agents}


@router.post("/sessions/{session_id}/agent-tasks", status_code=202)
async def submit_agent_task(session_id: str, body: AgentTaskRequest, request: Request) -> dict[str, Any]:
    manager = _manager(request)
    if not body.task.strip() or any(
        len(value) > 1000 or (
            value.partition(":")[0].strip() in {"output_contains", "output_not_contains"}
            and not value.partition(":")[2].strip()
        ) for value in body.acceptance_criteria
    ):
        raise HTTPException(422, "Invalid task or acceptance criteria")
    session = manager.store.get_session(session_id)
    if session is None or session["archived"]:
        raise HTTPException(404, "Session not found")
    runner = None
    if body.agent == "opencode":
        models = await _opencode_models()
        if not body.model or not any(model.model_id == body.model and model.available for model in models):
            raise HTTPException(422, "Select an available OpenCode model")
    elif body.agent not in _CLI_HARNESSES:
        raise HTTPException(404, "Unknown agent")
    else:
        runner = _CLI_HARNESSES[body.agent](timeout_seconds=body.timeout_seconds, write_enabled=False)
        if not _runner_available(runner):
            raise HTTPException(409, "Connect an enabled native agent executable in Settings first")
    session = manager.store.get_session(session_id)
    if session is None or session["archived"]:
        raise HTTPException(404, "Session not found")
    if len(manager.active) >= 4:
        raise HTTPException(429, "Four agent tasks are already active")
    payload = {
        "managed_agent": body.agent, "model": body.model,
        "acceptance_criteria": body.acceptance_criteria,
        "timeout_seconds": body.timeout_seconds,
    }
    record = manager.store.create_task(
        session_id, body.task.strip(), payload, task_id=TASK_PREFIX + uuid.uuid4().hex,
    )
    manager.store.add_message(session_id, "user", record["task"], record["id"])

    async def execute(task: dict[str, Any]) -> HarnessResult:
        if body.agent == "opencode":
            from synapse.llm.opencode_provider import OpenCodeCLIProvider

            try:
                value = await OpenCodeCLIProvider(body.model, body.timeout_seconds).generate(
                    task["task"], selected_by_user=True, cancellable=True,
                )
            except RuntimeError as exc:
                return HarnessResult(False, error=str(exc))
            return HarnessResult(True, output=value["content"], events=value["events"])
        assert runner is not None
        outcome = await runner.execute(HarnessRequest(
            task_id=task["id"], run_id=task["id"], prompt=task["task"],
            workspace_id=str(manager.workspace), capabilities=("fs:read",),
            metadata={"workspace_root": str(manager.workspace), "model": body.model, "managed_agent": True},
        ))
        return _final_harness_result(body.agent, outcome)

    manager.start(record, execute)
    return record


@router.post("/tasks/{task_id}/cancel")
async def cancel_agent_task(task_id: str, request: Request) -> dict[str, Any]:
    manager = _manager(request)
    manager.recover_expired()
    record = manager.store.get_task(task_id) if task_id.startswith(TASK_PREFIX) else None
    if record is None:
        raise HTTPException(404, "Agent task not found")
    return await manager.stop(record)
