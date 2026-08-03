"""
Synapse Ecosystem Layer - Phase 7.2

Components:
- DomainPacks: Pre-built agent configurations
- CapabilityMarketplace: Capability catalog & versioning
- ExternalAPIGateway: REST/GraphQL/WebSocket APIs
"""

PROTOCOL_VERSION: str = "1.0"

from synapse.ecosystem.api_gateway import ExternalAPIGateway
from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
from synapse.ecosystem.domain_packs import DomainPack

__all__ = [
    'PROTOCOL_VERSION',
    'CapabilityMarketplace',
    'DomainPack',
    'ExternalAPIGateway'
]
