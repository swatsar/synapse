"""Unit tests for Distributed Tracing. Phase 5 — Reliability & Observability.

TDD per TDD_INSTRUCTION_v1_2_FINAL.md + LANGSMITH_SDK_INTEGRATION.md §1.
"""
import pytest

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase5
@pytest.mark.unit
class TestTraceSpan:
    def test_span_creation(self):
        from synapse.observability.trace_client import TraceSpan, SpanType
        span = TraceSpan(trace_id="t1", name="test", span_type=SpanType.AGENT,
                        session_id="s1", agent_id="a1")
        assert span.id
        assert span.trace_id == "t1"
        assert span.protocol_version == PROTOCOL_VERSION

    def test_span_finish_ok(self):
        from synapse.observability.trace_client import TraceSpan, SpanStatus, SpanType
        span = TraceSpan(trace_id="t1", name="test", span_type=SpanType.LLM, session_id="s1", agent_id="a1")
        span.finish(status=SpanStatus.OK, outputs={"result": "done"})
        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_span_finish_error(self):
        from synapse.observability.trace_client import TraceSpan, SpanStatus, SpanType
        span = TraceSpan(trace_id="t1", name="test", span_type=SpanType.TOOL, session_id="s1", agent_id="a1")
        span.finish(status=SpanStatus.ERROR, error="failed")
        assert span.status == SpanStatus.ERROR
        assert span.error == "failed"

    def test_span_duration_ms(self):
        from synapse.observability.trace_client import TraceSpan, SpanStatus, SpanType
        import time
        span = TraceSpan(trace_id="t1", name="test", span_type=SpanType.SKILL, session_id="s1", agent_id="a1")
        time.sleep(0.01)
        span.finish(SpanStatus.OK)
        assert span.duration_ms() is not None
        assert span.duration_ms() >= 0

    def test_span_to_dict(self):
        from synapse.observability.trace_client import TraceSpan, SpanType
        span = TraceSpan(trace_id="t1", name="test", span_type=SpanType.CHAIN, session_id="s1", agent_id="a1")
        d = span.to_dict()
        assert d["trace_id"] == "t1"
        assert d["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase5
@pytest.mark.unit
class TestSecureTraceClient:
    @pytest.fixture
    def client(self):
        from synapse.observability.trace_client import SecureTraceClient
        return SecureTraceClient(project_name="test_project")

    def test_start_trace_creates_span(self, client):
        from synapse.observability.trace_client import SpanType
        span = client.start_trace("test_op", session_id="s1", agent_id="a1")
        assert span.trace_id
        assert span.name == "test_op"
        assert span.protocol_version == PROTOCOL_VERSION

    def test_start_child_span(self, client):
        from synapse.observability.trace_client import SpanType
        parent = client.start_trace("parent", session_id="s1", agent_id="a1")
        child = client.start_span("child", parent_span=parent, span_type=SpanType.TOOL)
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.id

    def test_finish_span_removes_from_active(self, client):
        from synapse.observability.trace_client import SpanStatus
        span = client.start_trace("test", session_id="s1", agent_id="a1")
        assert span.id in client._active
        client.finish_span(span, outputs={"result": "ok"})
        assert span.id not in client._active

    def test_get_trace_returns_all_spans(self, client):
        from synapse.observability.trace_client import SpanType, SpanStatus
        root = client.start_trace("root", session_id="s1", agent_id="a1")
        child = client.start_span("child", parent_span=root, span_type=SpanType.LLM)
        client.finish_span(root)
        client.finish_span(child)
        spans = client.get_trace(root.trace_id)
        assert len(spans) == 2

    def test_sensitive_data_filtered(self, client):
        from synapse.observability.trace_client import SpanType, SpanStatus
        span = client.start_trace(
            "sensitive_op",
            session_id="s1",
            agent_id="a1",
            inputs={"api_key": "sk-secret123", "prompt": "hello"},
            is_sensitive=True,
        )
        assert span.inputs["api_key"] == "***"
        assert span.inputs["prompt"] == "hello"

    def test_get_stats(self, client):
        client.start_trace("op1", session_id="s1", agent_id="a1")
        client.start_trace("op2", session_id="s1", agent_id="a1")
        stats = client.get_stats()
        assert stats["total_traces"] == 2
        assert stats["protocol_version"] == PROTOCOL_VERSION
