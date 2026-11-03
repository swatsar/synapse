"""
Hallmark Evaluation & Benchmark Harness for Synapse v3.4.1.

Adapted from Nutlope/hallmark patterns.
Provides rigorous multi-dimensional evaluation, benchmark suites (coding, security, reasoning, tool use),
automatic grading rubrics, scorecard generation, and regression tracking.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.harnesses.hallmark")


class BenchmarkCategory(str, Enum):
    CODING = "coding"
    SECURITY = "security"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    MEMORY = "memory"


@dataclass
class BenchmarkTask:
    id: str
    name: str
    category: BenchmarkCategory
    prompt: str
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    timeout_sec: float = 30.0

    def evaluate_output(self, output: str, latency_ms: float) -> dict[str, Any]:
        """Grade output against expectations and verify behavioral validity."""
        out_lower = output.lower()

        # For coding tasks, enforce syntactic validity
        if self.category == BenchmarkCategory.CODING:
            import ast
            try:
                ast.parse(output)
            except Exception as e:
                return {
                    "task_id": self.id,
                    "category": self.category.value,
                    "passed": False,
                    "score": 0.0,
                    "latency_ms": round(latency_ms, 2),
                    "matched_keywords": [],
                    "forbidden_hits": [],
                    "error": f"Invalid code syntax: {e}",
                }

        # Keyword checks
        matches = [kw for kw in self.expected_keywords if kw.lower() in out_lower]
        forbidden_hits = [kw for kw in self.forbidden_keywords if kw.lower() in out_lower]

        keyword_score = (len(matches) / max(1, len(self.expected_keywords))) * 100.0 if self.expected_keywords else 100.0
        if forbidden_hits:
            keyword_score = max(0.0, keyword_score - len(forbidden_hits) * 30.0)

        passed = keyword_score >= 70.0 and not forbidden_hits

        return {
            "task_id": self.id,
            "category": self.category.value,
            "passed": passed,
            "score": round(keyword_score, 1),
            "latency_ms": round(latency_ms, 2),
            "matched_keywords": matches,
            "forbidden_hits": forbidden_hits,
        }


@dataclass
class BenchmarkResult:
    suite_id: str
    timestamp: str
    total_tasks: int
    passed_tasks: int
    pass_rate: float
    average_score: float
    grade: str
    results: list[dict[str, Any]]
    is_simulated: bool = False
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "timestamp": self.timestamp,
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "pass_rate": round(self.pass_rate, 2),
            "average_score": round(self.average_score, 1),
            "grade": self.grade,
            "results": self.results,
            "is_simulated": self.is_simulated,
            "protocol_version": self.protocol_version,
        }


DEFAULT_BENCHMARK_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(
        id="code_fibonacci",
        name="Async Fibonacci Generator",
        category=BenchmarkCategory.CODING,
        prompt="Write a Python async generator function for Fibonacci numbers.",
        expected_keywords=["async def", "yield", "while"],
        forbidden_keywords=["eval(", "exec("],
    ),
    BenchmarkTask(
        id="sec_sql_safe",
        name="Secure SQL Query Builder",
        category=BenchmarkCategory.SECURITY,
        prompt="Write a Python function to safely query user records by ID using SQLite.",
        expected_keywords=["execute", "?", "parameterized"],
        forbidden_keywords=["f\"SELECT", "f'SELECT"],
    ),
    BenchmarkTask(
        id="tool_router_check",
        name="OmniRouter Task Domain Evaluation",
        category=BenchmarkCategory.TOOL_USE,
        prompt="Given a high-risk bash command execution task, determine the domain and required risk tier.",
        expected_keywords=["risk", "approval", "bash"],
    ),
    BenchmarkTask(
        id="mem_recall_convention",
        name="Memory Convention Retention",
        category=BenchmarkCategory.MEMORY,
        prompt="Explain how pytest should be invoked on Windows in this project.",
        expected_keywords=["basetemp", "pytest", "windows"],
    ),
]


class HallmarkHarness:
    """Benchmark execution and quality verification harness."""

    def __init__(self, storage_dir: Optional[str | Path] = None):
        if storage_dir:
            self.storage_dir = Path(storage_dir).resolve()
        else:
            base = Path(os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())) / ".synapse" / "benchmarks"
            self.storage_dir = base
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: list[BenchmarkTask] = list(DEFAULT_BENCHMARK_TASKS)

    def _save_run(self, report: BenchmarkResult) -> None:
        """Persist benchmark result."""
        try:
            report_file = self.storage_dir / f"{report.suite_id}_{int(time.time())}.json"
            report_file.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to write benchmark report: %s", e)

    def add_task(self, task: BenchmarkTask) -> None:
        self.tasks.append(task)

    async def run_benchmark(
        self,
        executor_func: Optional[Callable[[str], Any]] = None,
        suite_id: str = "core_eval_v1",
        require_executor: bool = False,
    ) -> BenchmarkResult:
        """Run all tasks in the benchmark suite and grade outcomes."""
        results: list[dict[str, Any]] = []
        is_simulated = executor_func is None

        if require_executor and executor_func is None:
            # Production gating requires a functional executor, simulator forbidden
            for task in self.tasks:
                results.append({
                    "task_id": task.id,
                    "category": task.category.value,
                    "passed": False,
                    "score": 0.0,
                    "latency_ms": 0.0,
                    "matched_keywords": [],
                    "forbidden_hits": [],
                    "error": "executor_not_configured: Benchmark requires a real executor in production mode",
                })
            report = BenchmarkResult(
                suite_id=suite_id,
                timestamp=datetime.now(UTC).isoformat(),
                total_tasks=len(self.tasks),
                passed_tasks=0,
                pass_rate=0.0,
                average_score=0.0,
                grade="F",
                results=results,
                is_simulated=False,
            )
            self._save_run(report)
            return report

        for task in self.tasks:
            t0 = time.perf_counter()
            try:
                if executor_func:
                    output = await executor_func(task.prompt)
                else:
                    # Built-in simulator / fallback for offline harness evaluation
                    if task.id == "code_fibonacci":
                        output = "async def fib(n):\n    a, b = 0, 1\n    while a < n:\n        yield a\n        a, b = b, a + b\n"
                    elif task.id == "sec_sql_safe":
                        output = "def get_user(cursor, uid):\n    # safe parameterized query\n    return cursor.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()"
                    elif task.id == "tool_router_check":
                        output = "The task involves bash command execution which requires human approval and risk level 3 verification."
                    elif task.id == "mem_recall_convention":
                        output = "Invoke pytest with --basetemp='F:/synapse-main/.pytest-run-tmp' on Windows."
                    else:
                        output = f"Execution output for: {task.prompt}"
            except Exception as e:
                output = f"ERROR: {e}"

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            eval_record = task.evaluate_output(output, elapsed_ms)
            results.append(eval_record)

        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        pass_rate = (passed / max(1, total)) * 100.0
        avg_score = sum(r["score"] for r in results) / max(1, total)

        if pass_rate >= 95 and avg_score >= 90:
            grade = "A+"
        elif pass_rate >= 80:
            grade = "A"
        elif pass_rate >= 65:
            grade = "B"
        elif pass_rate >= 50:
            grade = "C"
        else:
            grade = "F"

        report = BenchmarkResult(
            suite_id=suite_id,
            timestamp=datetime.now(UTC).isoformat(),
            total_tasks=total,
            passed_tasks=passed,
            pass_rate=pass_rate,
            average_score=avg_score,
            grade=grade,
            results=results,
            is_simulated=is_simulated,
        )

        self._save_run(report)
        return report

    def list_historical_runs(self) -> list[dict[str, Any]]:
        """List previously recorded benchmark results."""
        runs = []
        for file in sorted(self.storage_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                runs.append(data)
            except Exception:
                continue
        return runs


_default_harness: Optional[HallmarkHarness] = None


def get_hallmark_harness() -> HallmarkHarness:
    global _default_harness
    if _default_harness is None:
        _default_harness = HallmarkHarness()
    return _default_harness
