"""
Interactive Slash Command Engine for Synapse v3.4.1.

Adapted from anthropics/claude-code patterns.
Provides command routing, argument parsing, autocompletion metadata,
and unified invocation for /audit, /review, /memory, /bench, /model, and /diff.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import json
import logging
import shlex
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.interfaces.slash_engine")


@dataclass
class SlashCommandDef:
    name: str  # e.g. "audit", "memory", "bench"
    description: str
    usage: str
    handler: Callable[..., Any]
    category: str = "general"
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "usage": self.usage,
            "category": self.category,
            "protocol_version": self.protocol_version,
        }


@dataclass
class SlashCommandResult:
    command: str
    args: list[str]
    success: bool
    output: Any
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "args": self.args,
            "success": self.success,
            "output": self.output,
            "protocol_version": self.protocol_version,
        }


class SlashCommandEngine:
    """Parses and executes user slash commands."""

    def __init__(self):
        self._commands: dict[str, SlashCommandDef] = {}
        self._register_builtins()

    def register(self, cmd: SlashCommandDef) -> None:
        self._commands[cmd.name.lower().lstrip("/")] = cmd

    def get(self, name: str) -> Optional[SlashCommandDef]:
        return self._commands.get(name.lower().lstrip("/"))

    def list_commands(self) -> list[SlashCommandDef]:
        return list(self._commands.values())

    def _register_builtins(self) -> None:
        # /help
        async def _help_handler(*args) -> dict[str, Any]:
            return {
                "available_commands": [
                    {"command": f"/{c.name}", "description": c.description, "usage": c.usage}
                    for c in self.list_commands()
                ]
            }

        self.register(
            SlashCommandDef(
                name="help",
                description="List all available slash commands and usage syntax.",
                usage="/help",
                handler=_help_handler,
            )
        )

        # /audit [dir]
        async def _audit_handler(*args) -> dict[str, Any]:
            from synapse.security.audit_scanner import get_security_auditor
            target_dir = args[0] if args else "."
            auditor = get_security_auditor()
            report = auditor.run_audit(target_dir)
            return report.to_dict()

        self.register(
            SlashCommandDef(
                name="audit",
                description="Run security audit scanner for exposed secrets and dangerous APIs.",
                usage="/audit [directory]",
                handler=_audit_handler,
                category="security",
            )
        )

        # /memory [list | search <q> | add <title> <content>]
        async def _memory_handler(*args) -> dict[str, Any]:
            from synapse.memory.vault import get_memory_vault, MemoryType
            vault = get_memory_vault()
            if not args or args[0] == "list":
                entries = vault.list_entries()
                return {"entries": [e.to_dict() for e in entries]}
            elif args[0] == "search":
                q = " ".join(args[1:]) if len(args) > 1 else ""
                results = vault.search(q)
                return {"results": [e.to_dict() for e in results]}
            elif args[0] == "add" and len(args) >= 3:
                title = args[1]
                content = " ".join(args[2:])
                entry = vault.create_entry(title=title, content=content, memory_type=MemoryType.PROJECT)
                return {"created": entry.to_dict()}
            else:
                return {"error": "Invalid memory command. Usage: /memory [list | search <query> | add <title> <content>]"}

        self.register(
            SlashCommandDef(
                name="memory",
                description="Inspect or query agent persistent long-term memory vault.",
                usage="/memory [list | search <query> | add <title> <content>]",
                handler=_memory_handler,
                category="memory",
            )
        )

        # /bench [suite]
        async def _bench_handler(*args) -> dict[str, Any]:
            from synapse.harnesses.hallmark import get_hallmark_harness
            harness = get_hallmark_harness()
            suite_id = args[0] if args else "core_eval_v1"
            report = await harness.run_benchmark(suite_id=suite_id)
            return report.to_dict()

        self.register(
            SlashCommandDef(
                name="bench",
                description="Run Hallmark evaluation benchmark harness and compile scorecard.",
                usage="/bench [suite_id]",
                handler=_bench_handler,
                category="evaluation",
            )
        )

        # /model <task>
        async def _model_handler(*args) -> dict[str, Any]:
            from synapse.llm.omnirouter import get_omnirouter
            task_desc = " ".join(args) if args else "General reasoning and assistance"
            router = get_omnirouter()
            decision = router.route(task_desc)
            return decision.to_dict()

        self.register(
            SlashCommandDef(
                name="model",
                description="Query OmniRouter for optimal provider and model selection.",
                usage="/model <task description>",
                handler=_model_handler,
                category="llm",
            )
        )

        # /route <task> (OmniRouter decision & fallback chain)
        self.register(
            SlashCommandDef(
                name="route",
                description="Test OmniRouter dynamic routing, domain classification, and fallback chain.",
                usage="/route <task description>",
                handler=_model_handler,
                category="llm",
            )
        )

        # /goal <goal text> — run the full cognitive cycle on a high-level goal.
        async def _goal_handler(*args) -> dict[str, Any]:
            if not args:
                return {"error": "Usage: /goal <goal description>"}
            goal_text = " ".join(args)
            from synapse.core.orchestrator import build_orchestrator

            orchestrator = build_orchestrator()
            result = await orchestrator.handle({"task": goal_text})
            return {
                "goal": goal_text,
                "status": result.get("status"),
                "success": result.get("success"),
                "task_id": result.get("task_id"),
                "summary": (result.get("result") or {}).get("action_result", {}),
                "error": result.get("error"),
            }

        self.register(
            SlashCommandDef(
                name="goal",
                description="Run a high-level goal through the full 8-step cognitive cycle.",
                usage="/goal <goal description>",
                handler=_goal_handler,
                category="orchestration",
            )
        )

        # /agents — inventory of external coding-agent CLIs and their status.
        async def _agents_handler(*args) -> dict[str, Any]:
            from synapse.integrations.velly_bridge import detect_agents, velly_status

            status = velly_status()
            return {
                "agents": status["agents"],
                "workspaces": status["workspaces"],
                "chat_config": status["chat_config"],
                "note": "enable via /agent <id> enable, or the integrations page",
            }

        self.register(
            SlashCommandDef(
                name="agents",
                description="List installed external agents (Claude Code, Codex) and Velly app status.",
                usage="/agents",
                handler=_agents_handler,
                category="integrations",
            )
        )

        # /agent <id> [enable | disable | test <prompt>]
        async def _agent_handler(*args) -> dict[str, Any]:
            from synapse.integrations.control_plane import get_control_plane
            from synapse.harnesses import ClaudeCodeHarness, CodexHarness, HarnessRequest

            if not args:
                return {"error": "Usage: /agent <codex|claude_code> [enable | disable | test <prompt>]"}
            agent_id = args[0].lower().replace("-", "_")
            if agent_id not in {"codex", "claude_code"}:
                return {"error": f"Unknown agent '{args[0]}'. Available: codex, claude_code"}
            control_plane = get_control_plane()
            action = args[1].lower() if len(args) > 1 else "status"
            if action == "enable":
                from synapse.integrations.velly_bridge import sync_agents_to_control_plane

                sync_agents_to_control_plane()
                config = control_plane.update_executor(agent_id, enabled=True)
                return {"agent": agent_id, "action": "enable", "config": config}
            if action == "disable":
                config = control_plane.update_executor(agent_id, enabled=False)
                return {"agent": agent_id, "action": "disable", "config": config}
            if action == "test":
                prompt = " ".join(args[2:]) or "List the files in the current directory and summarize the project in one sentence."
                harness = CodexHarness() if agent_id == "codex" else ClaudeCodeHarness()
                if not harness.enabled:
                    return {"agent": agent_id, "error": "agent is disabled; run /agent " + agent_id + " enable first"}
                import os as _os
                from pathlib import Path as _Path

                workspace = _Path(_os.getenv("SYNAPSE_WORKSPACE_ROOT", _os.getcwd())).expanduser().resolve()
                result = await harness.execute(HarnessRequest(
                    task_id="slash_agent_test", run_id="slash_agent_test", prompt=prompt,
                    workspace_id=str(workspace),
                    metadata={"workspace_root": str(workspace)},
                ))
                return {
                    "agent": agent_id, "success": result.success,
                    "output": result.output, "error": result.error,
                    "receipt": result.receipt,
                }
            config = control_plane.executor_config().get(agent_id, {})
            return {"agent": agent_id, "action": "status", "config": config}

        self.register(
            SlashCommandDef(
                name="agent",
                description="Enable, disable, status or test-run an external agent CLI.",
                usage="/agent <codex|claude_code> [enable | disable | test <prompt>]",
                handler=_agent_handler,
                category="integrations",
            )
        )

        # /train <topic> — chat-driven learning loop over the local model.
        async def _train_handler(*args) -> dict[str, Any]:
            if not args:
                return {"error": "Usage: /train <topic> [cycles=N] [pairs=N]"}
            topic_parts = []
            cycles = 3
            pairs = 8
            for arg in args:
                if arg.lower().startswith("cycles="):
                    try:
                        cycles = max(1, min(int(arg.split("=", 1)[1]), 10))
                    except ValueError:
                        return {"error": "cycles must be an integer"}
                elif arg.lower().startswith("pairs="):
                    try:
                        pairs = max(2, min(int(arg.split("=", 1)[1]), 64))
                    except ValueError:
                        return {"error": "pairs must be an integer"}
                else:
                    topic_parts.append(arg)
            topic = " ".join(topic_parts).strip()
            if not topic:
                return {"error": "Usage: /train <topic> [cycles=N] [pairs=N]"}
            from synapse.core.models import ExecutionContext
            from synapse.skills.builtins.learning_loop import execute_learning_loop

            context = ExecutionContext(
                session_id="slash_train",
                agent_id="slash_engine",
                trace_id="slash_train",
                capabilities=["memory:read", "fs:read", "fs:write"],
            )
            return await execute_learning_loop(
                context, topic=topic, max_cycles=cycles, pairs_per_cycle=pairs,
            )

        self.register(
            SlashCommandDef(
                name="train",
                description="Run the chat-driven LoRA learning loop on a topic while holdout loss improves.",
                usage="/train <topic> [cycles=N] [pairs=N]",
                handler=_train_handler,
                category="training",
            )
        )

        # /skills [list | run <id> [params_json]]
        async def _skills_handler(*args) -> dict[str, Any]:
            from synapse.skills.library import get_skill_library
            lib = get_skill_library()
            if not args or args[0] == "list":
                return {"skills": [s.to_dict() for s in lib.list_skills()]}
            elif args[0] == "run" and len(args) > 1:
                skill_id = args[1]
                skill = lib.get(skill_id)
                if not skill:
                    return {"error": f"Skill '{skill_id}' not found."}
                try:
                    raw_params = " ".join(args[2:]).strip() if len(args) > 2 else ""
                    if (raw_params.startswith("'") and raw_params.endswith("'")) or (
                        raw_params.startswith('"') and raw_params.endswith('"')
                    ):
                        inner = raw_params[1:-1].strip()
                        if (inner.startswith("{") and inner.endswith("}")) or (
                            inner.startswith("[") and inner.endswith("]")
                        ):
                            raw_params = inner
                    params = json.loads(raw_params) if raw_params else {}
                except json.JSONDecodeError as exc:
                    return {"error": f"Invalid skill parameters JSON: {exc.msg} at column {exc.colno}."}
                if not isinstance(params, dict):
                    return {"error": "Skill parameters must be a JSON object."}
                return await skill.execute(params)
            return {"error": "Usage: /skills [list | run <skill_id> [params_json]]"}

        self.register(
            SlashCommandDef(
                name="skills",
                description="Explore composable skills catalog or invoke a skill.",
                usage="/skills [list | run <skill_id> [params_json]]",
                handler=_skills_handler,
                category="skills",
            )
        )

        # /patch [file]
        async def _patch_handler(*args) -> dict[str, Any]:
            from synapse.integrations.codex_engine import get_codex_engine
            engine = get_codex_engine()
            if not args:
                return {"status": "ready", "workspace_root": str(engine.workspace_root)}
            target = (engine.workspace_root / args[0]).resolve()
            if not target.is_relative_to(engine.workspace_root):
                return {"error": "File path escapes workspace root."}
            return {"file": args[0], "exists": target.exists(), "size_bytes": target.stat().st_size if target.exists() else 0}

        self.register(
            SlashCommandDef(
                name="patch",
                description="Transactional Codex multi-file patch engine inspection.",
                usage="/patch [file_path]",
                handler=_patch_handler,
                category="coding",
            )
        )

        # /ast <file>
        async def _ast_handler(*args) -> dict[str, Any]:
            from synapse.integrations.codex_engine import get_codex_engine
            if not args:
                return {"error": "Usage: /ast <python_file_path>"}
            engine = get_codex_engine()
            target = (engine.workspace_root / args[0]).resolve()
            if not target.is_relative_to(engine.workspace_root):
                return {"error": "File path escapes workspace root."}
            if not target.exists():
                return {"error": f"File {args[0]} not found."}
            code = target.read_text(encoding="utf-8")
            symbols = engine.analyze_python_ast(code)
            return {"file": args[0], "symbols": [s.to_dict() for s in symbols], "count": len(symbols)}

        self.register(
            SlashCommandDef(
                name="ast",
                description="Analyze Python AST symbols (classes, functions, async methods).",
                usage="/ast <python_file_path>",
                handler=_ast_handler,
                category="coding",
            )
        )

        # /browser <url>
        async def _browser_handler(*args) -> dict[str, Any]:
            from synapse.integrations.browser_controller import get_browser_controller
            ctrl = get_browser_controller()
            if not args:
                return {"status": "ready", "allowed_domains": list(ctrl.config.allowed_domains)}
            res = await ctrl.execute("navigate", {"url": args[0]})
            return res.to_dict()

        self.register(
            SlashCommandDef(
                name="browser",
                description="Computer Use: navigate to approved web domain and verify page status.",
                usage="/browser <url>",
                handler=_browser_handler,
                category="browser",
            )
        )

        # /sft [format]
        async def _sft_handler(*args) -> dict[str, Any]:
            from synapse.harnesses.trajectory import get_trajectory_harness
            fmt = args[0] if args else "chatml"
            samples = get_trajectory_harness().export_sft_dataset(format=fmt)
            return {"count": len(samples), "format": fmt, "samples": samples[:5]}

        self.register(
            SlashCommandDef(
                name="sft",
                description="Export SFT fine-tuning dataset (ChatML or Alpaca) from reasoning traces.",
                usage="/sft [chatml | alpaca]",
                handler=_sft_handler,
                category="learning",
            )
        )

        # /dpo
        async def _dpo_handler(*args) -> dict[str, Any]:
            from synapse.harnesses.trajectory import get_trajectory_harness
            pairs = get_trajectory_harness().export_dpo_dataset()
            return {"count": len(pairs), "pairs": pairs[:5]}

        self.register(
            SlashCommandDef(
                name="dpo",
                description="Export DPO preference pairs (chosen vs rejected) for frontier alignment.",
                usage="/dpo",
                handler=_dpo_handler,
                category="learning",
            )
        )

        # /optimize [agent]
        async def _optimize_handler(*args) -> dict[str, Any]:
            from synapse.learning.engine import get_learning_engine
            agent_role = args[0] if args else "developer"
            return get_learning_engine().optimize_agent_system_prompts(agent_role=agent_role)

        self.register(
            SlashCommandDef(
                name="optimize",
                description="Metacognition: optimize agent system prompt based on performance traces.",
                usage="/optimize [developer | critic | planner | hermes]",
                handler=_optimize_handler,
                category="learning",
            )
        )

        # /patterns
        async def _patterns_handler(*args) -> dict[str, Any]:
            from synapse.learning.engine import get_learning_engine
            return get_learning_engine().detect_skill_degradation_patterns()

        self.register(
            SlashCommandDef(
                name="patterns",
                description="Analyze skill degradation, failure clusters, and capability bottlenecks.",
                usage="/patterns",
                handler=_patterns_handler,
                category="learning",
            )
        )

    def is_slash_command(self, text: str) -> bool:
        """Check if user input text starts with a slash command."""
        clean = text.strip()
        return clean.startswith("/") and len(clean) > 1

    async def execute(self, text: str) -> SlashCommandResult:
        """Parse and execute a slash command string."""
        clean = text.strip()
        if not clean.startswith("/"):
            raise ValueError(f"Not a valid slash command: {text}")

        try:
            # Keep JSON string quoting intact for /skills run. Other commands
            # retain the familiar shell-style parsing of quoted arguments.
            if clean.lower().startswith("/skills "):
                parts = shlex.split(clean, posix=False)
                if len(parts) > 3:
                    parts[3:] = [clean.split(None, 3)[3]]
            else:
                parts = shlex.split(clean)
        except ValueError as exc:
            return SlashCommandResult(command="", args=[], success=False,
                                      output=f"Invalid command syntax: {exc}")
        if not parts or not parts[0][1:]:
            return SlashCommandResult(command="", args=[], success=False,
                                      output="Command name is required. Type /help for available commands.")
        cmd_name = parts[0][1:].lower()
        args = parts[1:]

        cmd_def = self.get(cmd_name)
        if not cmd_def:
            return SlashCommandResult(
                command=cmd_name,
                args=args,
                success=False,
                output=f"Unknown command: /{cmd_name}. Type /help for available commands.",
            )

        try:
            import inspect
            if inspect.iscoroutinefunction(cmd_def.handler):
                res = await cmd_def.handler(*args)
            else:
                res = cmd_def.handler(*args)
            success = True
            if isinstance(res, dict):
                success = res.get("success") is not False and res.get("status") not in {"failed", "blocked", "timeout"}
            return SlashCommandResult(
                command=cmd_name,
                args=args,
                success=success,
                output=res,
            )
        except Exception as e:
            logger.error("Slash command /%s failed: %s", cmd_name, e)
            return SlashCommandResult(
                command=cmd_name,
                args=args,
                success=False,
                output=str(e),
            )


_default_slash_engine: Optional[SlashCommandEngine] = None


def get_slash_engine() -> SlashCommandEngine:
    global _default_slash_engine
    if _default_slash_engine is None:
        _default_slash_engine = SlashCommandEngine()
    return _default_slash_engine
