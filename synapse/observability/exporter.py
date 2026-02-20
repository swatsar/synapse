"""Observability Exporters.

Provides exporters for Prometheus and other monitoring systems.
"""
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import json
import time

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


@dataclass
class Metric:
    """Metric data point."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0
    metric_type: str = "gauge"


@dataclass
class Span:
    """Trace span."""
    trace_id: str
    span_id: str
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)


class MetricsExporter:
    """Base metrics exporter."""
    
    protocol_version: str = "1.0"
    
    def __init__(self, prefix: str = "synapse", collector=None, config: Optional[dict] = None):
        self.protocol_version = "1.0"
        self._prefix = prefix
        self._metrics: Dict[str, Metric] = {}
        self.collector = collector
        self.config = config or {}
    
    def add_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        metric_type: str = "gauge"
    ) -> None:
        """Add a metric."""
        metric = Metric(
            name=name,
            value=value,
            labels=labels or {},
            timestamp=time.time(),
            metric_type=metric_type
        )
        self._metrics[f"{self._prefix}_{name}"] = metric
    
    async def export(self, metrics: Optional[Dict[str, Any]] = None) -> bool:
        """Export metrics."""
        if metrics:
            for name, value in metrics.items():
                if isinstance(value, dict):
                    self.add_metric(name, value.get("value", 0), value.get("labels"))
                else:
                    self.add_metric(name, value)
        return True
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # If we have a collector, use its metrics
        if self.collector and hasattr(self.collector, 'collect'):
            collected = self.collector.collect()
            if collected:
                for name, value in collected.items():
                    self.add_metric(name.replace(f"{self._prefix}_", ""), value)
        
        # Add protocol version metric
        lines.append(f"# HELP {self._prefix}_protocol_version Protocol version")
        lines.append(f"# TYPE {self._prefix}_protocol_version gauge")
        lines.append(f'{self._prefix}_protocol_version{{version="1.0"}} 1')
        
        for name, metric in self._metrics.items():
            lines.append(f"# HELP {name} {metric.name}")
            lines.append(f"# TYPE {name} {metric.metric_type}")
            if metric.labels:
                labels_str = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                lines.append(f"{name}{{{labels_str}}} {metric.value}")
            else:
                lines.append(f"{name} {metric.value}")
        return "\n".join(lines)


class ClusterMetricsAggregator:
    """Aggregates metrics from multiple cluster nodes."""
    
    protocol_version: str = "1.0"
    
    def __init__(self):
        self.protocol_version = "1.0"
        self._node_metrics: Dict[str, Any] = {}
    
    def add_node_metrics(self, node_id: str, metrics: Union[List[Metric], Dict[str, Any]]) -> None:
        """Add metrics from a node.
        
        Supports both Metric objects and dict metrics.
        """
        self._node_metrics[node_id] = metrics
    
    def get_aggregated(self) -> Dict[str, Any]:
        """Get aggregated metrics."""
        # Aggregate numeric values from all nodes
        aggregated = {"nodes": len(self._node_metrics), "protocol_version": self.protocol_version}
        
        for node_id, metrics in self._node_metrics.items():
            if isinstance(metrics, dict):
                for key, value in metrics.items():
                    if isinstance(value, (int, float)):
                        if key not in aggregated:
                            aggregated[key] = 0
                        aggregated[key] += value
            elif isinstance(metrics, list):
                for m in metrics:
                    if isinstance(m, Metric):
                        if m.name not in aggregated:
                            aggregated[m.name] = 0
                        aggregated[m.name] += m.value
        
        return aggregated


class LogExporter:
    """Exports logs in various formats."""
    
    protocol_version: str = "1.0"
    
    def __init__(self):
        self.protocol_version = "1.0"
        self._logs: List[Dict[str, Any]] = []
    
    def add_log(
        self,
        entry: Optional[Union[str, Dict[str, Any]]] = None,
        level: str = "INFO",
        message: Optional[str] = None,
        **kwargs
    ) -> str:
        """Add a log entry.
        
        Supports flexible calling:
        - add_log({"level": "INFO", "message": "test"})
        - add_log(level="ERROR", message="error")
        - add_log("test message")
        
        Args:
            entry: Log entry dict or message string (optional)
            level: Log level (default INFO)
            message: Log message (optional)
            **kwargs: Additional fields
            
        Returns:
            Log ID
        """
        log_id = f"log_{len(self._logs)}"
        
        if isinstance(entry, dict):
            # Entry is a dict with log data
            log_entry = {
                "id": log_id,
                "level": entry.get("level", level),
                "message": entry.get("message", ""),
                "timestamp": entry.get("timestamp", time.time()),
                **{k: v for k, v in entry.items() if k not in ["level", "message", "timestamp"]},
                **kwargs
            }
        elif isinstance(entry, str):
            # Entry is a message string
            log_entry = {
                "id": log_id,
                "level": level,
                "message": entry,
                "timestamp": time.time(),
                **kwargs
            }
        else:
            # Use level and message parameters
            log_entry = {
                "id": log_id,
                "level": level,
                "message": message or "",
                "timestamp": time.time(),
                **kwargs
            }
        
        self._logs.append(log_entry)
        return log_id
    
    def export_json(self) -> List[Dict[str, Any]]:
        """Export logs as list of dicts (for test compatibility)."""
        return self._logs
    
    def export_json_string(self) -> str:
        """Export logs as JSON string."""
        return json.dumps(self._logs, indent=2)
    
    def export_text(self) -> str:
        """Export logs as text."""
        lines = []
        for log in self._logs:
            lines.append(f"[{log['level']}] {log['message']}")
        return "\n".join(lines)


class TraceExporter:
    """Exports traces in various formats."""
    
    protocol_version: str = "1.0"
    
    def __init__(self):
        self.protocol_version = "1.0"
        self._spans: List[Dict[str, Any]] = []
        self._spans_by_trace: Dict[str, List[Dict[str, Any]]] = {}
    
    def add_span(
        self,
        span: Optional[Union[Span, Dict[str, Any]]] = None,
        span_data: Optional[Dict] = None,
        **kwargs
    ) -> str:
        """Add a trace span.
        
        Supports flexible calling:
        - add_span({"trace_id": "...", "span_id": "...", ...})
        - add_span(span=Span(...))
        - add_span(trace_id="...", span_id="...", name="...")
        
        Args:
            span: Span object or dict (optional)
            span_data: Span data dict (optional)
            **kwargs: Direct span attributes
            
        Returns:
            Span ID
        """
        if isinstance(span, dict):
            # Span is a dict
            span_dict = span.copy()
            if "span_id" not in span_dict:
                span_dict["span_id"] = f"span_{time.time()}"
        elif isinstance(span, Span):
            # Span is a Span object
            span_dict = {
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "name": span.name,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "attributes": span.attributes
            }
        elif span_data is not None:
            span_dict = span_data.copy()
            if "span_id" not in span_dict:
                span_dict["span_id"] = f"span_{time.time()}"
        else:
            span_dict = kwargs.copy()
            if "span_id" not in span_dict:
                span_dict["span_id"] = f"span_{time.time()}"
        
        self._spans.append(span_dict)
        
        trace_id = span_dict.get("trace_id", "")
        if trace_id:
            if trace_id not in self._spans_by_trace:
                self._spans_by_trace[trace_id] = []
            self._spans_by_trace[trace_id].append(span_dict)
        
        return span_dict.get("span_id", "")
    
    def export(self) -> List[Dict[str, Any]]:
        """Export all traces as list (for test compatibility)."""
        return self._spans
    
    def export_dict(self) -> Dict[str, Any]:
        """Export all traces as dict."""
        return {
            "traces": len(self._spans_by_trace),
            "spans": len(self._spans),
            "protocol_version": self.protocol_version
        }
    
    def export_for_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Export spans for a specific trace."""
        if trace_id not in self._spans_by_trace:
            return None
        return {
            "trace_id": trace_id,
            "spans": self._spans_by_trace[trace_id],
            "protocol_version": self.protocol_version
        }


class PrometheusExporter:
    """Exports metrics in Prometheus format."""
    
    protocol_version: str = "1.0"
    
    def __init__(self, prefix: str = "synapse"):
        self.protocol_version = "1.0"
        self._prefix = prefix
        self._metrics: Dict[str, Metric] = {}
    
    def export(self, metrics: List[Metric]) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        for metric in metrics:
            name = f"{self._prefix}_{metric.name}"
            if name not in self._metrics:
                lines.append(f"# HELP {name} {metric.name}")
                lines.append(f"# TYPE {name} {metric.metric_type}")
                self._metrics[name] = metric
            if metric.labels:
                labels_str = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                lines.append(f"{name}{{{labels_str}}} {metric.value}")
            else:
                lines.append(f"{name} {metric.value}")
        return "\n".join(lines)
    
    def add_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None, metric_type: str = "gauge") -> None:
        metric = Metric(name=name, value=value, labels=labels or {}, metric_type=metric_type)
        self._metrics[f"{self._prefix}_{name}"] = metric
    
    def get_metrics(self) -> List[Metric]:
        return list(self._metrics.values())
    
    def clear(self) -> None:
        self._metrics.clear()


class JSONExporter:
    """Exports metrics in JSON format."""
    
    protocol_version: str = "1.0"
    
    def __init__(self):
        self.protocol_version = "1.0"
        self._metrics: List[Dict[str, Any]] = []
    
    def export(self, metrics: List[Metric]) -> str:
        data = [{"name": m.name, "value": m.value, "labels": m.labels, "type": m.metric_type} for m in metrics]
        return json.dumps(data, indent=2)
