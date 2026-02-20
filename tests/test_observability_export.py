"""Tests for Observability Export."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_metrics_collector():
    """Mock metrics collector."""
    collector = MagicMock()
    collector.collect = MagicMock(return_value={
        "synapse_tasks_total": 100,
        "synapse_tasks_success": 95,
        "synapse_llm_calls_total": 500,
        "synapse_cluster_nodes": 3
    })
    return collector


@pytest.mark.unit
def test_metrics_endpoint_available(mock_metrics_collector):
    """Test /metrics endpoint is available."""
    from synapse.observability.exporter import MetricsExporter
    
    exporter = MetricsExporter(collector=mock_metrics_collector)
    metrics = exporter.export_prometheus()
    
    assert "synapse_" in metrics
    assert "protocol_version" in metrics


@pytest.mark.unit
def test_metrics_contain_protocol_version(mock_metrics_collector):
    """Test metrics contain protocol_version."""
    from synapse.observability.exporter import MetricsExporter
    
    exporter = MetricsExporter(collector=mock_metrics_collector)
    metrics = exporter.export_prometheus()
    
    assert 'protocol_version="1.0"' in metrics or 'protocol_version{version="1.0"}' in metrics


@pytest.mark.unit
def test_cluster_metrics_aggregation():
    """Test cluster metrics aggregation."""
    from synapse.observability.exporter import ClusterMetricsAggregator
    
    aggregator = ClusterMetricsAggregator()
    
    # Add node metrics
    aggregator.add_node_metrics("node1", {"tasks": 10, "cpu": 50})
    aggregator.add_node_metrics("node2", {"tasks": 20, "cpu": 30})
    aggregator.add_node_metrics("node3", {"tasks": 15, "cpu": 40})
    
    aggregated = aggregator.get_aggregated()
    assert aggregated["tasks"] == 45
    assert aggregated["nodes"] == 3


@pytest.mark.unit
def test_structured_logs_export():
    """Test structured logs export."""
    from synapse.observability.exporter import LogExporter
    
    exporter = LogExporter()
    exporter.add_log({"level": "INFO", "message": "test", "timestamp": "2024-01-01T00:00:00Z"})
    exporter.add_log({"level": "ERROR", "message": "error", "timestamp": "2024-01-01T00:01:00Z"})
    
    logs = exporter.export_json()
    assert len(logs) == 2
    assert logs[0]["level"] == "INFO"
    assert logs[1]["level"] == "ERROR"


@pytest.mark.unit
def test_trace_export_interface():
    """Test trace export interface."""
    from synapse.observability.exporter import TraceExporter
    
    exporter = TraceExporter()
    exporter.add_span({
        "trace_id": "test-trace",
        "span_id": "span-1",
        "operation": "task_execution",
        "duration_ms": 100
    })
    
    traces = exporter.export()
    assert len(traces) == 1
    assert traces[0]["trace_id"] == "test-trace"
