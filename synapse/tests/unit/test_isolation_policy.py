PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
import pytest
from synapse.core.isolation_policy import IsolationEnforcementPolicy, RuntimeIsolationType, SkillTrustLevel

@pytest.mark.parametrize(
    "trust,risk,expected",
    [
        (SkillTrustLevel.TRUSTED, 1, RuntimeIsolationType.SUBPROCESS),
        (SkillTrustLevel.VERIFIED, 2, RuntimeIsolationType.SUBPROCESS),
        (SkillTrustLevel.UNVERIFIED, 1, RuntimeIsolationType.CONTAINER),
        (SkillTrustLevel.TRUSTED, 4, RuntimeIsolationType.CONTAINER),
    ],
)
def test_isolation_mapping(trust, risk, expected):
    assert IsolationEnforcementPolicy.get_required_isolation(trust, risk) == expected
