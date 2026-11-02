"""
Unit tests for SecurityAuditor (Cloudflare Security Audit Skill integration).
"""

import pytest
from pathlib import Path
from synapse.security.audit_scanner import SecurityAuditor, Severity, PROTOCOL_VERSION


@pytest.fixture
def auditor(tmp_path):
    return SecurityAuditor(workspace_root=tmp_path)


def test_protocol_version(auditor):
    report = auditor.run_audit()
    assert report.protocol_version == PROTOCOL_VERSION


def test_detect_hardcoded_secret(auditor, tmp_path):
    bad_file = tmp_path / "config.py"
    bad_file.write_text("ANTHROPIC_KEY = 'sk-ant-api03-1234567890abcdef1234567890abcdef1234567890abcdef'")

    report = auditor.run_audit()
    assert report.total_findings >= 1
    assert any(f.severity == Severity.CRITICAL for f in report.findings)
    assert any("Anthropic API Key" in f.title for f in report.findings)


def test_detect_dangerous_eval(auditor, tmp_path):
    bad_file = tmp_path / "calculator.py"
    bad_file.write_text("def run(expr):\n    return eval(expr)\n")

    report = auditor.run_audit()
    assert report.total_findings >= 1
    assert any("Dynamic Code Execution" in f.title for f in report.findings)


def test_clean_codebase_gets_high_grade(auditor, tmp_path):
    clean_file = tmp_path / "app.py"
    clean_file.write_text("def hello():\n    return 'Hello, clean world!'\n")

    report = auditor.run_audit()
    assert report.total_findings == 0
    assert report.score == 100
    assert report.grade == "A+"
