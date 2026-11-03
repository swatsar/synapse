"""
Acceptance Test Suite for Etap A: Truthful Outcomes and Execution Boundaries (A1–A7).

Verifies:
- A1: Safe AST manifest loading without server-side module exec; capability gating at load time.
- A2: Capability manager revocation, context expiration, and isolated context checks without bypass.
- A3: InvocationService mediation for platform actions, receipts, budgets, and human approval gates.
- A4: Subprocess/container isolation boundary, no silent fallback to LocalOS, fail-closed container requirement.
- A5: Truthful execution reporting in Hallmark and optimization engines; syntax and simulator awareness.
- A6: Audit scanner path traversal confinement, symlink safety, and secret masking in snippets.
- A7: Atomic multi-file patching with preimage SHA-256 verification, duplicate path rejection, and LIFO rollback.
"""

import os
import sys
import pytest
from pathlib import Path

from synapse.core.models import ExecutionContext
from synapse.security.capability_manager import CapabilityManager, CapabilityError
from synapse.security.execution_guard import ExecutionGuard
from synapse.skills.dynamic.registry import SkillRegistry
from synapse.runtime.worker_backend import IsolatedWorkerBackend, is_docker_available
from synapse.environment.docker_env import DockerEnv
from synapse.api.invocation_service import InvocationService, InvocationContext
from synapse.integrations.codex_engine import CodexEngine, FilePatch
from synapse.security.audit_scanner import SecurityAuditor, Severity
from synapse.harnesses.hallmark import HallmarkHarness, BenchmarkTask, BenchmarkCategory


pytestmark = pytest.mark.asyncio


# -------------------------------------------------------------
# A1: AST Manifest Parsing & Capability Gating
# -------------------------------------------------------------
async def test_a1_ast_loading_does_not_execute_server_code(tmp_path):
    """Untrusted skill files must be parsed via AST without running code in the host process."""
    sentinel_file = tmp_path / "sentinel.txt"
    skill_file = tmp_path / "malicious_skill.py"
    skill_file.write_text(f"""
import os
# Side-effect that would execute if imported
with open(r"{sentinel_file}", "w") as f:
    f.write("EXECUTED_ON_IMPORT")

manifest = {{
    "name": "malicious_skill",
    "version": "1.0",
    "required_capabilities": ["restricted:admin"],
    "handler": "run_skill"
}}

def run_skill():
    return {{"status": "pwned"}}
""", encoding="utf-8")

    cap_mgr = CapabilityManager()
    # Notice: restricted:admin is NOT granted
    registry = SkillRegistry(capability_manager=cap_mgr)

    # Attempt to load untrusted skill must fail due to missing capability
    with pytest.raises((CapabilityError, PermissionError)):
        await registry.load_from_path(str(skill_file))

    # Assert sentinel file was NEVER created (module was not imported)
    assert not sentinel_file.exists(), "Untrusted module was imported into server process!"
    assert "malicious_skill" not in registry.list_skills()


# -------------------------------------------------------------
# A2: Capability Token & Context Expiration
# -------------------------------------------------------------
async def test_a2_context_capabilities_cannot_bypass_restrictions():
    """Context with restricted capabilities cannot use ungranted global capabilities."""
    cap_mgr = CapabilityManager()
    cap_mgr.grant("global:read")
    cap_mgr.grant("global:write")

    # Context that only has global:read
    restricted_ctx = ExecutionContext(
        session_id="s1",
        agent_id="worker_1",
        trace_id="t1",
        capabilities=["global:read"]
    )

    assert await cap_mgr.check_capability(restricted_ctx, "global:read") is True
    # global:write is globally granted, but NOT in restricted_ctx! Must fail.
    assert await cap_mgr.check_capability(restricted_ctx, "global:write") is False

    # Expired context must fail all checks
    expired_ctx = ExecutionContext(
        session_id="s2",
        agent_id="worker_2",
        trace_id="t2",
        capabilities=["global:read"]
    )
    # Mark expired
    object.__setattr__(expired_ctx, "is_expired", True)
    assert await cap_mgr.check_capability(expired_ctx, "global:read") is False


# -------------------------------------------------------------
# A3: InvocationService Mediation & Approval Gate
# -------------------------------------------------------------
async def test_a3_invocation_service_enforces_approval_and_receipts(tmp_path):
    """High-risk actions require explicit approval; successful actions generate receipts."""
    service = InvocationService()
    service.capability_manager.grant("system:action")

    # 1. Unapproved high-risk invocation must be rejected
    unapproved_ctx = InvocationContext(
        identity="user_alice",
        run_id="run_101",
        approval_granted=False,
        capabilities=["system:action"],
    )
    res = await service.invoke(
        action_type="system",
        action_name="reboot",
        handler=lambda: {"done": True},
        context=unapproved_ctx,
        required_capabilities=["system:action"],
        risk_level=3,
    )
    assert res.success is False
    assert res.requires_approval is True
    assert "requires explicit human approval" in (res.error or "")

    # 2. Approved invocation succeeds and emits receipt
    approved_ctx = InvocationContext(
        identity="user_alice",
        run_id="run_102",
        approval_granted=True,
        capabilities=["system:action"],
    )
    res_ok = await service.invoke(
        action_type="system",
        action_name="reboot",
        handler=lambda: {"done": True},
        context=approved_ctx,
        required_capabilities=["system:action"],
        risk_level=3,
    )
    assert res_ok.success is True
    assert res_ok.receipt["run_id"] == "run_102"
    assert res_ok.receipt["identity"] == "user_alice"
    assert res_ok.receipt["action_name"] == "reboot"


# -------------------------------------------------------------
# A4: Subprocess Execution & Docker Fallback Prohibition
# -------------------------------------------------------------
async def test_a4_subprocess_worker_runs_in_different_pid():
    """Isolated worker subprocesses must execute outside the server PID."""
    backend = IsolatedWorkerBackend()
    code = """
import os
def handler():
    return {"pid": os.getpid(), "success": True}
"""
    result = await backend.run_skill("pid_test", code, isolation_level="subprocess")
    assert result.get("success") is True
    assert result.get("worker_pid") != os.getpid()
    assert result.get("output", {}).get("pid") != os.getpid()


async def test_a4_docker_fails_closed_without_local_fallback():
    """If Docker daemon is unavailable, container env must fail closed instead of silently falling back."""
    if not is_docker_available():
        with pytest.raises(RuntimeError, match="LocalOS fallback is prohibited for container isolation"):
            DockerEnv(mode="production")


# -------------------------------------------------------------
# A5: Hallmark Syntactic Validation & Honest Failure
# -------------------------------------------------------------
async def test_a5_hallmark_rejects_syntactically_invalid_code():
    """Coding benchmark tasks must reject broken Python syntax instead of granting false passes."""
    task = BenchmarkTask(
        id="code_fib",
        name="Fibonacci",
        category=BenchmarkCategory.CODING,
        prompt="Write async fib",
        expected_keywords=["async def", "yield", "while"],
    )
    # Text with required keywords but invalid syntax
    invalid_code = "async def yield while"
    eval_result = task.evaluate_output(invalid_code, latency_ms=10.0)

    assert eval_result["passed"] is False
    assert eval_result["score"] == 0.0
    assert "Invalid code syntax" in eval_result.get("error", "")


async def test_a5_hallmark_fails_closed_in_production_without_executor():
    """In production mode (require_executor=True), missing executor returns Grade F."""
    harness = HallmarkHarness()
    result = await harness.run_benchmark(executor_func=None, require_executor=True)
    assert result.grade == "F"
    assert result.passed_tasks == 0
    assert result.is_simulated is False


# -------------------------------------------------------------
# A6: Security Auditor Traversal & Secret Masking
# -------------------------------------------------------------
async def test_a6_security_auditor_masks_secrets_and_rejects_escape(tmp_path):
    """Audit scanner masks cleartext secrets in snippets and rejects workspace escapes."""
    auditor = SecurityAuditor(workspace_root=tmp_path)

    # 1. File with secret
    secret_file = tmp_path / "secret.env"
    raw_secret = "sk-ant-api03-1234567890abcdef1234567890abcdef1234567890abcdef"
    secret_file.write_text(f"API_KEY = '{raw_secret}'\n", encoding="utf-8")

    report = auditor.run_audit()
    assert report.total_findings >= 1
    # Check that cleartext secret was redacted
    for finding in report.findings:
        assert raw_secret not in finding.snippet
        assert "[REDACTED SECRET]" in finding.snippet

    # 2. Path escape attempt
    outside = tmp_path.parent / "escape_dir"
    outside.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="inside the workspace"):
        auditor.run_audit(outside)


# -------------------------------------------------------------
# A7: Atomic Multi-File Patch Preimage & LIFO Rollback
# -------------------------------------------------------------
async def test_a7_atomic_patch_verifies_preimage_and_duplicates(tmp_path):
    """CodexEngine atomic patch enforces preimage SHA-256 and rejects duplicates."""
    codex = CodexEngine(workspace_root=tmp_path)
    target_file = tmp_path / "script.py"
    target_file.write_text("original_version = 1\n", encoding="utf-8")

    # 1. Duplicate path in batch must fail immediately
    p1 = codex.create_patch("script.py", "original_version = 2\n")
    p2 = codex.create_patch("script.py", "original_version = 3\n")
    with pytest.raises(ValueError, match="Duplicate file path in patch batch"):
        codex.apply_patches_atomically([p1, p2])
    assert target_file.read_text(encoding="utf-8") == "original_version = 1\n"

    # 2. Preimage hash mismatch (concurrent change) must fail before applying
    p3 = codex.create_patch("script.py", "original_version = 2\n")
    # Simulate external file modification
    target_file.write_text("concurrent_version = 99\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Preimage hash mismatch"):
        codex.apply_patches_atomically([p3])
    # The disk content is preserved, not overwritten
    assert target_file.read_text(encoding="utf-8") == "concurrent_version = 99\n"


async def test_a7_atomic_patch_lifo_rollback_preserves_tree(tmp_path):
    """When a patch in a multi-file batch fails, previously written files are rolled back LIFO."""
    codex = CodexEngine(workspace_root=tmp_path)
    f1 = tmp_path / "f1.py"
    f1.write_text("file1_initial", encoding="utf-8")

    patch_valid = codex.create_patch("f1.py", "file1_new_content")
    # Patch escaping workspace root
    patch_invalid = FilePatch(
        file_path="../outside.py",
        original_content="",
        updated_content="malicious",
        diff_text="",
    )

    with pytest.raises(PermissionError):
        codex.apply_patches_atomically([patch_valid, patch_invalid])

    # Assert f1 was rolled back to initial state
    assert f1.read_text(encoding="utf-8") == "file1_initial"
