"""Distributed Tracing Client.

Protocol Version: 1.0
Specification: 3.1

Adapted from LangSmith SDK tracing patterns (LANGSMITH_SDK_INTEGRATION.md §1).
Synapse additions: security context, capability metadata, audit integration,
protocol versioning, sensitive data filtering.
"""
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


class SpanType(str, Enum):
    LLM = "llm"
    CHAIN = "chain"
    TOOL = "tool"
    RETRIEVER = "retriever"
    EMBEDDING = "embedding"
    AGENT = "agent"
    SKILL = "skill"
    GRAPH_NODE = "graph_node"
    COGNITIVE_STEP = "cognitive_step"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class TraceSpan:
    """A single span in a distributed trace.

    Adapted from LangSmith TraceSpan (LANGSMITH_SDK_INTEGRATION.md §1.2).
    Adds: protocol_version, security_context, capability_checks, resource_usage.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    name: str = ""
    span_type: SpanType = SpanType.AGENT
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    status: SpanStatus = SpanStatus.UNSET
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Synapse-specific
    protocol_version: str = PROTOCOL_VERSION
    session_id: str = ""
    agent_id: str = ""
    security_context: Dict[str, Any] = field(default_factory=dict)
    capability_checks: List[Dict[str, Any]] = field(default_factory=list)
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    is_sensitive: bool = False

    def finish(self, status: SpanStatus = SpanStatus.OK, outputs: Any = None, error: str = None) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.status = status
        if outputs is not None:
            self.outputs = outputs if isinstance(outputs, dict) else {"result": outputs}
        if error:
            self.error = error

    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            try:
                s = datetime.fromisoformat(self.start_time)
                e = datetime.fromisoformat(self.end_time)
                return (e - s).total_seconds() * 1000
            except Exception as _exc:  # noqa
                pass  # noqa: silenced - _exc
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "span_type": self.span_type.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status.value,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "error": self.error,
            "metadata": self.metadata,
            "protocol_version": self.protocol_version,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "duration_ms": self.duration_ms(),
            "is_sensitive": self.is_sensitive,
        }


class SecureTraceClient:
    """Distributed tracing with security filtering.

    Adapted from LangSmith SDK (LANGSMITH_SDK_INTEGRATION.md §1.2).
    Adds: security filtering, capability metadata, protocol versioning,
    sensitive data masking, audit trail.
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    def __init__(
        self,
        project_name: str = "synapse",
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        sampling_rate: float = 1.0,
        filter_sensitive: bool = True,
    ):
        self.project_name = project_name
        self.api_key = api_key
        self.endpoint = endpoint or "http://localhost:1984"
        self.sampling_rate = sampling_rate
        self.filter_sensitive = filter_sensitive
        # In-memory store (production would export to LangSmith/OTLP/etc.)
        self._traces: Dict[str, List[TraceSpan]] = {}
        self._active: Dict[str, TraceSpan] = {}  # span_id → span

        audit(event="trace_client_initialized", project=project_name, protocol_version=PROTOCOL_VERSION)

    # ------------------------------------------------------------------
    # Trace management
    # ------------------------------------------------------------------

    def start_trace(
        self,
        name: str,
        session_id: str = "",
        agent_id: str = "",
        span_type: SpanType = SpanType.AGENT,
        metadata: Optional[Dict] = None,
        inputs: Optional[Dict] = None,
        is_sensitive: bool = False,
    ) -> TraceSpan:
        """Start a new root trace span."""
        trace_id = str(uuid.uuid4())
        span = TraceSpan(
            trace_id=trace_id,
            name=name,
            span_type=span_type,
            session_id=session_id,
            agent_id=agent_id,
            metadata=metadata or {},
            inputs=self._filter(inputs) if is_sensitive else inputs,
            is_sensitive=is_sensitive,
        )
        self._traces[trace_id] = [span]
        self._active[span.id] = span
        audit(event="trace_started", trace_id=trace_id, name=name, agent_id=agent_id, protocol_version=PROTOCOL_VERSION)
        return span

    def start_span(
        self,
        name: str,
        parent_span: TraceSpan,
        span_type: SpanType = SpanType.SKILL,
        inputs: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> TraceSpan:
        """Start a child span within an existing trace."""
        span = TraceSpan(
            trace_id=parent_span.trace_id,
            parent_span_id=parent_span.id,
            name=name,
            span_type=span_type,
            session_id=parent_span.session_id,
            agent_id=parent_span.agent_id,
            inputs=inputs,
            metadata=metadata or {},
        )
        self._traces.setdefault(parent_span.trace_id, []).append(span)
        self._active[span.id] = span
        return span

    def finish_span(
        self,
        span: TraceSpan,
        outputs: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """Finish a span and record it."""
        status = SpanStatus.ERROR if error else SpanStatus.OK
        out = self._filter(outputs) if span.is_sensitive and isinstance(outputs, dict) else outputs
        span.finish(status=status, outputs=out, error=error)
        self._active.pop(span.id, None)

    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """Return all spans for a trace."""
        return self._traces.get(trace_id, [])

    def get_all_traces(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return all traces as serializable dicts."""
        return {
            tid: [s.to_dict() for s in spans]
            for tid, spans in self._traces.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return tracing statistics."""
        total_spans = sum(len(v) for v in self._traces.values())
        return {
            "project": self.project_name,
            "total_traces": len(self._traces),
            "total_spans": total_spans,
            "active_spans": len(self._active),
            "protocol_version": PROTOCOL_VERSION,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter(self, data: Optional[Dict]) -> Optional[Dict]:
        """Mask sensitive fields from trace data."""
        if not data or not self.filter_sensitive:
            return data
        SENSITIVE = {"api_key", "password", "token", "secret", "credential"}
        return {
            k: ("***" if any(s in k.lower() for s in SENSITIVE) else v)
            for k, v in data.items()
        }
