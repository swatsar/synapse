"""Synapse local workspace and HTTP API.

Task execution uses the real cognitive cycle. The workspace API persists
sessions, messages, approvals and progress independently of agent memory.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from synapse.api.middleware import (
    make_rate_limit_middleware,
    make_request_logging_middleware,
    make_security_headers_middleware,
)
from synapse.api.workspace_store import WorkspaceStore, default_workspace_store, utc_now
from synapse.core.exceptions import SynapseError, generic_error_handler, synapse_error_handler

PROTOCOL_VERSION = "1.0"
WEB_ROOT = Path(__file__).resolve().parent.parent / "ui" / "web"
TEMPLATES = WEB_ROOT / "templates"


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def _close_orchestrator(orchestrator: Any) -> None:
    if orchestrator is None:
        return
    memory = getattr(orchestrator, "memory_store", None)
    if memory is not None and hasattr(memory, "close"):
        await _maybe_await(memory.close())
    vector = getattr(memory, "vector_store", None)
    if vector is not None and hasattr(vector, "close"):
        await _maybe_await(vector.close())


def _store(application: FastAPI) -> WorkspaceStore:
    store = getattr(application.state, "workspace_store", None)
    if store is None:
        store = default_workspace_store()
        application.state.workspace_store = store
    return store


def _session(application: FastAPI, session_id: str) -> dict[str, Any]:
    session = _store(application).get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Own runtime resources and await outstanding work during graceful shutdown."""
    from synapse.core.orchestrator import build_orchestrator
    from synapse.runtime.container import get_runtime_container

    container = get_runtime_container()
    application.state.container = container
    await container.start()

    # A new application lifespan starts a fresh rate-limit window. In-flight
    # limits stay unchanged; this prevents separate embedded runs sharing state.
    application.state.rate_limiter.reset()
    owns_runtime = getattr(application.state, "orchestrator", None) is None
    owns_store = getattr(application.state, "workspace_store", None) is None
    if owns_runtime:
        application.state.orchestrator = build_orchestrator(
            db_path=os.getenv("SYNAPSE_DB_PATH") or None,
            vector_persist_dir=os.getenv("SYNAPSE_VECTOR_DIR") or None,
            workspace_root=os.getenv("SYNAPSE_WORKSPACE_ROOT") or None,
        )
        application.state.checkpoint_manager = application.state.orchestrator.checkpoint_manager
        container.orchestrator = application.state.orchestrator
    if owns_store:
        application.state.workspace_store = container.workspace_store
    application.state.omnirouter = container.omnirouter
    jobs: set[asyncio.Task] = set()
    application.state.background_jobs = jobs
    try:
        yield
    finally:
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        if owns_runtime:
            await _close_orchestrator(application.state.orchestrator)
            application.state.orchestrator = None
            application.state.checkpoint_manager = None
        if owns_store:
            application.state.workspace_store.close()
            application.state.workspace_store = None
        await container.stop()


app = FastAPI(title="Synapse Agent Platform", version="3.4.1", lifespan=lifespan)
app.state.orchestrator = None
app.state.checkpoint_manager = None
app.state.rollback_manager = None
app.state.workspace_store = None
app.state.omnirouter = None
app.state.logs = []

app.middleware("http")(make_request_logging_middleware())
app.middleware("http")(make_security_headers_middleware())
app.state.rate_limiter = make_rate_limit_middleware(requests_per_minute=60)
app.middleware("http")(app.state.rate_limiter)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000", "http://127.0.0.1:8000",
        "http://localhost:8080", "http://127.0.0.1:8080",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Correlation-ID", "X-Trace-ID"],
)


@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    """Require an API key for API operations; local HTML and health stay readable."""
    path = request.url.path
    if path == "/health" or not path.startswith(("/api/", "/task", "/checkpoint", "/rollback")):
        return await call_next(request)
    expected_api_key = os.getenv("SYNAPSE_API_KEY")
    if not expected_api_key:
        return await call_next(request)
    supplied_key = request.headers.get("X-API-Key")
    if not supplied_key or not secrets.compare_digest(supplied_key, expected_api_key):
        return JSONResponse(status_code=401, content={
            "error": "Unauthorized", "message": "Invalid or missing X-API-Key header",
            "protocol_version": PROTOCOL_VERSION,
        })
    return await call_next(request)


app.add_exception_handler(SynapseError, synapse_error_handler)
app.add_exception_handler(Exception, generic_error_handler)
from synapse.api.routes import api_router
app.include_router(api_router, prefix="/api/v1")
if (WEB_ROOT / "static").exists():
    app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")


class TaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20_000)
    payload: dict[str, Any] | None = None
    session_id: str | None = None
    protocol_version: Literal["1.0"] = PROTOCOL_VERSION
    model_config = {"extra": "forbid"}


class ApprovalRequest(BaseModel):
    action: str = Field(min_length=1, max_length=500)
    risk_level: int = Field(ge=1, le=5)
    details: dict[str, Any] | None = None


class SessionCreate(BaseModel):
    title: str = Field(default="Новая задача", min_length=1, max_length=160)


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=160)


def _schedule(application: FastAPI, task_id: str) -> None:
    jobs = getattr(application.state, "background_jobs", None)
    if jobs is None:
        raise HTTPException(status_code=503, detail="Background runtime is not initialized")
    container = getattr(application.state, "container", None)
    if container is not None:
        job = container.register_background_task(_execute_task(application, task_id))
    else:
        job = asyncio.create_task(_execute_task(application, task_id), name=f"synapse:{task_id}")
    jobs.add(job)
    job.add_done_callback(jobs.discard)


async def _execute_task(application: FastAPI, task_id: str) -> dict[str, Any]:
    store = _store(application)
    task = store.get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    orchestrator = application.state.orchestrator
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Task runtime is not initialized")
    started = time.monotonic()
    container = getattr(application.state, "container", None)
    invocation = getattr(container, "invocation_service", None)
    work_engine = getattr(container, "work_engine", None)
    durable_task = None
    lease = None
    durable_run = None
    if work_engine is not None:
        from synapse.work import Run, Task, WorkStatus
        durable_task = await work_engine.create_task(
            Task(id=task_id, title=task["task"], description=task["task"])
        )
        durable_run = await work_engine.create_run(Run(task_id=task_id))
        lease = await work_engine.checkout(task_id, "api-worker")
        if lease is None:
            raise RuntimeError("Task could not acquire a durable execution lease")
        await work_engine.transition_task(task_id, WorkStatus.RUNNING)
        await work_engine.transition_run(durable_run.id, WorkStatus.RUNNING)

    store.update_task(task_id, status="running", started_at=utc_now())
    store.add_event(task["session_id"], task_id, "task", {"status": "running"})

    # OmniRouter dynamic model and provider selection
    router = getattr(application.state, "omnirouter", None)
    if router is None:
        from synapse.llm.omnirouter import get_omnirouter
        router = get_omnirouter()
    route_decision = router.route(task["task"], task.get("payload"))
    store.add_event(task["session_id"], task_id, "router", route_decision.to_dict())

    async def progress(step: str, data: dict[str, Any]) -> None:
        await asyncio.to_thread(store.add_event, task["session_id"], task_id, step, data)

    request = {
        "task": task["task"],
        "payload": task["payload"],
        "_progress_callback": progress,
        "_route_decision": route_decision.to_dict(),
    }
    if task.get("approval_id"):
        # This private field is added only after the persisted approval decision.
        request["_approval_granted"] = True
    try:
        async def invoke_orchestrator(**params: Any) -> dict[str, Any]:
            return await orchestrator.handle(params["request"])

        if invocation is not None:
            from synapse.api.invocation_service import InvocationContext
            invocation_result = await invocation.invoke(
                action_type="task",
                action_name="orchestrator.handle",
                handler=invoke_orchestrator,
                context=InvocationContext(
                    identity="api",
                    session_id=task["session_id"],
                    run_id=durable_run.id if durable_run else task_id,
                    workspace_root=Path(getattr(container, "workspace_root", Path.cwd())),
                    capabilities=["fs:read", "llm:route"],
                    approval_granted=bool(task.get("approval_id")),
                    is_network_request=True,
                    auth_authenticated=True,
                ),
                required_capabilities=["fs:read"],
                risk_level=1,
                params={"request": request},
            )
            outcome = invocation_result.result or {"success": False, "error": invocation_result.error}
            if isinstance(outcome.get("result"), dict):
                outcome["result"]["invocation_receipt"] = invocation_result.receipt
            else:
                outcome["invocation_receipt"] = invocation_result.receipt
            if not invocation_result.success and not outcome.get("error"):
                outcome["error"] = invocation_result.error
        else:
            outcome = await orchestrator.handle(request)
        status = outcome.get("status", "failed")
        if work_engine is not None and durable_run is not None:
            from synapse.work import WorkStatus
            if status == "approval_required":
                await work_engine.transition_run(durable_run.id, WorkStatus.WAITING_APPROVAL)
                if lease is not None:
                    await work_engine.release(lease, WorkStatus.WAITING_APPROVAL)
            else:
                final_status = WorkStatus.COMPLETED if bool(outcome.get("success", False)) else WorkStatus.FAILED
                await work_engine.transition_run(durable_run.id, final_status)
                if lease is not None:
                    await work_engine.release(lease, final_status)
        status = outcome.get("status", "failed")
        result = outcome.get("result", outcome)
        record = store.update_task(
            task_id, status=status, success=bool(outcome.get("success", False)),
            error=outcome.get("error"), result=result, completed_at=utc_now(),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        if container is not None and getattr(container, "experience_store", None) is not None:
            from synapse.experience import ExperienceRecord
            receipt = result.get("invocation_receipt", {}) if isinstance(result, dict) else {}
            container.experience_store.append(ExperienceRecord(
                task_id=task_id,
                run_id=receipt.get("run_id", durable_run.id if durable_run else task_id),
                session_id=task["session_id"],
                objective=task["task"],
                inputs=task.get("payload") or {},
                executor="orchestrator.handle",
                provider=(route_decision.to_dict().get("provider") if route_decision else None),
                model=(route_decision.to_dict().get("model") if route_decision else None),
                execution_success=bool(outcome.get("success", False)),
                verifier_passed=None,
                verifier_status="inconclusive",
                eligibility="ineligible",
                error=outcome.get("error"),
                latency_ms=record.get("duration_ms"),
                provenance={"source": "http_task", "invocation_receipt": receipt},
            ))
        if status == "approval_required":
            risk_level = (result or {}).get("plan", {}).get("risk_level", 3)
            approval = store.create_approval(record, risk_level)
            record = store.get_task(task_id)
            store.add_event(task["session_id"], task_id, "approval", approval)
        content = result_message(record)
        store.add_message(task["session_id"], "assistant", content, task_id)
        store.add_event(task["session_id"], task_id, "task", {
            "status": status, "success": record["success"], "error": record["error"],
            "duration_ms": record["duration_ms"],
        })
        application.state.logs.append({
            "timestamp": record["completed_at"], "message": f"Task {task_id}: {status}",
            "task_id": task_id, "protocol_version": PROTOCOL_VERSION,
        })
        return record
    except Exception as exc:
        if work_engine is not None and durable_run is not None:
            from synapse.work import WorkStatus
            try:
                await work_engine.transition_run(durable_run.id, WorkStatus.FAILED)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Failed to persist durable run failure", extra={"run_id": durable_run.id}
                )
            if lease is not None:
                try:
                    await work_engine.release(lease, WorkStatus.FAILED)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to release durable task lease", extra={"task_id": task_id}
                    )
        record = store.update_task(
            task_id, status="failed", success=False, error=str(exc),
            completed_at=utc_now(), duration_ms=round((time.monotonic() - started) * 1000),
        )
        store.add_message(task["session_id"], "assistant", f"Не удалось выполнить задачу: {exc}", task_id)
        store.add_event(task["session_id"], task_id, "task", {"status": "failed", "error": str(exc)})
        return record


def result_message(task: dict[str, Any]) -> str:
    """Human-readable summary; the complete structured result remains available."""
    status = task.get("status")
    if status == "approval_required":
        return "Действие требует вашего подтверждения. Оно ещё не выполнялось."
    if status != "completed":
        return task.get("error") or "Задача завершилась с ошибкой."
    result = task.get("result") or {}
    outputs = (result.get("action_result") or {}).get("outputs") or []
    if len(outputs) == 1 and isinstance(outputs[0].get("content"), str):
        return outputs[0]["content"]
    if outputs:
        return f"Выполнено шагов: {len(outputs)}. Результат доступен на панели справа."
    return "Задача выполнена."


async def _run_task(
    application: FastAPI, task: str, payload: dict[str, Any] | None,
    approval_id: str | None = None, session_id: str | None = None,
) -> dict[str, Any]:
    """Synchronous compatibility endpoint; new UI submits through a session."""
    if session_id:
        _session(application, session_id)
    else:
        session_id = _store(application).create_session(task.strip()[:160])["id"]
    record = _store(application).create_task(session_id, task, payload or {}, approval_id=approval_id)
    _store(application).add_message(session_id, "user", task, record["id"])
    return await _execute_task(application, record["id"])


@app.get("/runtime-info")
async def runtime_info():
    """Expose non-secret UI capability information for clear onboarding."""
    configured = bool(os.getenv("SYNAPSE_API_KEY"))
    return {
        "api_auth_required": configured,
        "api_auth_description": (
            "Защита HTTP API включена. Используйте значение SYNAPSE_API_KEY; "
            "это не ключ провайдера модели."
            if configured else
            "Защита HTTP API отключена для локального режима. Ключ не требуется."
        ),
        "protocol_version": PROTOCOL_VERSION,
    }


@app.get("/health")
async def health_check(request: Request):
    from synapse.runtime.container import get_runtime_container
    container = getattr(request.app.state, "container", None) or get_runtime_container()
    return await container.health()


@app.get("/api/v1/status")
async def get_status(request: Request):
    from synapse.runtime.container import get_runtime_container
    container = getattr(request.app.state, "container", None) or get_runtime_container()
    health_data = await container.health()
    tasks = _store(request.app).list_all_tasks()
    approvals = _store(request.app).list_approvals()
    router = container.omnirouter
    stats = router.get_stats()
    return {
        "status": health_data.get("status", "operational"),
        "subsystems": health_data.get("subsystems", {}),
        "agents_count": sum(getattr(request.app.state.orchestrator, name, None) is not None
                            for name in ("planner", "critic", "learning_engine", "skill_registry")),
        "pending_approvals": sum(a["status"] == "pending" for a in approvals),
        "tasks_completed": sum(t["status"] == "completed" for t in tasks),
        "tasks_failed": sum(t["status"] == "failed" for t in tasks),
        "router": {
            "default_model": router.default_model,
            "total_models": len(router.catalog),
            "routed_total": stats.get("routed_total", 0),
        },
        "protocol_version": PROTOCOL_VERSION,
    }


@app.post("/api/v1/tasks")
async def create_task(data: TaskRequest, request: Request):
    task = data.task.strip()
    if not task:
        raise HTTPException(status_code=422, detail="Task must contain non-whitespace characters")
    return await _run_task(request.app, task, data.payload, session_id=data.session_id)


@app.get("/api/v1/tasks")
async def list_tasks(request: Request):
    return {"tasks": _store(request.app).list_all_tasks(), "protocol_version": PROTOCOL_VERSION}


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    task = _store(request.app).get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/v1/tasks/{task_id}/retry", status_code=202)
async def retry_task(task_id: str, request: Request):
    original = _store(request.app).get_task(task_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if original.get("approval_id"):
        approval = _store(request.app).get_approval(original["approval_id"])
        if not approval or approval["status"] != "approved":
            raise HTTPException(status_code=409, detail="Approve the original action before retrying")
    record = _store(request.app).create_task(
        original["session_id"], original["task"], original["payload"], parent_task_id=task_id,
    )
    _store(request.app).add_message(original["session_id"], "user", original["task"], record["id"])
    _schedule(request.app, record["id"])
    return record


@app.get("/api/v1/sessions")
async def list_sessions(request: Request):
    return {"sessions": _store(request.app).list_sessions(), "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v1/sessions", status_code=201)
async def create_session(request: Request, data: SessionCreate | None = None):
    title = (data.title.strip() if data else None) or "Новая задача"
    return _store(request.app).create_session(title)


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    return {**_session(request.app, session_id),
            "messages": _store(request.app).list_messages(session_id),
            "tasks": _store(request.app).list_tasks(session_id),
            "protocol_version": PROTOCOL_VERSION}


@app.patch("/api/v1/sessions/{session_id}")
async def update_session(session_id: str, data: SessionUpdate, request: Request):
    updated = _store(request.app).update_session(session_id, data.title.strip())
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@app.delete("/api/v1/sessions/{session_id}")
async def archive_session(session_id: str, request: Request):
    if any(t["status"] in {"queued", "running"}
           for t in _store(request.app).list_tasks(session_id)):
        raise HTTPException(status_code=409, detail="Wait for active tasks to finish before archiving")
    if not _store(request.app).archive_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "archived", "id": session_id, "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v1/sessions/{session_id}/tasks", status_code=202)
async def submit_session_task(session_id: str, data: TaskRequest, request: Request):
    task = data.task.strip()
    if not task:
        raise HTTPException(status_code=422, detail="Task must contain non-whitespace characters")
    _session(request.app, session_id)
    record = _store(request.app).create_task(session_id, task, data.payload or {})
    _store(request.app).add_message(session_id, "user", task, record["id"])
    _schedule(request.app, record["id"])
    return record


@app.get("/api/v1/sessions/{session_id}/events")
async def get_session_events(session_id: str, request: Request, after: int = 0):
    _session(request.app, session_id)
    return {"events": _store(request.app).list_events(session_id, max(after, 0)),
            "protocol_version": PROTOCOL_VERSION}


def _workspace_root(application: FastAPI) -> Path:
    registry = getattr(application.state.orchestrator, "skill_registry", None)
    for record in getattr(registry, "_registry", {}).values():
        handler = getattr(record, "handler", None)
        root = getattr(handler, "workspace_root", None)
        if root is not None:
            return Path(root).resolve()
    return Path.cwd().resolve()


@app.get("/api/v1/workspace")
async def workspace_info(request: Request):
    root = _workspace_root(request.app)
    return {"root": str(root), "read_only": True, "protocol_version": PROTOCOL_VERSION}


@app.get("/api/v1/workspace/files")
async def list_workspace_files(request: Request, path: str = ""):
    root = _workspace_root(request.app)
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = root / target
    try:
        target = target.resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Folder not found") from exc
    if not target.is_relative_to(root) or not target.is_dir():
        raise HTTPException(status_code=403, detail="Folder is outside the workspace")
    directories, files = [], []
    try:
        for item in sorted(target.iterdir(), key=lambda value: value.name.lower()):
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            resolved = item.resolve()
            if not resolved.is_relative_to(root):
                continue
            record = {"name": item.name, "path": str(item.relative_to(root)).replace("\\", "/"),
                      "is_directory": item.is_dir()}
            (directories if item.is_dir() else files).append(record)
    except OSError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"path": "" if target == root else str(target.relative_to(root)).replace("\\", "/"),
            "directories": directories[:100], "files": files[:250], "protocol_version": PROTOCOL_VERSION}


@app.get("/api/v1/approvals")
async def list_approvals(request: Request):
    return {"approvals": _store(request.app).list_approvals(), "protocol_version": PROTOCOL_VERSION}


@app.get("/api/v1/approvals/pending")
async def list_pending_approvals(request: Request):
    pending = [a for a in _store(request.app).list_approvals() if a["status"] == "pending"]
    return {"approvals": pending, "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v1/approvals")
async def create_approval(data: ApprovalRequest, request: Request):
    session_id = _store(request.app).create_session(data.action[:160])["id"]
    task = _store(request.app).create_task(session_id, data.action, data.details or {})
    _store(request.app).update_task(task["id"], status="approval_required", success=False,
                                    error="Human approval required", completed_at=utc_now())
    return _store(request.app).create_approval(_store(request.app).get_task(task["id"]), data.risk_level)


async def _decide_approval(approval_id: str, request: Request, approved: bool) -> dict[str, Any]:
    approval = _store(request.app).get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval["status"] != "pending":
        raise HTTPException(status_code=409, detail="Approval has already been decided")
    if approved:
        original = _store(request.app).get_task(approval["task_id"])
        if original is None:
            raise HTTPException(status_code=409, detail="Associated task no longer exists")
        # Claim the decision before execution: concurrent requests must not run
        # a privileged action twice.
        if not _store(request.app).decide_approval(approval_id, "approved"):
            raise HTTPException(status_code=409, detail="Approval has already been decided")
        result = await _run_task(
            request.app, original["task"], original.get("payload"),
            approval_id=approval_id, session_id=original["session_id"],
        )
        _store(request.app).link_approval_execution(approval_id, result["id"])
    else:
        if not _store(request.app).decide_approval(approval_id, "rejected"):
            raise HTTPException(status_code=409, detail="Approval has already been decided")
        task = _store(request.app).get_task(approval["task_id"])
        if task:
            _store(request.app).add_message(task["session_id"], "assistant", "Действие отклонено и не будет выполнено.", task["id"])
    return _store(request.app).get_approval(approval_id)


@app.post("/api/v1/approvals/{approval_id}/approve")
async def approve_request(approval_id: str, request: Request):
    return await _decide_approval(approval_id, request, True)


@app.post("/api/v1/approvals/{approval_id}/reject")
async def reject_request(approval_id: str, request: Request):
    return await _decide_approval(approval_id, request, False)


@app.get("/api/v1/logs")
async def get_logs(request: Request, limit: int = 100):
    limit = max(1, min(limit, 1000))
    return {"logs": request.app.state.logs[-limit:], "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v1/logs")
async def add_log(log: dict[str, Any], request: Request):
    entry = dict(log)
    entry.update(timestamp=utc_now(), protocol_version=PROTOCOL_VERSION)
    request.app.state.logs.append(entry)
    return entry


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    expected_token = os.getenv("SYNAPSE_API_KEY")
    token = websocket.query_params.get("token")
    if not expected_token or not token or not secrets.compare_digest(token, expected_token):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    await websocket.accept()
    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "Invalid JSON",
                                           "protocol_version": PROTOCOL_VERSION})
                continue
            await websocket.send_json({"type": "echo", "data": message,
                                       "protocol_version": PROTOCOL_VERSION})
    except WebSocketDisconnect:
        return


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard.html", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse((TEMPLATES / "dashboard.html").read_text(encoding="utf-8"))


@app.get("/{page_name}.html", response_class=HTMLResponse)
async def html_page(page_name: str):
    if page_name not in {"providers", "agents", "settings"}:
        raise HTTPException(status_code=404, detail="Page not found")
    return HTMLResponse((TEMPLATES / f"{page_name}.html").read_text(encoding="utf-8"))


def create_app(orchestrator=None, checkpoint_manager=None, rollback_manager=None):
    """Create an isolated API instance for tests and embedded use."""
    application = FastAPI(title="Synapse API", version="3.4.1")
    application.state.orchestrator = orchestrator
    application.state.checkpoint_manager = checkpoint_manager
    application.state.rollback_manager = rollback_manager
    application.state.tasks = []
    application.state.approvals = []
    application.state.logs = []

    @application.get("/health")
    async def health():
        return {"status": "healthy", "version": "3.4.1", "protocol_version": PROTOCOL_VERSION}

    @application.get("/metrics")
    async def metrics():
        return {"metrics": {}, "protocol_version": PROTOCOL_VERSION}

    @application.post("/task")
    async def execute_task(data: TaskRequest):
        if orchestrator is None:
            raise HTTPException(status_code=503, detail="No orchestrator configured")
        outcome = await orchestrator.handle({"task": data.task, "payload": data.payload or {}})
        return {"status": outcome.get("status", "failed"), "success": bool(outcome.get("success", False)),
                "error": outcome.get("error"), "result": outcome.get("result", outcome),
                "protocol_version": PROTOCOL_VERSION}

    @application.get("/agents")
    async def list_agents():
        return {"agents": [], "protocol_version": PROTOCOL_VERSION}

    @application.post("/checkpoint")
    async def create_checkpoint(data: dict[str, Any]):
        if checkpoint_manager is None:
            raise HTTPException(status_code=503, detail="No checkpoint manager configured")
        checkpoint = await _maybe_await(checkpoint_manager.create_checkpoint(
            agent_id=data.get("agent_id", "default"), session_id=data.get("session_id", "default"),
        ))
        return {"checkpoint_id": checkpoint.id if hasattr(checkpoint, "id") else str(checkpoint),
                "protocol_version": PROTOCOL_VERSION}

    @application.post("/rollback")
    async def execute_rollback(data: dict[str, Any]):
        if rollback_manager is None:
            raise HTTPException(status_code=503, detail="No rollback manager configured")
        await _maybe_await(rollback_manager.rollback_to(data.get("checkpoint_id")))
        return {"status": "rolled_back", "protocol_version": PROTOCOL_VERSION}

    @application.get("/cluster/status")
    async def cluster_status():
        return {"status": "operational", "nodes": 1, "protocol_version": PROTOCOL_VERSION}

    return application
