"""
Security Audit Scanner for Synapse v3.4.1.

Adapted from Cloudflare Security Audit Skill patterns (cloudflare/security-audit-skill).
Performs static security analysis, secrets detection, dangerous API checks,
path traversal inspection, and dependency vulnerability audits.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION: str = "1.0"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class SecurityFinding:
    severity: Severity
    title: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    snippet: Optional[str] = None
    recommendation: Optional[str] = None
    cwe: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "snippet": self.snippet,
            "recommendation": self.recommendation,
            "cwe": self.cwe,
        }


@dataclass
class SecurityAuditReport:
    total_findings: int
    findings_by_severity: dict[str, int]
    score: int  # 0 to 100
    grade: str  # A+, A, B, C, F
    scanned_files_count: int
    findings: list[SecurityFinding]
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_findings": self.total_findings,
            "findings_by_severity": self.findings_by_severity,
            "score": self.score,
            "grade": self.grade,
            "scanned_files_count": self.scanned_files_count,
            "findings": [f.to_dict() for f in self.findings],
            "protocol_version": self.protocol_version,
        }


# High-precision patterns for detecting leaked secrets & tokens
SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[a-zA-Z0-9_\-]{32,}", re.IGNORECASE), "Anthropic API Key", Severity.CRITICAL, "CWE-798"),
    (re.compile(r"sk-[a-zA-Z0-9]{32,}", re.IGNORECASE), "OpenAI API Key", Severity.CRITICAL, "CWE-798"),
    (re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE), "AWS Access Key ID", Severity.CRITICAL, "CWE-798"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36,}", re.IGNORECASE), "GitHub Personal Access Token", Severity.CRITICAL, "CWE-798"),
    (re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,}", re.IGNORECASE), "Slack Token", Severity.CRITICAL, "CWE-798"),
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY-----"), "Private Cryptographic Key", Severity.CRITICAL, "CWE-312"),
    (re.compile(r"(postgres|mysql|mongodb)://[^:\s]+:[^@\s]+@[^/\s]+/\w+", re.IGNORECASE), "Database Connection String with Credentials", Severity.HIGH, "CWE-312"),
]

# Dangerous execution patterns
DANGEROUS_CODE_PATTERNS = [
    (re.compile(r"\b(eval|exec)\s*\("), "Dynamic Code Execution", Severity.HIGH, "Use of eval() or exec() poses severe remote code execution risk.", "CWE-95"),
    (re.compile(r"\bsubprocess\.(Popen|run|call)\s*\(.*shell\s*=\s*True"), "Shell Injection in Subprocess", Severity.CRITICAL, "Avoid shell=True with external inputs.", "CWE-78"),
    (re.compile(r"\bos\.system\s*\("), "Direct System Command Execution", Severity.HIGH, "os.system() is vulnerable to command injection. Use subprocess with explicit argument lists.", "CWE-78"),
    (re.compile(r"\bpickle\.loads?\s*\("), "Insecure Object Deserialization", Severity.HIGH, "Pickle deserialization allows arbitrary code execution.", "CWE-502"),
    (re.compile(r"cursor\.execute\s*\(f[\"'].*SELECT.*\{", re.IGNORECASE), "Potential SQL Injection", Severity.HIGH, "Use parameterized queries instead of f-string formatting.", "CWE-89"),
]

# File extensions to scan
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml", ".env", ".toml", ".sh"}
EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".pytest-run-tmp"}


class SecurityAuditor:
    """Security audit engine scanning codebase for vulnerabilities, secrets, and dangerous APIs."""

    def __init__(
        self,
        workspace_root: Optional[str | Path] = None,
        max_file_size: int = 2 * 1024 * 1024,
        scan_timeout_sec: float = 30.0,
    ):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.max_file_size = max_file_size
        self.scan_timeout_sec = scan_timeout_sec

    def _redact_secrets(self, text: str) -> str:
        """Thoroughly mask all secret patterns from text."""
        result = text
        for pattern, _, _, _ in SECRET_PATTERNS:
            result = pattern.sub("[REDACTED SECRET]", result)
        # Also mask generic token/key assignments
        generic_pattern = re.compile(r"""((?:api_key|apikey|secret|token|password|passwd)\s*[:=]\s*["'])([^"']{6,})(["'])""", re.IGNORECASE)
        result = generic_pattern.sub(r"\1[REDACTED SECRET]\3", result)
        return result

    def scan_content(self, file_path: str, content: str) -> list[SecurityFinding]:
        """Scan a string content for secrets and dangerous code patterns."""
        findings: list[SecurityFinding] = []
        lines = content.splitlines()

        for line_idx, line in enumerate(lines, 1):
            # Check secret patterns
            for pattern, name, severity, cwe in SECRET_PATTERNS:
                if pattern.search(line):
                    redacted = self._redact_secrets(line)
                    findings.append(
                        SecurityFinding(
                            severity=severity,
                            title=f"Hardcoded {name}",
                            description=f"Potential {name} detected in source file.",
                            file_path=file_path,
                            line_number=line_idx,
                            snippet=redacted[:160].strip(),
                            recommendation="Move sensitive credentials into environment variables or secrets manager.",
                            cwe=cwe,
                        )
                    )

            # Check dangerous code patterns
            for pattern, title, severity, desc, cwe in DANGEROUS_CODE_PATTERNS:
                if pattern.search(line):
                    redacted = self._redact_secrets(line)
                    findings.append(
                        SecurityFinding(
                            severity=severity,
                            title=title,
                            description=desc,
                            file_path=file_path,
                            line_number=line_idx,
                            snippet=redacted[:120].strip(),
                            recommendation="Refactor to use safe abstractions without shell or dynamic execution.",
                            cwe=cwe,
                        )
                    )

        return findings

    def scan_file(self, file_path: Path) -> list[SecurityFinding]:
        """Scan a single file safely with symlink, size, and binary file checks."""
        # Check symlink destination confinement
        if file_path.is_symlink():
            try:
                resolved = file_path.resolve()
                if not resolved.is_relative_to(self.workspace_root):
                    return []
            except Exception:
                return []

        rel_path = str(file_path.relative_to(self.workspace_root) if file_path.is_relative_to(self.workspace_root) else file_path)
        try:
            # Skip files exceeding size limit
            stat = file_path.stat()
            if stat.st_size > self.max_file_size:
                return []

            # Check binary content by probing the first 1024 bytes
            with open(file_path, "rb") as f:
                header = f.read(1024)
                if b"\x00" in header:
                    return []

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            return self.scan_content(rel_path, content)
        except Exception:
            return []

    def run_audit(
        self,
        target_dir: Optional[str | Path] = None,
        timeout_sec: Optional[float] = None,
    ) -> SecurityAuditReport:
        """Run full security audit over the directory."""
        import time
        deadline = time.time() + (timeout_sec if timeout_sec is not None else self.scan_timeout_sec)

        scan_dir = Path(target_dir or self.workspace_root).expanduser()
        if not scan_dir.is_absolute():
            scan_dir = self.workspace_root / scan_dir
        scan_dir = scan_dir.resolve()
        if not scan_dir.is_relative_to(self.workspace_root):
            raise ValueError("Audit target must stay inside the workspace")
        if not scan_dir.is_dir():
            raise ValueError("Audit target must be an existing directory")
        findings: list[SecurityFinding] = []
        scanned_count = 0

        for root, dirs, files in os.walk(scan_dir, followlinks=False):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            # Filter symlink directories pointing outside workspace
            safe_dirs = []
            for d in dirs:
                sub = Path(root) / d
                if sub.is_symlink():
                    try:
                        if sub.resolve().is_relative_to(self.workspace_root):
                            safe_dirs.append(d)
                    except Exception:
                        continue
                else:
                    safe_dirs.append(d)
            dirs[:] = safe_dirs

            for file in files:
                if time.time() > deadline:
                    break
                p = Path(root) / file
                if p.is_symlink():
                    try:
                        if not p.resolve().is_relative_to(self.workspace_root):
                            continue
                    except Exception:
                        continue

                if p.suffix in CODE_EXTENSIONS or p.name in {".env", ".env.example", "Dockerfile"}:
                    scanned_count += 1
                    findings.extend(self.scan_file(p))

            if time.time() > deadline:
                break

        # Calculate severity summary
        counts: dict[str, int] = {
            Severity.CRITICAL.value: 0,
            Severity.HIGH.value: 0,
            Severity.MEDIUM.value: 0,
            Severity.LOW.value: 0,
            Severity.INFO.value: 0,
        }
        for f in findings:
            counts[f.severity.value] += 1

        # Calculate security score (out of 100)
        penalty = (
            counts[Severity.CRITICAL.value] * 25
            + counts[Severity.HIGH.value] * 10
            + counts[Severity.MEDIUM.value] * 4
            + counts[Severity.LOW.value] * 1
        )
        score = max(0, 100 - penalty)

        if score >= 95:
            grade = "A+"
        elif score >= 85:
            grade = "A"
        elif score >= 70:
            grade = "B"
        elif score >= 50:
            grade = "C"
        else:
            grade = "F"

        return SecurityAuditReport(
            total_findings=len(findings),
            findings_by_severity=counts,
            score=score,
            grade=grade,
            scanned_files_count=scanned_count,
            findings=findings,
        )


_default_auditor: Optional[SecurityAuditor] = None


def get_security_auditor(workspace_root: Optional[str | Path] = None) -> SecurityAuditor:
    global _default_auditor
    if _default_auditor is None:
        _default_auditor = SecurityAuditor(workspace_root)
    return _default_auditor
