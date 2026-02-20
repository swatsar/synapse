"""Comprehensive tests for observability exporter."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestMetricsExporter:
    """Test metrics exporter comprehensively."""
    
    @pytest.fixture
    def exporter(self):
        """Create a metrics exporter for testing."""
        from synapse.observability.exporter import MetricsExporter
        
        return MetricsExporter()
    
    def test_exporter_creation(self, exporter):
        """Test exporter creation."""
        assert exporter is not None
    
    def test_protocol_version(self, exporter):
        """Test protocol version."""
        assert exporter.protocol_version == "1.0"
    
    def test_add_metric(self, exporter):
        """Test adding a metric."""
        exporter.add_metric("test_metric", 1.0, {"label": "value"})
        
        # MetricsExporter adds synapse_ prefix
        assert "synapse_test_metric" in exporter._metrics
    
    def test_export_prometheus(self, exporter):
        """Test exporting metrics in Prometheus format."""
        exporter.add_metric("test_metric", 1.0)
        
        result = exporter.export_prometheus()
        
        assert "test_metric" in result
        assert "synapse_protocol_version" in result


class TestClusterMetricsAggregator:
    """Test cluster metrics aggregator."""
    
    @pytest.fixture
    def aggregator(self):
        """Create a cluster metrics aggregator for testing."""
        from synapse.observability.exporter import ClusterMetricsAggregator
        
        return ClusterMetricsAggregator()
    
    def test_aggregator_creation(self, aggregator):
        """Test aggregator creation."""
        assert aggregator is not None
    
    def test_protocol_version(self, aggregator):
        """Test protocol version."""
        assert aggregator.protocol_version == "1.0"
    
    def test_add_node_metrics(self, aggregator):
        """Test adding node metrics."""
        aggregator.add_node_metrics("node1", {"cpu": 50, "memory": 100})
        
        assert "node1" in aggregator._node_metrics
    
    def test_get_aggregated(self, aggregator):
        """Test getting aggregated metrics."""
        aggregator.add_node_metrics("node1", {"cpu": 50, "memory": 100})
        aggregator.add_node_metrics("node2", {"cpu": 30, "memory": 200})
        
        result = aggregator.get_aggregated()
        
        assert result["nodes"] == 2
        assert result["cpu"] == 80
        assert result["memory"] == 300


class TestLogExporter:
    """Test log exporter."""
    
    @pytest.fixture
    def exporter(self):
        """Create a log exporter for testing."""
        from synapse.observability.exporter import LogExporter
        
        return LogExporter()
    
    def test_exporter_creation(self, exporter):
        """Test exporter creation."""
        assert exporter is not None
    
    def test_protocol_version(self, exporter):
        """Test protocol version."""
        assert exporter.protocol_version == "1.0"
    
    def test_add_log(self, exporter):
        """Test adding a log entry."""
        exporter.add_log({"level": "INFO", "message": "test log"})
        
        assert len(exporter._logs) == 1
    
    def test_export_json(self, exporter):
        """Test exporting logs as JSON."""
        exporter.add_log({"level": "INFO", "message": "test log"})
        
        result = exporter.export_json()
        
        assert len(result) == 1
        assert result[0]["level"] == "INFO"
    
    def test_export_text(self, exporter):
        """Test exporting logs as text."""
        exporter.add_log({"level": "INFO", "message": "test log", "timestamp": "2024-01-01"})
        
        result = exporter.export_text()
        
        assert "INFO" in result
        assert "test log" in result


class TestTraceExporter:
    """Test trace exporter."""
    
    @pytest.fixture
    def exporter(self):
        """Create a trace exporter for testing."""
        from synapse.observability.exporter import TraceExporter
        
        return TraceExporter()
    
    def test_exporter_creation(self, exporter):
        """Test exporter creation."""
        assert exporter is not None
    
    def test_protocol_version(self, exporter):
        """Test protocol version."""
        assert exporter.protocol_version == "1.0"
    
    def test_add_span(self, exporter):
        """Test adding a trace span."""
        exporter.add_span({"trace_id": "test_trace", "duration": 0.5})
        
        assert len(exporter._spans) == 1
    
    def test_export(self, exporter):
        """Test exporting all spans."""
        exporter.add_span({"trace_id": "test_trace", "duration": 0.5})
        
        result = exporter.export()
        
        assert len(result) == 1
    
    def test_export_for_trace(self, exporter):
        """Test exporting spans for a specific trace."""
        exporter.add_span({"trace_id": "trace1", "duration": 0.5})
        exporter.add_span({"trace_id": "trace2", "duration": 0.3})
        
        result = exporter.export_for_trace("trace1")
        
        # export_for_trace returns dict with trace_id, spans, protocol_version
        assert "spans" in result
        assert len(result["spans"]) == 1
