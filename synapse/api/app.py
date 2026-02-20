"""Synapse Web API - FastAPI Application.

Protocol Version: 1.0
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import json
import asyncio

PROTOCOL_VERSION: str = "1.0"

app = FastAPI(
    title="Synapse Agent Platform",
    description="Universal Autonomous Agent Platform API",
    version="3.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
from synapse.api.routes import api_router
app.include_router(api_router, prefix="/api/v1")

# In-memory storage for demo
agents: Dict[str, Dict] = {}
approvals: List[Dict] = []
logs: List[Dict] = []
tasks: List[Dict] = []


# === Models ===

class TaskRequest(BaseModel):
    task: str
    payload: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    action: str
    risk_level: int
    details: Optional[Dict[str, Any]] = None


class ApprovalResponse(BaseModel):
    approval_id: str
    approved: bool


# === Health & Status ===

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "3.1.0",
        "protocol_version": PROTOCOL_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/status")
async def get_status():
    """Get system status."""
    return {
        "status": "operational",
        "agents_count": len(agents),
        "pending_approvals": len([a for a in approvals if a["status"] == "pending"]),
        "tasks_completed": len([t for t in tasks if t["status"] == "completed"]),
        "protocol_version": PROTOCOL_VERSION
    }


# === Tasks ===

@app.post("/api/v1/tasks")
async def create_task(request: TaskRequest):
    """Create and execute a task."""
    task_id = f"task_{len(tasks) + 1}"
    task = {
        "id": task_id,
        "task": request.task,
        "payload": request.payload,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION
    }
    tasks.append(task)
    return task


@app.get("/api/v1/tasks")
async def list_tasks():
    """List all tasks."""
    return {"tasks": tasks, "protocol_version": PROTOCOL_VERSION}


# === Approvals ===

@app.get("/api/v1/approvals")
async def list_approvals():
    """List all approval requests."""
    return {"approvals": approvals, "protocol_version": PROTOCOL_VERSION}


@app.get("/api/v1/approvals/pending")
async def list_pending_approvals():
    """List pending approval requests."""
    pending = [a for a in approvals if a["status"] == "pending"]
    return {"approvals": pending, "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v1/approvals")
async def create_approval(request: ApprovalRequest):
    """Create an approval request."""
    approval_id = f"approval_{len(approvals) + 1}"
    approval = {
        "id": approval_id,
        "action": request.action,
        "risk_level": request.risk_level,
        "details": request.details,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION
    }
    approvals.append(approval)
    return approval


@app.post("/api/v1/approvals/{approval_id}/approve")
async def approve_request(approval_id: str):
    """Approve a request."""
    for approval in approvals:
        if approval["id"] == approval_id:
            approval["status"] = "approved"
            approval["approved_at"] = datetime.now(timezone.utc).isoformat()
            return approval
    raise HTTPException(status_code=404, detail="Approval not found")


@app.post("/api/v1/approvals/{approval_id}/reject")
async def reject_request(approval_id: str):
    """Reject a request."""
    for approval in approvals:
        if approval["id"] == approval_id:
            approval["status"] = "rejected"
            approval["rejected_at"] = datetime.now(timezone.utc).isoformat()
            return approval
    raise HTTPException(status_code=404, detail="Approval not found")


# === Logs ===

@app.get("/api/v1/logs")
async def get_logs(limit: int = 100):
    """Get recent logs."""
    return {"logs": logs[-limit:], "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v1/logs")
async def add_log(log: Dict[str, Any]):
    """Add a log entry."""
    log["timestamp"] = datetime.now(timezone.utc).isoformat()
    log["protocol_version"] = PROTOCOL_VERSION
    logs.append(log)
    return log


# === WebSocket ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            response = {
                "type": "echo",
                "data": message,
                "protocol_version": PROTOCOL_VERSION
            }
            await websocket.send_json(response)
    except WebSocketDisconnect:
        pass


# === Dashboard HTML ===

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard HTML."""
    return HTMLResponse(content=DASHBOARD_HTML)


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Synapse Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid #333;
            margin-bottom: 30px;
        }
        h1 { font-size: 2em; color: #00d4ff; }
        .version { color: #888; font-size: 0.9em; }
        .nav { display: flex; gap: 15px; }
        .nav a { color: #00d4ff; text-decoration: none; padding: 8px 16px; border-radius: 6px; }
        .nav a:hover { background: rgba(0,212,255,0.1); }
        .nav a.active { background: #00d4ff; color: #000; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 { font-size: 1.2em; margin-bottom: 15px; color: #00d4ff; }
        .stat { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #333; }
        .stat:last-child { border-bottom: none; }
        .stat-value { font-weight: bold; color: #00ff88; }
        .status-healthy { color: #00ff88; }
        .status-pending { color: #ffaa00; }
        .btn {
            background: #00d4ff;
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            margin: 5px;
        }
        .btn:hover { background: #00a8cc; }
        .btn-danger { background: #ff4444; }
        .btn-success { background: #00ff88; }
        .task-input {
            width: 100%;
            padding: 12px;
            border-radius: 6px;
            border: 1px solid #333;
            background: rgba(255,255,255,0.05);
            color: #fff;
            margin-bottom: 10px;
        }
        .approval-item {
            background: rgba(255,255,255,0.03);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .risk-high { border-left: 3px solid #ff4444; }
        .risk-medium { border-left: 3px solid #ffaa00; }
        .risk-low { border-left: 3px solid #00ff88; }
        .log-entry {
            font-family: monospace;
            font-size: 0.85em;
            padding: 5px 0;
            border-bottom: 1px solid #222;
        }
        .refresh-btn { float: right; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🧠 Synapse Dashboard</h1>
                <span class="version">Protocol v1.0 | Spec v3.1</span>
            </div>
            <nav class="nav">
                <a href="/" class="active">Dashboard</a>
                <a href="/providers.html">Providers</a>
                <a href="/agents.html">Agents</a>
                <a href="/settings.html">Settings</a>
            </nav>
            <button class="btn refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        </header>
        
        <div class="grid">
            <!-- Status Card -->
            <div class="card">
                <h2>📊 System Status</h2>
                <div class="stat">
                    <span>Status</span>
                    <span class="stat-value status-healthy" id="status">Loading...</span>
                </div>
                <div class="stat">
                    <span>Agents</span>
                    <span class="stat-value" id="agents-count">-</span>
                </div>
                <div class="stat">
                    <span>Pending Approvals</span>
                    <span class="stat-value" id="pending-count">-</span>
                </div>
                <div class="stat">
                    <span>Tasks Completed</span>
                    <span class="stat-value" id="tasks-count">-</span>
                </div>
            </div>
            
            <!-- Task Execution -->
            <div class="card">
                <h2>⚡ Execute Task</h2>
                <textarea class="task-input" id="task-input" rows="3" placeholder="Enter task description..."></textarea>
                <button class="btn" onclick="executeTask()">▶ Execute</button>
                <div id="task-result" style="margin-top: 15px;"></div>
            </div>
            
            <!-- Pending Approvals -->
            <div class="card">
                <h2>🔐 Pending Approvals</h2>
                <div id="approvals-list">Loading...</div>
            </div>
            
            <!-- Recent Logs -->
            <div class="card">
                <h2>📋 Recent Logs</h2>
                <div id="logs-list">Loading...</div>
            </div>
        </div>
    </div>
    
    <script>
        const API_BASE = '/api/v1';
        
        async function fetchStatus() {
            try {
                const res = await fetch(`${API_BASE}/status`);
                const data = await res.json();
                document.getElementById('status').textContent = data.status;
                document.getElementById('agents-count').textContent = data.agents_count;
                document.getElementById('pending-count').textContent = data.pending_approvals;
                document.getElementById('tasks-count').textContent = data.tasks_completed;
            } catch (e) {
                document.getElementById('status').textContent = 'Error';
            }
        }
        
        async function fetchApprovals() {
            try {
                const res = await fetch(`${API_BASE}/approvals/pending`);
                const data = await res.json();
                const list = document.getElementById('approvals-list');
                if (data.approvals.length === 0) {
                    list.innerHTML = '<p style="color: #888;">No pending approvals</p>';
                    return;
                }
                list.innerHTML = data.approvals.map(a => `
                    <div class="approval-item risk-${a.risk_level >= 4 ? 'high' : a.risk_level >= 2 ? 'medium' : 'low'}">
                        <strong>${a.action}</strong><br>
                        <small>Risk Level: ${a.risk_level}</small><br>
                        <button class="btn btn-success" onclick="approve('${a.id}')">✓ Approve</button>
                        <button class="btn btn-danger" onclick="reject('${a.id}')">✗ Reject</button>
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('approvals-list').innerHTML = '<p style="color: #ff4444;">Error loading approvals</p>';
            }
        }
        
        async function fetchLogs() {
            try {
                const res = await fetch(`${API_BASE}/logs?limit=10`);
                const data = await res.json();
                const list = document.getElementById('logs-list');
                if (data.logs.length === 0) {
                    list.innerHTML = '<p style="color: #888;">No logs yet</p>';
                    return;
                }
                list.innerHTML = data.logs.map(l => `
                    <div class="log-entry">${l.timestamp || 'N/A'} - ${l.message || JSON.stringify(l)}</div>
                `).join('');
            } catch (e) {
                document.getElementById('logs-list').innerHTML = '<p style="color: #ff4444;">Error loading logs</p>';
            }
        }
        
        async function executeTask() {
            const task = document.getElementById('task-input').value;
            if (!task) return alert('Please enter a task');
            
            try {
                const res = await fetch(`${API_BASE}/tasks`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({task})
                });
                const data = await res.json();
                document.getElementById('task-result').innerHTML = 
                    `<div style="color: #00ff88;">✓ Task created: ${data.id}</div>`;
                fetchStatus();
            } catch (e) {
                document.getElementById('task-result').innerHTML = 
                    `<div style="color: #ff4444;">Error: ${e.message}</div>`;
            }
        }
        
        async function approve(id) {
            try {
                await fetch(`${API_BASE}/approvals/${id}/approve`, {method: 'POST'});
                fetchApprovals();
                fetchStatus();
            } catch (e) {
                alert('Error approving: ' + e.message);
            }
        }
        
        async function reject(id) {
            try {
                await fetch(`${API_BASE}/approvals/${id}/reject`, {method: 'POST'});
                fetchApprovals();
                fetchStatus();
            } catch (e) {
                alert('Error rejecting: ' + e.message);
            }
        }
        
        // Initial load
        fetchStatus();
        fetchApprovals();
        fetchLogs();
        
        // Auto-refresh every 5 seconds
        setInterval(() => {
            fetchStatus();
            fetchApprovals();
            fetchLogs();
        }, 5000);
    </script>
</body>
</html>
"""


# === Static HTML Pages ===

@app.get("/providers.html", response_class=HTMLResponse)
async def providers_page():
    """Serve providers page."""
    from pathlib import Path
    html_path = Path(__file__).parent.parent / "ui" / "web" / "templates" / "providers.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="<h1>Providers page not found</h1>", status_code=404)


@app.get("/agents.html", response_class=HTMLResponse)
async def agents_page():
    """Serve agents page."""
    from pathlib import Path
    html_path = Path(__file__).parent.parent / "ui" / "web" / "templates" / "agents.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="<h1>Agents page not found</h1>", status_code=404)


@app.get("/settings.html", response_class=HTMLResponse)
async def settings_page():
    """Serve settings page."""
    from pathlib import Path
    html_path = Path(__file__).parent.parent / "ui" / "web" / "templates" / "settings.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="<h1>Settings page not found</h1>", status_code=404)


# === Factory Function for Testing ===

def create_app(orchestrator=None, checkpoint_manager=None, rollback_manager=None):
    """
    Factory function to create a FastAPI app with injected dependencies.
    
    Used for testing and programmatic app creation.
    
    Args:
        orchestrator: Optional orchestrator instance
        checkpoint_manager: Optional checkpoint manager instance
        rollback_manager: Optional rollback manager instance
    
    Returns:
        FastAPI application instance
    """
    from fastapi import FastAPI
    from synapse.core.models import PROTOCOL_VERSION
    
    # Create new app instance
    app = FastAPI(
        title="Synapse API",
        version="3.1.0",
        description="Synapse Agent Platform API"
    )
    
    # Store injected dependencies in app state
    app.state.orchestrator = orchestrator
    app.state.checkpoint_manager = checkpoint_manager
    app.state.rollback_manager = rollback_manager
    app.state.protocol_version = PROTOCOL_VERSION
    
    # Add health endpoint
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "version": "3.1.0",
            "protocol_version": PROTOCOL_VERSION
        }
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        return {
            "metrics": {},
            "protocol_version": PROTOCOL_VERSION
        }
    
    # Add task endpoint
    @app.post("/task")
    async def execute_task(request: dict):
        if orchestrator:
            result = await orchestrator.handle(request)
            return {"status": "completed", "result": result, "protocol_version": PROTOCOL_VERSION}
        return {"status": "no_orchestrator", "protocol_version": PROTOCOL_VERSION}
    
    # Add agents endpoint
    @app.get("/agents")
    async def list_agents():
        return {
            "agents": [],
            "protocol_version": PROTOCOL_VERSION
        }
    
    # Add checkpoint endpoint
    @app.post("/checkpoint")
    async def create_checkpoint(request: dict):
        if checkpoint_manager:
            cp_id = checkpoint_manager.create_checkpoint(
                agent_id=request.get("agent_id", "default"),
                session_id=request.get("session_id", "default")
            )
            return {"checkpoint_id": cp_id.id if hasattr(cp_id, 'id') else str(cp_id), "protocol_version": PROTOCOL_VERSION}
        return {"status": "no_checkpoint_manager", "protocol_version": PROTOCOL_VERSION}
    
    # Add rollback endpoint
    @app.post("/rollback")
    async def execute_rollback(request: dict):
        if rollback_manager:
            rollback_manager.rollback_to(request.get("checkpoint_id"))
            return {"status": "rolled_back", "protocol_version": PROTOCOL_VERSION}
        return {"status": "no_rollback_manager", "protocol_version": PROTOCOL_VERSION}
    
    # Add cluster status endpoint
    @app.get("/cluster/status")
    async def cluster_status():
        return {
            "status": "operational",
            "nodes": 1,
            "protocol_version": PROTOCOL_VERSION
        }
    
    return app
