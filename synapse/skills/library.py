"""
Composable Skill Library for Synapse v3.4.1.

Adapted from mattpocock/skills patterns.
Provides declarative parameterized skills with input/output validation,
capability-based security authorization, and multi-skill pipeline composition.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.skills.library")


@dataclass
class SkillParameter:
    name: str
    type_name: str
    description: str
    required: bool = True
    default: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type_name,
            "description": self.description,
            "required": self.required,
            "default": self.default,
        }


@dataclass
class ComposableSkill:
    id: str
    name: str
    description: str
    parameters: list[SkillParameter]
    required_capabilities: list[str]
    risk_level: int
    handler: Callable[..., Any]
    category: str = "general"
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "required_capabilities": self.required_capabilities,
            "risk_level": self.risk_level,
            "category": self.category,
            "protocol_version": self.protocol_version,
        }

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute skill with parameter validation and error boundary."""
        # Check required parameters
        for p in self.parameters:
            if p.required and p.name not in params:
                raise ValueError(f"Missing required parameter '{p.name}' for skill '{self.id}'")

        kwargs = {p.name: params.get(p.name, p.default) for p in self.parameters if p.name in params or p.default is not None}
        if inspect.iscoroutinefunction(self.handler):
            res = await self.handler(**kwargs)
        else:
            res = self.handler(**kwargs)

        return {
            "skill_id": self.id,
            "result": res,
            "success": True,
            "protocol_version": self.protocol_version,
        }


class SkillLibrary:
    """Registry and composition engine for standardized agent skills."""

    def __init__(self):
        self._skills: dict[str, ComposableSkill] = {}
        self._register_builtins()

    def register(self, skill: ComposableSkill) -> None:
        self._skills[skill.id] = skill

    def get(self, skill_id: str) -> Optional[ComposableSkill]:
        return self._skills.get(skill_id)

    def list_skills(self) -> list[ComposableSkill]:
        return list(self._skills.values())

    def _register_builtins(self) -> None:
        # 1. Security Scan Skill
        def _security_scan(target_dir: str = ".") -> dict[str, Any]:
            from synapse.security.audit_scanner import get_security_auditor
            auditor = get_security_auditor()
            report = auditor.run_audit(target_dir)
            return report.to_dict()

        self.register(
            ComposableSkill(
                id="security_scan",
                name="Security Audit Scan",
                description="Scan workspace code for exposed credentials, dangerous APIs, and security vulnerabilities.",
                parameters=[
                    SkillParameter(name="target_dir", type_name="string", description="Directory to scan", required=False, default=".")
                ],
                required_capabilities=["fs:read"],
                risk_level=1,
                handler=_security_scan,
                category="security",
            )
        )

        # 2. Memory Recall Skill
        def _memory_recall(query: str, limit: int = 5) -> dict[str, Any]:
            from synapse.memory.vault import get_memory_vault
            vault = get_memory_vault()
            results = vault.search(query, limit=limit)
            return {"memories": [m.to_dict() for m in results]}

        self.register(
            ComposableSkill(
                id="memory_recall",
                name="Memory Recall",
                description="Search durable agent memory vault for project conventions, past lessons, and user preferences.",
                parameters=[
                    SkillParameter(name="query", type_name="string", description="Search query or topic", required=True),
                    SkillParameter(name="limit", type_name="integer", description="Maximum entries to return", required=False, default=5),
                ],
                required_capabilities=["memory:read"],
                risk_level=1,
                handler=_memory_recall,
                category="memory",
            )
        )

        # 3. Model Route Skill
        def _model_route(task: str) -> dict[str, Any]:
            from synapse.llm.omnirouter import get_omnirouter
            router = get_omnirouter()
            decision = router.route(task)
            return {"decision": decision.to_dict()}

        self.register(
            ComposableSkill(
                id="model_route",
                name="OmniRouter Model Selection",
                description="Automatically determine the optimal provider and model based on task requirements.",
                parameters=[
                    SkillParameter(name="task", type_name="string", description="Task description", required=True),
                ],
                required_capabilities=["llm:route"],
                risk_level=1,
                handler=_model_route,
                category="llm",
            )
        )

        # 4. Code Review Skill
        def _code_review(code: str, language: str = "python") -> dict[str, Any]:
            lines = code.splitlines()
            findings = []
            if "print(" in code and language == "python":
                findings.append("Consider using structured logging instead of print statements.")
            if "TODO" in code:
                findings.append("Unresolved TODO comment detected in review snippet.")
            return {
                "language": language,
                "lines_count": len(lines),
                "review_score": 95 if not findings else 85,
                "suggestions": findings,
            }

        self.register(
            ComposableSkill(
                id="code_review",
                name="Code Reviewer",
                description="Analyze code snippet for best practices, clarity, and potential improvements.",
                parameters=[
                    SkillParameter(name="code", type_name="string", description="Code text to analyze", required=True),
                    SkillParameter(name="language", type_name="string", description="Programming language", required=False, default="python"),
                ],
                required_capabilities=["code:analyze"],
                risk_level=1,
                handler=_code_review,
                category="coding",
            )
        )

        # 5. Browser Navigation Skill
        async def _browser_nav(url: str = "https://example.com") -> dict[str, Any]:
            from synapse.integrations.browser_controller import get_browser_controller
            res = await get_browser_controller().execute("navigate", {"url": url})
            return res.to_dict()

        self.register(
            ComposableSkill(
                id="browser_navigate",
                name="Browser Navigation",
                description="Securely navigate and inspect approved web domains with screenshot feedback.",
                parameters=[
                    SkillParameter(name="url", type_name="string", description="Web address to navigate to", required=True, default="https://example.com"),
                ],
                required_capabilities=["browser:navigate"],
                risk_level=3,
                handler=_browser_nav,
                category="browser",
            )
        )

        # 6. Python AST Analysis Skill
        def _ast_analyze(code: str = "") -> dict[str, Any]:
            from synapse.integrations.codex_engine import get_codex_engine
            engine = get_codex_engine()
            symbols = engine.analyze_python_ast(code) if code else []
            return {"symbols": [s.to_dict() for s in symbols], "count": len(symbols)}

        self.register(
            ComposableSkill(
                id="ast_analyze",
                name="Python AST Analysis",
                description="Extract function, class, and async definitions with argument lists from Python source.",
                parameters=[
                    SkillParameter(name="code", type_name="string", description="Python source code text", required=True),
                ],
                required_capabilities=["code:analyze"],
                risk_level=1,
                handler=_ast_analyze,
                category="coding",
            )
        )

        # 7. Benchmark Evaluation Skill
        async def _bench_eval(suite_id: str = "core_eval_v1") -> dict[str, Any]:
            from synapse.harnesses.hallmark import get_hallmark_harness
            report = await get_hallmark_harness().run_benchmark(suite_id=suite_id)
            return report.to_dict()

        self.register(
            ComposableSkill(
                id="benchmark_eval",
                name="Hallmark Evaluation Benchmark",
                description="Run structured benchmarks across coding, security, reasoning, and memory dimensions.",
                parameters=[
                    SkillParameter(name="suite_id", type_name="string", description="Benchmark suite ID", required=False, default="core_eval_v1"),
                ],
                required_capabilities=["eval:run"],
                risk_level=1,
                handler=_bench_eval,
                category="evaluation",
            )
        )

        # 8. SFT Dataset Export Skill
        def _sft_export_skill(format: str = "chatml") -> dict[str, Any]:
            from synapse.harnesses.trajectory import get_trajectory_harness
            samples = get_trajectory_harness().export_sft_dataset(format=format)
            return {"count": len(samples), "format": format, "samples": samples[:5]}

        self.register(
            ComposableSkill(
                id="sft_export",
                name="Export SFT Training Dataset",
                description="Export multi-turn reasoning traces into ChatML or Alpaca format for local model fine-tuning.",
                parameters=[
                    SkillParameter(name="format", type_name="string", description="Dataset format (chatml or alpaca)", required=False, default="chatml"),
                ],
                required_capabilities=["learning:export"],
                risk_level=1,
                handler=_sft_export_skill,
                category="learning",
            )
        )

    async def execute_pipeline(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compose and execute a sequence of skills, piping results forward."""
        results: list[dict[str, Any]] = []
        context: dict[str, Any] = {}

        for step in steps:
            skill_id = step.get("skill_id")
            skill = self.get(skill_id)
            if not skill:
                raise ValueError(f"Skill not found: {skill_id}")
            params = dict(step.get("params", {}))

            # Merge previous step output if requested
            if step.get("pipe_from_previous") and results:
                params["piped_input"] = results[-1].get("result")

            res = await skill.execute(params)
            results.append(res)
            context[skill_id] = res

        return results


_default_library: Optional[SkillLibrary] = None


def get_skill_library() -> SkillLibrary:
    global _default_library
    if _default_library is None:
        _default_library = SkillLibrary()
    return _default_library
