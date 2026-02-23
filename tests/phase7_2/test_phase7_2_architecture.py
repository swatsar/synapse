"""
Phase 7.2: Ecosystem Layer - Architecture Tests

TDD tests for Domain Packs, Capability Marketplace, and External API Gateway.
"""

import pytest
from datetime import datetime
from typing import Dict, List, Optional, Any


class TestDomainPacks:
    """Tests for Domain Packs component"""
    
    def test_domain_pack_exists(self):
        """DomainPack class must exist"""
        from synapse.ecosystem.domain_packs import DomainPack
        assert DomainPack is not None
    
    def test_domain_pack_has_name(self):
        """DomainPack must have name attribute"""
        from synapse.ecosystem.domain_packs import DomainPack
        pack = DomainPack(
            name="test_pack",
            version="1.0.0",
            description="Test domain pack"
        )
        assert pack.name == "test_pack"
    
    def test_domain_pack_has_version(self):
        """DomainPack must have version attribute"""
        from synapse.ecosystem.domain_packs import DomainPack
        pack = DomainPack(
            name="test_pack",
            version="1.0.0",
            description="Test domain pack"
        )
        assert pack.version == "1.0.0"
    
    def test_domain_pack_has_capabilities(self):
        """DomainPack must have capabilities list"""
        from synapse.ecosystem.domain_packs import DomainPack
        pack = DomainPack(
            name="test_pack",
            version="1.0.0",
            description="Test domain pack",
            capabilities=["fs:read", "net:http"]
        )
        assert pack.capabilities == ["fs:read", "net:http"]
    
    def test_domain_pack_has_protocol_version(self):
        """DomainPack must have protocol_version"""
        from synapse.ecosystem.domain_packs import DomainPack
        pack = DomainPack(
            name="test_pack",
            version="1.0.0",
            description="Test domain pack"
        )
        assert pack.protocol_version == "1.0"
    
    def test_domain_pack_validate_method(self):
        """DomainPack must have validate method"""
        from synapse.ecosystem.domain_packs import DomainPack
        pack = DomainPack(
            name="test_pack",
            version="1.0.0",
            description="Test domain pack"
        )
        assert hasattr(pack, 'validate')
        assert callable(pack.validate)


class TestCapabilityMarketplace:
    """Tests for Capability Marketplace component"""
    
    def test_marketplace_exists(self):
        """CapabilityMarketplace class must exist"""
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        assert CapabilityMarketplace is not None
    
    def test_marketplace_register_capability(self):
        """Marketplace must have register_capability method"""
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        marketplace = CapabilityMarketplace()
        assert hasattr(marketplace, 'register_capability')
    
    def test_marketplace_list_capabilities(self):
        """Marketplace must have list_capabilities method"""
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        marketplace = CapabilityMarketplace()
        assert hasattr(marketplace, 'list_capabilities')
    
    def test_marketplace_get_capability(self):
        """Marketplace must have get_capability method"""
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        marketplace = CapabilityMarketplace()
        assert hasattr(marketplace, 'get_capability')
    
    def test_marketplace_resolve_dependencies(self):
        """Marketplace must have resolve_dependencies method"""
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        marketplace = CapabilityMarketplace()
        assert hasattr(marketplace, 'resolve_dependencies')
    
    def test_marketplace_has_protocol_version(self):
        """Marketplace must have protocol_version"""
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        marketplace = CapabilityMarketplace()
        assert marketplace.protocol_version == "1.0"


class TestExternalAPIGateway:
    """Tests for External API Gateway component"""
    
    def test_api_gateway_exists(self):
        """ExternalAPIGateway class must exist"""
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        assert ExternalAPIGateway is not None
    
    def test_api_gateway_has_rest_handler(self):
        """Gateway must have REST handler"""
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        gateway = ExternalAPIGateway()
        assert hasattr(gateway, 'rest_handler')
    
    def test_api_gateway_has_graphql_handler(self):
        """Gateway must have GraphQL handler"""
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        gateway = ExternalAPIGateway()
        assert hasattr(gateway, 'graphql_handler')
    
    def test_api_gateway_has_websocket_handler(self):
        """Gateway must have WebSocket handler"""
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        gateway = ExternalAPIGateway()
        assert hasattr(gateway, 'websocket_handler')
    
    def test_api_gateway_authenticate(self):
        """Gateway must have authenticate method"""
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        gateway = ExternalAPIGateway()
        assert hasattr(gateway, 'authenticate')
    
    def test_api_gateway_has_protocol_version(self):
        """Gateway must have protocol_version"""
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        gateway = ExternalAPIGateway()
        assert gateway.protocol_version == "1.0"


class TestEcosystemIntegration:
    """Integration tests for Ecosystem Layer"""
    
    def test_domain_pack_registration_in_marketplace(self):
        """Domain packs can be registered in marketplace"""
        from synapse.ecosystem.domain_packs import DomainPack
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        
        pack = DomainPack(
            name="analytics_pack",
            version="1.0.0",
            description="Analytics domain pack",
            capabilities=["analytics:read", "analytics:write"]
        )
        
        marketplace = CapabilityMarketplace()
        result = marketplace.register_capability(pack)
        assert result is not None
    
    def test_api_gateway_uses_marketplace(self):
        """API Gateway integrates with marketplace"""
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        
        marketplace = CapabilityMarketplace()
        gateway = ExternalAPIGateway(marketplace=marketplace)
        assert gateway.marketplace is not None


class TestProtocolCompliance:
    """Protocol version compliance tests"""
    
    def test_all_components_have_protocol_version(self):
        """All ecosystem components must have protocol_version"""
        from synapse.ecosystem.domain_packs import DomainPack
        from synapse.ecosystem.capability_marketplace import CapabilityMarketplace
        from synapse.ecosystem.api_gateway import ExternalAPIGateway
        
        pack = DomainPack(name="test", version="1.0", description="test")
        marketplace = CapabilityMarketplace()
        gateway = ExternalAPIGateway()
        
        assert pack.protocol_version == "1.0"
        assert marketplace.protocol_version == "1.0"
        assert gateway.protocol_version == "1.0"
