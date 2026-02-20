"""Safety Layer for plan evaluation.

Implements SYSTEM_SPEC_v3.1 - Safety Layer.
With comprehensive audit logging.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

# Import audit for logging
from synapse.observability.logger import audit


class SafetyReport(BaseModel):
    """Safety evaluation report."""
    safe: bool
    risk_level: int
    issues: List[Dict]
    requires_human_approval: bool
    protocol_version: str = "1.0"


class SafetyLayer:
    """Safety layer for evaluating plans before execution."""

    DANGEROUS_PATTERNS = [
        'delete all files',
        'format disk',
        'bypass security',
        'escalate privileges',
        'remove system',
        'drop table',
        'rm -rf /',
        'chmod 777',
    ]

    def __init__(self, security_manager=None, llm_provider=None):
        self.security = security_manager
        self.llm = llm_provider

        # Audit: safety layer initialized
        audit(
            event="safety_layer_initialized",
            has_security_manager=security_manager is not None,
            has_llm_provider=llm_provider is not None,
            protocol_version=PROTOCOL_VERSION
        )

    async def evaluate_plan(self, plan: Dict) -> SafetyReport:
        """Evaluate plan for safety with audit logging.

        Args:
            plan: Plan to evaluate

        Returns:
            SafetyReport with evaluation results
        """
        # Audit: plan evaluation started
        audit(
            event="safety_evaluation_started",
            plan_id=plan.get("id", "unknown"),
            risk_level=plan.get("risk_level", 0),
            protocol_version=PROTOCOL_VERSION
        )

        issues = []

        # 1. Pattern matching for dangerous operations
        pattern_issues = await self._check_dangerous_patterns(plan)
        issues.extend(pattern_issues)

        # 2. Capability validation
        capability_issues = await self._validate_capabilities(plan)
        issues.extend(capability_issues)

        # 3. Resource limit check
        resource_issues = await self._check_resource_limits(plan)
        issues.extend(resource_issues)

        # Determine if human approval needed
        risk_level = plan.get("risk_level", 0)
        requires_approval = risk_level >= 3 or len(issues) > 0

        report = SafetyReport(
            safe=len(issues) == 0,
            risk_level=risk_level,
            issues=issues,
            requires_human_approval=requires_approval,
            protocol_version=PROTOCOL_VERSION
        )

        # Audit: plan evaluation completed
        audit(
            event="safety_evaluation_completed",
            safe=report.safe,
            issues_count=len(issues),
            requires_approval=requires_approval,
            protocol_version=PROTOCOL_VERSION
        )

        return report

    async def _check_dangerous_patterns(self, plan: Dict) -> List[Dict]:
        """Check for dangerous patterns in plan."""
        issues = []
        plan_text = str(plan).lower()

        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in plan_text:
                issues.append({
                    "type": "dangerous_pattern",
                    "severity": "high",
                    "pattern": pattern,
                    "message": f"Dangerous pattern detected: {pattern}"
                })

        return issues

    async def _validate_capabilities(self, plan: Dict) -> List[Dict]:
        """Validate required capabilities."""
        issues = []
        required_caps = plan.get("required_capabilities", [])

        if self.security:
            for cap in required_caps:
                # Check if capability is valid
                if not self._is_valid_capability(cap):
                    issues.append({
                        "type": "invalid_capability",
                        "severity": "medium",
                        "capability": cap,
                        "message": f"Invalid capability format: {cap}"
                    })

        return issues

    async def _check_resource_limits(self, plan: Dict) -> List[Dict]:
        """Check resource limits."""
        issues = []
        resources = plan.get("resources", {})

        # Check for excessive resource requests
        if resources.get("cpu_seconds", 0) > 300:
            issues.append({
                "type": "resource_limit",
                "severity": "medium",
                "resource": "cpu_seconds",
                "message": "CPU request exceeds 5 minutes"
            })

        if resources.get("memory_mb", 0) > 4096:
            issues.append({
                "type": "resource_limit",
                "severity": "medium",
                "resource": "memory_mb",
                "message": "Memory request exceeds 4GB"
            })

        return issues

    def _is_valid_capability(self, capability: str) -> bool:
        """Check if capability format is valid."""
        # Basic validation: must have at least one colon
        return ":" in capability and len(capability) > 3
