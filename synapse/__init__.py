"""Synapse - Distributed Cognitive Platform for Autonomous Agents

Version: 3.1.0
Protocol Version: 1.0
Spec Version: 3.1
"""

__version__ = "3.1.0"
__author__ = "Synapse Contributors"
__license__ = "MIT"

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

from synapse.core.models import *
from synapse.core.security import CapabilityManager
from synapse.core.rollback import RollbackManager
from synapse.core.checkpoint import CheckpointManager
from synapse.skills.base import BaseSkill
