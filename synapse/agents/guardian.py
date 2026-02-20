"""Guardian Agent for security validation.

Implements SYSTEM_SPEC_v3.1 - Guardian Agent.
With comprehensive audit logging.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Import audit for logging
from synapse.observability.logger import audit


@dataclass
class SecurityCheckResult:
    """Result of security check."""
    approved: bool
    reason: str
    blocked_capabilities: List[str]
    requires_human_approval: bool
    protocol_version: str = "1.0"


class GuardianAgent:
    """Agent for security validation before execution with audit logging."""

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self, security_manager=None, audit_logger=None):
        self.security = security_manager
        self.audit_logger = audit_logger

        # Audit: guardian agent initialized
        audit(
            event="guardian_agent_initialized",
            has_security_manager=security_manager is not None,
            protocol_version=self.protocol_version
        )

    async def validate_plan(self, plan: Dict, context: Dict = None) -> SecurityCheckResult:
        """Validate plan before execution with audit logging.

        Args:
            plan: Plan to validate
            context: Execution context

        Returns:
            SecurityCheckResult with validation results
        """
        # Audit: plan validation started
        audit(
            event="plan_validation_started",
            plan_id=plan.get("id", "unknown"),
            risk_level=plan.get("risk_level", 0),
            protocol_version=self.protocol_version
        )

        # 1. Capability check
        caps_result = await self._check_capabilities(plan, context)

        if not caps_result.approved:
            # Audit: validation denied - missing capabilities
            audit(
                event="plan_validation_denied",
                reason="missing_capabilities",
                blocked=caps_result.blocked_capabilities,
                protocol_version=self.protocol_version
            )
            return caps_result

        # 2. Human approval check for high risk
        risk_level = plan.get("risk_level", 0)
        if risk_level >= 3:
            approval = await self._request_human_approval(plan, context)
            if not approval.approved:
                # Audit: human denied
                audit(
                    event="human_approval_denied",
                    plan_id=plan.get("id", "unknown"),
                    protocol_version=self.protocol_version
                )
                return SecurityCheckResult(
                    approved=False,
                    reason="human_denied",
                    blocked_capabilities=[],
                    requires_human_approval=True,
                    protocol_version=self.protocol_version
                )

        # Audit: validation approved
        audit(
            event="plan_validation_approved",
            plan_id=plan.get("id", "unknown"),
            protocol_version=self.protocol_version
        )

        return SecurityCheckResult(
            approved=True,
            reason="all_checks_passed",
            blocked_capabilities=[],
            requires_human_approval=risk_level >= 3,
            protocol_version=self.protocol_version
        )

    async def _check_capabilities(self, plan: Dict, context: Dict) -> SecurityCheckResult:
        """Check required capabilities."""
        required_caps = plan.get("required_capabilities", [])

        if not required_caps:
            return SecurityCheckResult(
                approved=True,
                reason="no_capabilities_required",
                blocked_capabilities=[],
                requires_human_approval=False,
                protocol_version=self.protocol_version
            )

        if self.security:
            result = await self.security.check_capabilities(
                required=required_caps,
                context=context
            )

            blocked = getattr(result, 'blocked_capabilities', [])

            return SecurityCheckResult(
                approved=result.approved,
                reason="capability_check_complete",
                blocked_capabilities=blocked,
                requires_human_approval=False,
                protocol_version=self.protocol_version
            )

        # No security manager - approve by default
        return SecurityCheckResult(
            approved=True,
            reason="no_security_manager",
            blocked_capabilities=[],
            requires_human_approval=False,
            protocol_version=self.protocol_version
        )

    async def _request_human_approval(self, plan: Dict, context: Dict) -> SecurityCheckResult:
        """Request human approval for high-risk plan."""
        # Audit: human approval requested
        audit(
            event="human_approval_requested",
            plan_id=plan.get("id", "unknown"),
            risk_level=plan.get("risk_level", 0),
            protocol_version=self.protocol_version
        )

        if self.security:
            approval = await self.security.request_human_approval(
                plan=plan,
                trace_id=context.get("trace_id", "unknown") if context else "unknown"
            )
            return SecurityCheckResult(
                approved=approval.approved,
                reason="human_approval_complete",
                blocked_capabilities=[],
                requires_human_approval=True,
                protocol_version=self.protocol_version
            )

        # No security manager - auto-approve
        return SecurityCheckResult(
            approved=True,
            reason="auto_approved_no_security",
            blocked_capabilities=[],
            requires_human_approval=True,
            protocol_version=self.protocol_version
        )

    async def check_execution_safety(self, skill_name: str, params: Dict) -> SecurityCheckResult:
        """Check if skill execution is safe with audit logging."""
        # Audit: execution safety check started
        audit(
            event="execution_safety_check_started",
            skill_name=skill_name,
            protocol_version=self.protocol_version
        )

        # Check for dangerous parameters
        dangerous_params = self._check_dangerous_params(params)

        if dangerous_params:
            # Audit: dangerous params detected
            audit(
                event="dangerous_params_detected",
                skill_name=skill_name,
                params=dangerous_params,
                protocol_version=self.protocol_version
            )

            return SecurityCheckResult(
                approved=False,
                reason="dangerous_parameters",
                blocked_capabilities=[],
                requires_human_approval=True,
                protocol_version=self.protocol_version
            )

        # Audit: execution safety check passed
        audit(
            event="execution_safety_check_passed",
            skill_name=skill_name,
            protocol_version=self.protocol_version
        )

        return SecurityCheckResult(
            approved=True,
            reason="safety_check_passed",
            blocked_capabilities=[],
            requires_human_approval=False,
            protocol_version=self.protocol_version
        )

    def _check_dangerous_params(self, params: Dict) -> List[str]:
        """Check for dangerous parameters."""
        dangerous = []
        dangerous_patterns = ['rm -rf', 'format', 'delete', 'drop', 'truncate']

        for key, value in params.items():
            value_str = str(value).lower()
            for pattern in dangerous_patterns:
                if pattern in value_str:
                    dangerous.append(f"{key}: {pattern}")

        return dangerous
