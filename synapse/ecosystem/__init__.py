"""
Synapse Ecosystem Layer - Phase 7.2

Components:
- DomainPacks: Pre-built agent configurations
- CapabilityMarketplace: Capability catalog & versioning
- ExternalAPIGateway: REST/GraphQL/WebSocket APIs
"""

PROTOCOL_VERSION: str = "1.0"

from synapse.ecosystem.domain_packs import DomainPack
from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
from synapse.ecosystem.api_gateway import ExternalAPIGateway

__all__ = [
    'DomainPack',
    'CapabilityMarketplace',
    'ExternalAPIGateway',
    'PROTOCOL_VERSION'
]
