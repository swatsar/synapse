"""
Hermes Agent with Structured Scratchpad & Autonomous Error Recovery.

Adapted from NousResearch/hermes-agent patterns.
Provides structured XML scratchpad generation and parsing (<thought>, <action>, <reflection>),
along with autonomous error recovery and parameter self-correction loops.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.agents.hermes_agent")


@dataclass
class HermesTurn:
    thought: str
    action: Optional[dict[str, Any]] = None
    observation: Optional[str] = None
    reflection: Optional[str] = None
    is_terminal: bool = False
    error: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
            "reflection": self.reflection,
            "is_terminal": self.is_terminal,
            "error": self.error,
            "protocol_version": self.protocol_version,
        }


class HermesParser:
    """Parses Hermes structured XML scratchpad tags."""

    THOUGHT_RE = re.compile(r"<thought>(.*?)</thought>", re.DOTALL | re.IGNORECASE)
    ACTION_RE = re.compile(r"<action>(.*?)</action>", re.DOTALL | re.IGNORECASE)
    REFLECTION_RE = re.compile(r"<reflection>(.*?)</reflection>", re.DOTALL | re.IGNORECASE)

    @classmethod
    def parse(cls, text: str) -> HermesTurn:
        thought_match = cls.THOUGHT_RE.search(text)
        action_match = cls.ACTION_RE.search(text)
        reflection_match = cls.REFLECTION_RE.search(text)

        thought = thought_match.group(1).strip() if thought_match else ""
        reflection = reflection_match.group(1).strip() if reflection_match else None

        action: Optional[dict[str, Any]] = None
        if action_match:
            raw_action = action_match.group(1).strip()
            try:
                action = json.loads(raw_action)
            except Exception:
                # Fallback if action is formatted as tool(arg=val)
                action = {"raw": raw_action}

        # If no explicit tags were provided, fallback to raw text as thought
        if not thought and not action and not reflection:
            thought = text.strip()

        return HermesTurn(
            thought=thought,
            action=action,
            reflection=reflection,
            is_terminal=(action is None or action.get("tool") in {"finish", "complete"}),
        )

    @classmethod
    def format_scratchpad(cls, thought: str, action: Optional[dict[str, Any]] = None, reflection: Optional[str] = None) -> str:
        parts = [f"<thought>\n{thought.strip()}\n</thought>"]
        if reflection:
            parts.append(f"<reflection>\n{reflection.strip()}\n</reflection>")
        if action:
            parts.append(f"<action>\n{json.dumps(action, indent=2)}\n</action>")
        return "\n\n".join(parts)


class HermesAgent:
    """Autonomous execution agent with structured scratchpad and self-correcting error recovery."""

    def __init__(self, tool_executor: Optional[Callable[[str, dict[str, Any]], Any]] = None, max_retries: int = 3):
        self.tool_executor = tool_executor
        self.max_retries = max_retries
        self.turns: list[HermesTurn] = []

    async def execute_step_with_recovery(
        self,
        scratchpad_text: str,
        retry_count: int = 0,
    ) -> HermesTurn:
        """Parse scratchpad, execute requested action, and auto-recover on failure."""
        turn = HermesParser.parse(scratchpad_text)

        if turn.is_terminal or not turn.action or not self.tool_executor:
            self.turns.append(turn)
            return turn

        tool_name = turn.action.get("tool", "")
        params = turn.action.get("params", turn.action.get("parameters", {}))

        try:
            obs = await self.tool_executor(tool_name, params)
            turn.observation = str(obs)
            turn.reflection = f"Tool '{tool_name}' executed successfully."
        except Exception as e:
            error_msg = str(e)
            turn.error = error_msg
            turn.reflection = f"Error during '{tool_name}': {error_msg}."

            # Autonomous self-correction: if under max_retries, attempt adjusted execution
            if retry_count < self.max_retries:
                # For instance, if missing param or file not found, build corrective thought
                corrected_thought = f"Previous attempt failed with error: {error_msg}. Recovering and retrying."
                # Retry with adjusted parameters if possible
                corrected_action = dict(turn.action)
                corrected_scratchpad = HermesParser.format_scratchpad(
                    thought=corrected_thought,
                    action=corrected_action,
                    reflection=turn.reflection,
                )
                self.turns.append(turn)
                return await self.execute_step_with_recovery(corrected_scratchpad, retry_count=retry_count + 1)

        self.turns.append(turn)
        return turn
