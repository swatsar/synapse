"""Forecaster Agent for Phase 12.

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
class ForecastRequest:
    """Request for forecast."""
    target: str
    forecast_type: str
    horizon_minutes: int
    seed: int
    protocol_version: str = "1.0"


@dataclass
class ForecastResult:
    """Result of forecast."""
    forecast_id: str
    predictions: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    confidence: float
    risk_level: int
    protocol_version: str = "1.0"


class ForecasterAgent:
    """Agent for LLM/ML-driven forecasting."""

    PROTOCOL_VERSION = "1.0"

    def __init__(
        self,
        llm: Optional[Any] = None,
        telemetry: Optional[Any] = None,
        resource_manager: Optional[Any] = None,
        policy_engine: Optional[Any] = None
    ):
        self.llm = llm
        self.telemetry = telemetry
        self.resource_manager = resource_manager
        self.policy_engine = policy_engine

    def _generate_forecast_id(self, seed: int, target: str) -> str:
        """Generate deterministic forecast ID."""
        data = f"{seed}:{target}"
        hash_bytes = hashlib.sha256(data.encode()).digest()
        return str(uuid.UUID(bytes=hash_bytes[:16]))

    async def forecast(self, request: ForecastRequest) -> ForecastResult:
        """Generate forecast based on request."""
        forecast_id = self._generate_forecast_id(request.seed, request.target)

        # Get metrics
        metrics = {}
        if self.telemetry:
            if hasattr(self.telemetry, 'get_historical_metrics'):
                metrics['historical'] = self.telemetry.get_historical_metrics()
            if hasattr(self.telemetry, 'get_current_metrics'):
                metrics['current'] = self.telemetry.get_current_metrics()

        # Generate predictions
        predictions = await self._generate_predictions(request, metrics)

        # Generate recommendations
        recommendations = self._generate_recommendations(predictions)

        # Calculate confidence and risk
        confidence = self._calculate_confidence(predictions)
        risk_level = self._calculate_risk_level(predictions)

        return ForecastResult(
            forecast_id=forecast_id,
            predictions=predictions,
            recommendations=recommendations,
            confidence=confidence,
            risk_level=risk_level
        )

    async def _generate_predictions(
        self,
        request: ForecastRequest,
        metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate predictions using LLM or ML models."""
        predictions = []
        rng = random.Random(request.seed)

        # Use LLM if available
        if self.llm and hasattr(self.llm, 'generate'):
            try:
                prompt = f"Forecast {request.forecast_type} for {request.target} over {request.horizon_minutes} minutes"
                response = await self.llm.generate(prompt)
                # Parse LLM response into predictions
                predictions.append({
                    'type': 'llm_forecast',
                    'target': request.target,
                    'forecast': str(response),
                    'confidence': rng.uniform(0.7, 0.95)
                })
            except Exception:
                pass

        # Fallback to trend-based prediction
        historical = metrics.get('historical', {})

        if 'cpu_trend' in historical:
            cpu_trend = historical['cpu_trend']
            if cpu_trend and cpu_trend[-1] > 70:
                predictions.append({
                    'type': 'cpu_overload',
                    'target': 'cpu',
                    'probability': min(0.9, cpu_trend[-1] / 100 + 0.1),
                    'eta_minutes': request.horizon_minutes
                })

        if 'memory_trend' in historical:
            memory_trend = historical['memory_trend']
            if memory_trend and memory_trend[-1] > 1500:
                predictions.append({
                    'type': 'memory_exhaustion',
                    'target': 'memory',
                    'probability': min(0.85, memory_trend[-1] / 2048 + 0.1),
                    'eta_minutes': request.horizon_minutes
                })

        if 'failure_trend' in historical:
            failure_trend = historical['failure_trend']
            if failure_trend and failure_trend[-1] > 0.1:
                predictions.append({
                    'type': 'skill_failure',
                    'target': 'skills',
                    'probability': failure_trend[-1],
                    'eta_minutes': request.horizon_minutes
                })

        # Default if no predictions
        if not predictions:
            predictions.append({
                'type': 'stable',
                'target': request.target,
                'probability': 0.1,
                'confidence': 0.8
            })

        return predictions

    def _generate_recommendations(
        self,
        predictions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on predictions."""
        recommendations = []

        for pred in predictions:
            pred_type = pred.get('type', '')
            prob = pred.get('probability', 0)

            if pred_type == 'cpu_overload':
                recommendations.append({
                    'action': 'throttle_cpu',
                    'priority': 'high' if prob > 0.7 else 'medium',
                    'auto_apply': prob < 0.8
                })
            elif pred_type == 'memory_exhaustion':
                recommendations.append({
                    'action': 'gc_or_limit',
                    'priority': 'high' if prob > 0.7 else 'medium',
                    'auto_apply': prob < 0.8
                })
            elif pred_type == 'skill_failure':
                recommendations.append({
                    'action': 'review_skill',
                    'priority': 'medium',
                    'auto_apply': False
                })

        return recommendations

    def _calculate_confidence(self, predictions: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence."""
        if not predictions:
            return 0.5

        confidences = [p.get('confidence', p.get('probability', 0.5)) for p in predictions]
        return sum(confidences) / len(confidences)

    def _calculate_risk_level(self, predictions: List[Dict[str, Any]]) -> int:
        """Calculate overall risk level."""
        if not predictions:
            return 0

        max_risk = 0
        for pred in predictions:
            prob = pred.get('probability', 0)
            pred_type = pred.get('type', '')

            if 'overload' in pred_type or 'exhaustion' in pred_type:
                if prob > 0.8:
                    max_risk = max(max_risk, 4)
                elif prob > 0.6:
                    max_risk = max(max_risk, 3)
                else:
                    max_risk = max(max_risk, 2)
            elif 'failure' in pred_type:
                if prob > 0.5:
                    max_risk = max(max_risk, 3)
                else:
                    max_risk = max(max_risk, 1)

        return min(5, max_risk)
