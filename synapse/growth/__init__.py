"""Mycelial growth network: the persistent learning substrate of Synapse."""
from synapse.growth.autonomy import AutonomyLoop, get_autonomy_loop
from synapse.growth.network import GrowthNetwork, PROTOCOL_VERSION, get_growth_network

__all__ = [
    "AutonomyLoop",
    "GrowthNetwork",
    "PROTOCOL_VERSION",
    "get_autonomy_loop",
    "get_growth_network",
]
