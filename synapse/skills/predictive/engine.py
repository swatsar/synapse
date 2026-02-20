"""Predictive Engine for Phase 12.

Predictive Autonomy & Proactive Risk Management.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import asyncio
import random


PROTOCOL_VERSION: str = "1.0"


@dataclass
class PredictionRequest:
    """Request for prediction."""
    target: str
    prediction_type: str
    horizon_minutes: int
    seed: int
    cluster_wide: bool = False
    create_snapshot: bool = False
    protocol_version: str = "1.0"


@dataclass
class Prediction:
    """Single prediction result."""
    type: str
    probability: float
    severity: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MitigationAction:
    """Mitigation action for prediction."""
    action_type: str
    target: str
    auto_applied: bool = False
    cluster_propagated: bool = False
    protocol_version: str = "1.0"


@dataclass
class PredictionResult:
    """Result of prediction."""
    prediction_id: str
    predictions: List[Dict[str, Any]]
    risk_level: int
    requires_approval: bool = False
    auto_executed: bool = False
    cluster_propagated: bool = False
    consistent: bool = True
    mitigation: Optional[MitigationAction] = None
    protocol_version: str = "1.0"


class PredictiveEngine:
    """Engine for predictive analysis and forecasting."""

    PROTOCOL_VERSION = "1.0"

    def __init__(
        self,
        telemetry: Optional[Any] = None,
        resource_manager: Optional[Any] = None,
        policy_engine: Optional[Any] = None,
        cluster_manager: Optional[Any] = None,
        human_approval: Optional[Any] = None
    ):
        self.telemetry = telemetry
        self.resource_manager = resource_manager
        self.policy_engine = policy_engine
        self.cluster_manager = cluster_manager
        self.human_approval = human_approval
        self.audit_logger: Optional[Any] = None

    def _generate_deterministic_id(self, seed: int, target: str, prediction_type: str) -> str:
        """Generate deterministic prediction ID."""
        data = f"{seed}:{target}:{prediction_type}"
        hash_bytes = hashlib.sha256(data.encode()).digest()
        return str(uuid.UUID(bytes=hash_bytes[:16]))

    async def predict(self, request: PredictionRequest) -> PredictionResult:
        """Generate prediction based on request."""
        # Generate deterministic ID
        prediction_id = self._generate_deterministic_id(
            request.seed,
            request.target,
            request.prediction_type
        )

        # Get metrics if available
        metrics = {}
        if self.telemetry:
            if hasattr(self.telemetry, 'get_historical_metrics'):
                metrics['historical'] = self.telemetry.get_historical_metrics()
            if hasattr(self.telemetry, 'get_current_metrics'):
                metrics['current'] = self.telemetry.get_current_metrics()
            if hasattr(self.telemetry, 'get_cluster_metrics') and request.cluster_wide:
                metrics['cluster'] = self.telemetry.get_cluster_metrics()

        # Analyze and generate predictions
        predictions = await self._analyze_trends(request, metrics)

        # Calculate risk level
        risk_level = self._calculate_risk_level(predictions)

        # Determine if approval needed
        requires_approval = False
        if self.policy_engine and hasattr(self.policy_engine, 'requires_approval'):
            requires_approval = self.policy_engine.requires_approval(risk_level)

        # Auto-execute low risk
        auto_executed = risk_level < 3 and not requires_approval

        # Cluster propagation
        cluster_propagated = False
        if request.cluster_wide and self.cluster_manager:
            if hasattr(self.cluster_manager, 'broadcast_prediction'):
                result = await self.cluster_manager.broadcast_prediction({
                    'prediction_id': prediction_id,
                    'predictions': predictions
                })
                cluster_propagated = result.get('success', False)

        # Create mitigation if needed
        mitigation = None
        if risk_level >= 2:
            mitigation = MitigationAction(
                action_type="throttle" if risk_level < 4 else "alert",
                target=request.target,
                auto_applied=auto_executed,
                cluster_propagated=cluster_propagated
            )

        # Create snapshot before mitigation if requested
        if request.create_snapshot and self.cluster_manager:
            if hasattr(self.cluster_manager, 'create_cluster_snapshot'):
                await self.cluster_manager.create_cluster_snapshot({
                    'prediction_id': prediction_id,
                    'reason': 'pre_mitigation'
                })

        # Audit logging
        if self.audit_logger:
            self.audit_logger.record({
                'event': 'prediction',
                'prediction_id': prediction_id,
                'risk_level': risk_level,
                'cluster_wide': request.cluster_wide
            })

        return PredictionResult(
            prediction_id=prediction_id,
            predictions=predictions,
            risk_level=risk_level,
            requires_approval=requires_approval,
            auto_executed=auto_executed,
            cluster_propagated=cluster_propagated,
            mitigation=mitigation
        )

    async def _analyze_trends(
        self,
        request: PredictionRequest,
        metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze trends and generate predictions."""
        predictions = []

        # Use deterministic random for reproducibility
        rng = random.Random(request.seed)

        # CPU overload prediction
        if request.target in ["system", "cpu", "cluster"]:
            cpu_trend = metrics.get('historical', {}).get('cpu_trend', [])
            if cpu_trend:
                trend_increasing = all(cpu_trend[i] < cpu_trend[i+1] for i in range(len(cpu_trend)-1))
                if trend_increasing or cpu_trend[-1] > 70:
                    predictions.append({
                        'type': 'cpu_overload',
                        'probability': min(0.95, cpu_trend[-1] / 100 + 0.1),
                        'severity': 'high' if cpu_trend[-1] > 80 else 'medium',
                        'eta_minutes': request.horizon_minutes
                    })

        # Memory exhaustion prediction
        if request.target in ["system", "memory", "cluster"]:
            memory_trend = metrics.get('historical', {}).get('memory_trend', [])
            if memory_trend:
                trend_increasing = all(memory_trend[i] < memory_trend[i+1] for i in range(len(memory_trend)-1))
                if trend_increasing or memory_trend[-1] > 1500:
                    predictions.append({
                        'type': 'memory_exhaustion',
                        'probability': min(0.9, memory_trend[-1] / 2048 + 0.1),
                        'severity': 'high' if memory_trend[-1] > 1800 else 'medium',
                        'eta_minutes': request.horizon_minutes
                    })

        # Skill failure prediction
        if request.target.startswith("skill:"):
            failure_trend = metrics.get('historical', {}).get('failure_trend', [])
            if failure_trend:
                predictions.append({
                    'type': 'skill_failure',
                    'probability': failure_trend[-1] if failure_trend else 0.1,
                    'severity': 'medium',
                    'skill': request.target.split(":")[1] if ":" in request.target else "unknown"
                })

        # Default prediction if none generated
        if not predictions:
            predictions.append({
                'type': 'no_issue_detected',
                'probability': 0.1,
                'severity': 'low'
            })

        return predictions

    def _calculate_risk_level(self, predictions: List[Dict[str, Any]]) -> int:
        """Calculate overall risk level from predictions."""
        if not predictions:
            return 0

        max_severity = 0
        for p in predictions:
            severity = p.get('severity', 'low')
            if severity == 'high':
                max_severity = max(max_severity, 4)
            elif severity == 'medium':
                max_severity = max(max_severity, 2)

            prob = p.get('probability', 0)
            if prob > 0.8:
                max_severity = max(max_severity, 5)
            elif prob > 0.6:
                max_severity = max(max_severity, 3)

        return min(5, max_severity)
