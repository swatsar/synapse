PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

import pytest
from synapse.core.isolation_policy import IsolationEnforcementPolicy, RuntimeIsolationType, SkillTrustLevel

@pytest.fixture
def policy():
    return IsolationEnforcementPolicy()

@pytest.mark.parametrize(
    "trust,risk,expected",
    [
        # Trusted + low risk → subprocess
        (SkillTrustLevel.TRUSTED, 1, RuntimeIsolationType.SUBPROCESS),
        # Verified + medium risk → subprocess
        (SkillTrustLevel.VERIFIED, 2, RuntimeIsolationType.SUBPROCESS),
        # Unverified → sandbox (strictest, per Execution Trust Model)
        (SkillTrustLevel.UNVERIFIED, 1, RuntimeIsolationType.SANDBOX),
        # Human-approved + low risk → subprocess
        (SkillTrustLevel.HUMAN_APPROVED, 2, RuntimeIsolationType.SUBPROCESS),
        # Any trust + risk >= 3 → container minimum
        (SkillTrustLevel.TRUSTED, 4, RuntimeIsolationType.CONTAINER),
        (SkillTrustLevel.VERIFIED, 3, RuntimeIsolationType.CONTAINER),
        (SkillTrustLevel.HUMAN_APPROVED, 5, RuntimeIsolationType.CONTAINER),
        (SkillTrustLevel.UNVERIFIED, 3, RuntimeIsolationType.CONTAINER),
    ],
)
def test_isolation_mapping(policy, trust, risk, expected):
    assert policy.get_required_isolation(trust, risk) == expected


def test_unknown_trust_defaults_to_container(policy):
    """Unknown trust levels should default to container for safety."""
    result = policy.get_required_isolation("unknown_level", 1)
    assert result == RuntimeIsolationType.CONTAINER


def test_human_approved_trust_level_exists():
    """HUMAN_APPROVED must exist per 4-level Execution Trust Model."""
    assert hasattr(SkillTrustLevel, 'HUMAN_APPROVED')
    assert SkillTrustLevel.HUMAN_APPROVED == "human_approved"
