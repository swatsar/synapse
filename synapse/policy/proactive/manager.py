"""Proactive Policy Manager for Phase 12.

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
class ProactiveRule:
    """Rule for proactive policy management."""
    name: str
    condition: Dict[str, Any]
    action: Dict[str, Any]
    risk_level: int
    cluster_wide: bool = False
    protocol_version: str = "1.0"


@dataclass
class ProactiveAction:
    """Action taken by proactive manager."""
    action_type: str
    target: str
    auto_applied: bool = False
    requires_approval: bool = False
    pending_approval: bool = False
    approval_denied: bool = False
    cluster_propagated: bool = False
    protocol_version: str = "1.0"


@dataclass
class RuleCreationResult:
    """Result of rule creation."""
    success: bool
    rule_id: Optional[str] = None
    cluster_propagated: bool = False


class ProactivePolicyManager:
    """Manager for proactive policy enforcement."""

    PROTOCOL_VERSION = "1.0"

    def __init__(
        self,
        resource_manager: Optional[Any] = None,
        telemetry: Optional[Any] = None,
        policy_engine: Optional[Any] = None,
        capability_manager: Optional[Any] = None,
        cluster_manager: Optional[Any] = None,
        human_approval: Optional[Any] = None,
        rollback_manager: Optional[Any] = None
    ):
        self.resource_manager = resource_manager
        self.telemetry = telemetry
        self.policy_engine = policy_engine
        self.capability_manager = capability_manager
        self.cluster_manager = cluster_manager
        self.human_approval = human_approval
        self.rollback_manager = rollback_manager
        self.audit_logger: Optional[Any] = None
        self._rules: Dict[str, ProactiveRule] = {}

    def _generate_rule_id(self, rule: ProactiveRule) -> str:
        """Generate deterministic rule ID."""
        data = f"{rule.name}:{rule.risk_level}"
        hash_bytes = hashlib.sha256(data.encode()).digest()
        return str(uuid.UUID(bytes=hash_bytes[:16]))

    async def create_rule(self, rule: ProactiveRule) -> RuleCreationResult:
        """Create a new proactive rule."""
        rule_id = self._generate_rule_id(rule)
        self._rules[rule_id] = rule

        # Register with policy engine
        if self.policy_engine and hasattr(self.policy_engine, 'register_rule'):
            self.policy_engine.register_rule(rule_id, rule)

        # Cluster propagation
        cluster_propagated = False
        if rule.cluster_wide and self.cluster_manager:
            if hasattr(self.cluster_manager, 'broadcast_rule'):
                result = await self.cluster_manager.broadcast_rule({
                    'rule_id': rule_id,
                    'rule': rule
                })
                cluster_propagated = result.get('success', False)

        # Audit logging
        if self.audit_logger:
            self.audit_logger.record({
                'event': 'rule_created',
                'rule_id': rule_id,
                'rule_name': rule.name,
                'risk_level': rule.risk_level
            })

        return RuleCreationResult(
            success=True,
            rule_id=rule_id,
            cluster_propagated=cluster_propagated
        )

    def _evaluate_condition(self, condition: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """Evaluate if condition is met."""
        for key, condition_value in condition.items():
            metric_value = metrics.get(key, 0)

            if isinstance(condition_value, str):
                # Parse condition like ">80", "<50", ">=70"
                if condition_value.startswith(">="):
                    threshold = float(condition_value[2:])
                    if metric_value < threshold:
                        return False
                elif condition_value.startswith("<="):
                    threshold = float(condition_value[2:])
                    if metric_value > threshold:
                        return False
                elif condition_value.startswith(">"):
                    threshold = float(condition_value[1:])
                    if metric_value <= threshold:
                        return False
                elif condition_value.startswith("<"):
                    threshold = float(condition_value[1:])
                    if metric_value >= threshold:
                        return False
                else:
                    # Direct comparison
                    if metric_value != condition_value:
                        return False

        return True

    async def evaluate_and_act(self, metrics: Dict[str, Any]) -> ProactiveAction:
        """Evaluate metrics and take proactive action."""
        # Get telemetry data if available
        if self.telemetry and hasattr(self.telemetry, 'get_metrics'):
            telemetry_data = self.telemetry.get_metrics()
            metrics = {**telemetry_data, **metrics}

        # Find matching rules
        matching_rules = []
        for rule_id, rule in self._rules.items():
            if self._evaluate_condition(rule.condition, metrics):
                matching_rules.append((rule_id, rule))

        # Sort by risk level (highest first)
        matching_rules.sort(key=lambda x: x[1].risk_level, reverse=True)

        # If we have matching rules, process them
        if matching_rules:
            # Take action based on highest priority rule
            rule_id, rule = matching_rules[0]
            action_type = rule.action.get("type", "alert")
            target = rule.action.get("target", "system")

            # Check if approval required based on rule risk level
            requires_approval = rule.risk_level >= 3

            # Also check policy engine
            if self.policy_engine and hasattr(self.policy_engine, 'requires_approval'):
                if self.policy_engine.requires_approval(rule.risk_level):
                    requires_approval = True

            # Check capabilities
            if self.capability_manager and hasattr(self.capability_manager, 'check_capabilities'):
                cap_result = self.capability_manager.check_capabilities(
                    required=[f"proactive:{action_type}"],
                    context={}
                )
                if not cap_result.approved:
                    action = ProactiveAction(
                        action_type="blocked",
                        target=target,
                        auto_applied=False,
                        requires_approval=True
                    )
                    return action

            # Handle approval flow
            if requires_approval:
                if self.human_approval:
                    # Check if pending
                    if hasattr(self.human_approval, 'is_pending') and self.human_approval.is_pending():
                        action = ProactiveAction(
                            action_type=action_type,
                            target=target,
                            pending_approval=True,
                            requires_approval=True,
                            auto_applied=False
                        )
                        if self.audit_logger:
                            self.audit_logger.record({
                                'event': 'proactive_action',
                                'action_type': action.action_type,
                                'target': action.target,
                                'pending_approval': True
                            })
                        return action

                    # Request approval
                    if hasattr(self.human_approval, 'request_approval'):
                        approval_result = await self.human_approval.request_approval({
                            'action': action_type,
                            'target': target,
                            'risk_level': rule.risk_level
                        })

                        # Check if approved
                        approved = getattr(approval_result, 'approved', True)

                        if not approved:
                            action = ProactiveAction(
                                action_type=action_type,
                                target=target,
                                requires_approval=True,
                                approval_denied=True,
                                auto_applied=False
                            )
                            if self.audit_logger:
                                self.audit_logger.record({
                                    'event': 'proactive_action',
                                    'action_type': action.action_type,
                                    'target': action.target,
                                    'approval_denied': True
                                })
                            return action
                        else:
                            # Approved - execute with approval flag set
                            action = ProactiveAction(
                                action_type=action_type,
                                target=target,
                                requires_approval=True,
                                auto_applied=False
                            )
                            if self.audit_logger:
                                self.audit_logger.record({
                                    'event': 'proactive_action',
                                    'action_type': action.action_type,
                                    'target': action.target,
                                    'approved': True
                                })
                            return action

                # Requires approval but no human_approval available
                action = ProactiveAction(
                    action_type=action_type,
                    target=target,
                    requires_approval=True,
                    auto_applied=False
                )
                if self.audit_logger:
                    self.audit_logger.record({
                        'event': 'proactive_action',
                        'action_type': action.action_type,
                        'target': action.target,
                        'requires_approval': True
                    })
                return action
            else:
                # Low risk - auto apply
                action = ProactiveAction(
                    action_type=action_type,
                    target=target,
                    auto_applied=True,
                    requires_approval=False
                )
                if self.audit_logger:
                    self.audit_logger.record({
                        'event': 'proactive_action',
                        'action_type': action.action_type,
                        'target': action.target,
                        'auto_applied': True
                    })
                return action

        # Default action when no rules match
        action = ProactiveAction(
            action_type="none",
            target="system"
        )

        # Check for default proactive actions based on metrics
        if metrics.get("cpu", 0) > 80 or metrics.get("predicted_cpu", 0) > 90:
            action = ProactiveAction(
                action_type="throttle",
                target="cpu",
                auto_applied=True
            )
        elif metrics.get("memory", 0) > 1800 or metrics.get("predicted_memory", 0) > 2000:
            action = ProactiveAction(
                action_type="gc",
                target="memory",
                auto_applied=True
            )

        # Audit logging
        if self.audit_logger:
            self.audit_logger.record({
                'event': 'proactive_action',
                'action_type': action.action_type,
                'target': action.target,
                'auto_applied': action.auto_applied
            })

        return action

    async def predict_violation(self, action_context: Dict[str, Any]) -> Dict[str, Any]:
        """Predict if an action would cause a policy violation."""
        # Get historical violation trends
        violation_risk = 0.0

        if self.telemetry and hasattr(self.telemetry, 'get_metrics'):
            metrics = self.telemetry.get_metrics()
            violations = metrics.get('policy_violations_trend', [])
            if violations:
                # Increasing trend indicates higher risk
                if violations[-1] > violations[0]:
                    violation_risk = min(0.9, violations[-1] / 10)

        # Check action context
        action = action_context.get('action', '')
        predicted_risk = action_context.get('predicted_risk', 0)

        # High-risk actions
        dangerous_actions = ['delete', 'kill', 'execute_command', 'rm']
        if any(d in action.lower() for d in dangerous_actions):
            violation_risk = max(violation_risk, 0.7)

        # Combine with predicted risk
        violation_risk = max(violation_risk, predicted_risk)

        return {
            'violation_risk': violation_risk,
            'action': action,
            'recommendation': 'block' if violation_risk > 0.8 else 'approve'
        }

    async def evaluate_action(self, action_context: Dict[str, Any]) -> Any:
        """Evaluate an action for policy compliance."""
        prediction = await self.predict_violation(action_context)

        # Check capabilities
        blocked = False
        if self.capability_manager and hasattr(self.capability_manager, 'check_capabilities'):
            action = action_context.get('action', '')
            cap_result = self.capability_manager.check_capabilities(
                required=[f"action:{action}"],
                context=action_context
            )
            blocked = not cap_result.approved

        # Determine if approval needed
        requires_approval = False
        if self.policy_engine and hasattr(self.policy_engine, 'requires_approval'):
            risk = action_context.get('predicted_risk', 0)
            requires_approval = self.policy_engine.requires_approval(int(risk * 5))

        # Create result
        result = type('ActionResult', (), {
            'blocked': blocked,
            'requires_approval': requires_approval,
            'decision': 'deny' if blocked else ('approve' if not requires_approval else 'pending'),
            'prediction': prediction
        })()

        return result
