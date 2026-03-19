"""Composable Chain/Workflow System.

Protocol Version: 1.0
Specification: 3.1

Adapted from LangChain chain patterns (LANGCHAIN_INTEGRATION.md §2).
Synapse additions: checkpoint integration, capability checks,
audit logging, protocol versioning, rollback support.
"""
import asyncio
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


@dataclass
class ChainInput:
    """Input to a chain step."""
    data: Dict[str, Any]
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    protocol_version: str = PROTOCOL_VERSION


@dataclass
class ChainOutput:
    """Output from a chain step."""
    result: Any
    intermediate_steps: List[Dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""
    session_id: str = ""
    success: bool = True
    error: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result,
            "intermediate_steps": self.intermediate_steps,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "success": self.success,
            "error": self.error,
            "protocol_version": self.protocol_version,
        }


class BaseChain(ABC):
    """Abstract base chain.

    Adapted from LangChain BaseChain (LANGCHAIN_INTEGRATION.md §2.1).
    Adds: checkpoint support, audit logging, protocol versioning.
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    def __init__(
        self,
        name: str,
        checkpoint_manager: Any = None,
        audit_logger: Any = None,
    ):
        self.name = name
        self.checkpoint = checkpoint_manager
        self.audit = audit_logger

    @abstractmethod
    async def execute(self, input: ChainInput) -> ChainOutput:
        """Execute the chain."""

    async def _create_checkpoint(self, input: ChainInput, state: Dict) -> Optional[str]:
        if self.checkpoint:
            try:
                cp = self.checkpoint.create_checkpoint(
                    state={**state, "chain": self.name},
                    agent_id=f"chain:{self.name}",
                    session_id=input.session_id,
                )
                return cp.checkpoint_id
            except Exception as e:
                logger.warning("Checkpoint creation failed: %s", e)
        return None

    async def _audit_step(self, step: str, inp: Any, out: Any) -> None:
        audit(
            event="chain_step",
            chain=self.name,
            step=step,
            input_preview=str(inp)[:100],
            output_preview=str(out)[:100],
            protocol_version=PROTOCOL_VERSION,
        )


class LLMChain(BaseChain):
    """Single LLM call chain.

    Adapted from LangChain LLMChain (LANGCHAIN_INTEGRATION.md §2.1).
    """

    def __init__(
        self,
        name: str,
        llm_provider: Any,
        prompt_template: str = "{input}",
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        self.llm = llm_provider
        self.prompt_template = prompt_template

    async def execute(self, input: ChainInput) -> ChainOutput:
        audit(event="llm_chain_start", chain=self.name, trace_id=input.trace_id, protocol_version=PROTOCOL_VERSION)
        try:
            prompt = self.prompt_template.format(**input.data) if "{" in self.prompt_template else self.prompt_template
            response = await self.llm.generate(prompt)
            content = response.get("content", "") if isinstance(response, dict) else str(response)
            await self._audit_step("llm_call", prompt[:80], content[:80])
            return ChainOutput(
                result=content,
                trace_id=input.trace_id,
                session_id=input.session_id,
                success=True,
            )
        except Exception as e:
            audit(event="llm_chain_error", chain=self.name, error=str(e), protocol_version=PROTOCOL_VERSION)
            return ChainOutput(result=None, trace_id=input.trace_id, session_id=input.session_id, success=False, error=str(e))


class SequentialChain(BaseChain):
    """Runs chains in sequence, passing output as next input.

    Adapted from LangChain SequentialChain (LANGCHAIN_INTEGRATION.md §2.1).
    """

    def __init__(self, chains: List[BaseChain], **kwargs):
        super().__init__(name="sequential_chain", **kwargs)
        self.chains = chains

    async def execute(self, input: ChainInput) -> ChainOutput:
        audit(event="sequential_chain_start", steps=len(self.chains), trace_id=input.trace_id, protocol_version=PROTOCOL_VERSION)
        await self._create_checkpoint(input, {"step": 0, "total": len(self.chains)})

        current = input
        steps: List[Dict[str, Any]] = []
        for i, chain in enumerate(self.chains):
            try:
                out = await chain.execute(current)
                steps.append({"chain": chain.name, "step": i, "success": out.success, "error": out.error})
                await self._audit_step(chain.name, current.data, out.result)
                if not out.success:
                    return ChainOutput(result=out.result, intermediate_steps=steps, trace_id=input.trace_id,
                                       session_id=input.session_id, success=False, error=out.error)
                current = ChainInput(data={"input": out.result, "previous": out.result},
                                     trace_id=input.trace_id, session_id=input.session_id)
            except Exception as e:
                steps.append({"chain": chain.name, "step": i, "error": str(e)})
                return ChainOutput(result=None, intermediate_steps=steps, trace_id=input.trace_id,
                                   session_id=input.session_id, success=False, error=str(e))

        audit(event="sequential_chain_complete", steps=len(steps), trace_id=input.trace_id, protocol_version=PROTOCOL_VERSION)
        return ChainOutput(result=current.data.get("input"), intermediate_steps=steps,
                           trace_id=input.trace_id, session_id=input.session_id, success=True)


class ParallelChain(BaseChain):
    """Runs chains concurrently and merges results.

    Adapted from LangChain parallel patterns (LANGCHAIN_INTEGRATION.md §2.1).
    """

    def __init__(self, chains: List[BaseChain], merge_key: str = "results", **kwargs):
        super().__init__(name="parallel_chain", **kwargs)
        self.chains = chains
        self.merge_key = merge_key

    async def execute(self, input: ChainInput) -> ChainOutput:
        audit(event="parallel_chain_start", parallel_count=len(self.chains), trace_id=input.trace_id, protocol_version=PROTOCOL_VERSION)
        tasks = [chain.execute(input) for chain in self.chains]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        outputs: List[Any] = []
        steps: List[Dict[str, Any]] = []
        all_success = True
        for chain, res in zip(self.chains, results):
            if isinstance(res, Exception):
                steps.append({"chain": chain.name, "error": str(res)})
                all_success = False
            else:
                steps.append({"chain": chain.name, "success": res.success})
                outputs.append(res.result)
                if not res.success:
                    all_success = False
        return ChainOutput(result={self.merge_key: outputs}, intermediate_steps=steps,
                           trace_id=input.trace_id, session_id=input.session_id, success=all_success)


class RouterChain(BaseChain):
    """Routes to different chains based on input conditions.

    Adapted from LangChain RouterChain (LANGCHAIN_INTEGRATION.md §2.1).
    """

    def __init__(self, routes: Dict[str, BaseChain], default_chain: Optional[BaseChain] = None, **kwargs):
        super().__init__(name="router_chain", **kwargs)
        self.routes = routes
        self.default = default_chain

    async def execute(self, input: ChainInput) -> ChainOutput:
        route_key = input.data.get("route", "")
        chain = self.routes.get(route_key, self.default)
        if chain is None:
            return ChainOutput(result=None, trace_id=input.trace_id, session_id=input.session_id,
                               success=False, error=f"No route for key: {route_key!r}")
        audit(event="router_chain_route", route=route_key, chain=chain.name, protocol_version=PROTOCOL_VERSION)
        return await chain.execute(input)
