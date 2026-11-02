"""
Interactive Slash Command Engine for Synapse v3.4.1.

Adapted from anthropics/claude-code patterns.
Provides command routing, argument parsing, autocompletion metadata,
and unified invocation for /audit, /review, /memory, /bench, /model, and /diff.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

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

    def is_slash_command(self, text: str) -> bool:
        """Check if user input text starts with a slash command."""
        clean = text.strip()
        return clean.startswith("/") and len(clean) > 1

    async def execute(self, text: str) -> SlashCommandResult:
        """Parse and execute a slash command string."""
        clean = text.strip()
        if not clean.startswith("/"):
            raise ValueError(f"Not a valid slash command: {text}")

        parts = shlex.split(clean)
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
            return SlashCommandResult(
                command=cmd_name,
                args=args,
                success=True,
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
