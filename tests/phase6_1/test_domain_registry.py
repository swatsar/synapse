"""
Tests for Domain Capability Registry
"""

import pytest
import hashlib
import json
from datetime import datetime

from synapse.capability.domain_registry import (
    CapabilityStatus,
    DependencyType,
    CapabilityDescriptor,
    DomainRegistry
)


class TestCapabilityDescriptorSpecification:
    """Specification tests for CapabilityDescriptor"""

    def test_descriptor_exists(self):
        """Descriptor must exist"""
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test_domain",
            description="Test capability",
            permissions=["read", "write"]
        )

        assert descriptor is not None
        assert descriptor.protocol_version == "1.0"

    def test_versioned_capabilities(self):
        """Capabilities must be versioned"""
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="2.1.0",
            domain="test_domain",
            description="Test capability",
            permissions=[]
        )

        assert descriptor.version == "2.1.0"

    def test_domain_scoped(self):
        """Capabilities must be domain-scoped"""
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="filesystem",
            description="Filesystem capability",
            permissions=[]
        )

        assert descriptor.domain == "filesystem"

    def test_dependency_graph(self):
        """Descriptor must support dependency graph"""
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[],
            dependencies={
                "cap_base": DependencyType.REQUIRED,
                "cap_optional": DependencyType.OPTIONAL,
                "cap_conflict": DependencyType.CONFLICT
            }
        )

        assert "cap_base" in descriptor.dependencies
        assert descriptor.dependencies["cap_base"] == DependencyType.REQUIRED

    def test_deterministic_resolution(self):
        """Capability ID must be deterministic"""
        descriptor1 = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )

        descriptor2 = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )

        assert descriptor1.capability_id == descriptor2.capability_id

    def test_policy_validation(self):
        """Descriptor must support policy validation"""
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[],
            policies={"max_requests": 100, "timeout": 30}
        )

        assert "max_requests" in descriptor.policies
        assert descriptor.policies["max_requests"] == 100

    def test_descriptor_validation(self):
        """Descriptor must validate"""
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )

        assert descriptor.validate() == True

    def test_descriptor_hash_verification(self):
        """Descriptor hash must be verifiable"""
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=["read"]
        )

        # Hash must be SHA256
        assert len(descriptor.descriptor_hash) == 64


class TestDomainRegistrySpecification:
    """Specification tests for DomainRegistry"""

    def test_registry_exists(self):
        """Registry must exist"""
        registry = DomainRegistry()
        assert registry is not None
        assert registry.PROTOCOL_VERSION == "1.0"

    def test_register_capability(self):
        """Registry must register capabilities"""
        registry = DomainRegistry()
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )

        result = registry.register(descriptor)

        assert result == True
        assert descriptor.capability_id in registry.list_capabilities()

    def test_read_only_at_runtime(self):
        """Registry must be read-only at runtime"""
        registry = DomainRegistry()

        # Register and seal
        descriptor = CapabilityDescriptor.create(
            name="test_capability",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )
        registry.register(descriptor)
        registry.seal()

        # Try to register after sealing
        descriptor2 = CapabilityDescriptor.create(
            name="test_capability2",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )

        with pytest.raises(RuntimeError):
            registry.register(descriptor2)

    def test_get_capabilities_by_domain(self):
        """Registry must return capabilities by domain"""
        registry = DomainRegistry()

        # Register capabilities in different domains
        for i in range(3):
            descriptor = CapabilityDescriptor.create(
                name=f"cap_{i}",
                version="1.0.0",
                domain="domain_a",
                description="Test",
                permissions=[]
            )
            registry.register(descriptor)

        for i in range(2):
            descriptor = CapabilityDescriptor.create(
                name=f"cap_b_{i}",
                version="1.0.0",
                domain="domain_b",
                description="Test",
                permissions=[]
            )
            registry.register(descriptor)

        # Get by domain
        caps_a = registry.get_capabilities_by_domain("domain_a")
        caps_b = registry.get_capabilities_by_domain("domain_b")

        assert len(caps_a) == 3
        assert len(caps_b) == 2

    def test_resolve_capabilities(self):
        """Registry must resolve capabilities deterministically"""
        registry = DomainRegistry()

        # Register base capability
        base = CapabilityDescriptor.create(
            name="base",
            version="1.0.0",
            domain="test",
            description="Base",
            permissions=[]
        )
        registry.register(base)

        # Register dependent capability
        dependent = CapabilityDescriptor.create(
            name="dependent",
            version="1.0.0",
            domain="test",
            description="Dependent",
            permissions=[],
            dependencies={base.capability_id: DependencyType.REQUIRED}
        )
        registry.register(dependent)

        # Resolve
        resolved = registry.resolve_capabilities([dependent.capability_id])

        # Should include both dependent and base
        assert len(resolved) == 2
        capability_ids = [c.capability_id for c in resolved]
        assert base.capability_id in capability_ids
        assert dependent.capability_id in capability_ids

    def test_validate_policy(self):
        """Registry must validate policies"""
        registry = DomainRegistry()

        descriptor = CapabilityDescriptor.create(
            name="test",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[],
            policies={"max_requests": 100}
        )
        registry.register(descriptor)

        # Valid policy
        assert registry.validate_policy(
            descriptor.capability_id,
            "max_requests",
            100
        ) == True

        # Invalid policy
        assert registry.validate_policy(
            descriptor.capability_id,
            "max_requests",
            200
        ) == False

    def test_check_compatibility(self):
        """Registry must check capability compatibility"""
        registry = DomainRegistry()

        # Create conflicting capabilities
        cap1 = CapabilityDescriptor.create(
            name="cap1",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )
        registry.register(cap1)

        cap2 = CapabilityDescriptor.create(
            name="cap2",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[],
            dependencies={cap1.capability_id: DependencyType.CONFLICT}
        )
        registry.register(cap2)

        # Check compatibility
        assert registry.check_compatibility([
            cap1.capability_id,
            cap2.capability_id
        ]) == False

    def test_list_domains(self):
        """Registry must list domains"""
        registry = DomainRegistry()

        for domain in ["domain_a", "domain_b", "domain_c"]:
            descriptor = CapabilityDescriptor.create(
                name=f"cap_{domain}",
                version="1.0.0",
                domain=domain,
                description="Test",
                permissions=[]
            )
            registry.register(descriptor)

        domains = registry.list_domains()

        assert len(domains) == 3
        assert "domain_a" in domains
        assert "domain_b" in domains
        assert "domain_c" in domains

    def test_dependency_graph(self):
        """Registry must provide dependency graph"""
        registry = DomainRegistry()

        base = CapabilityDescriptor.create(
            name="base",
            version="1.0.0",
            domain="test",
            description="Base",
            permissions=[]
        )
        registry.register(base)

        dependent = CapabilityDescriptor.create(
            name="dependent",
            version="1.0.0",
            domain="test",
            description="Dependent",
            permissions=[],
            dependencies={base.capability_id: DependencyType.REQUIRED}
        )
        registry.register(dependent)

        graph = registry.get_dependency_graph()

        assert dependent.capability_id in graph
        assert base.capability_id in graph[dependent.capability_id]


class TestDomainRegistrySecurity:
    """Security tests for DomainRegistry"""

    def test_missing_dependency_fails(self):
        """Missing required dependency must fail"""
        registry = DomainRegistry()

        descriptor = CapabilityDescriptor.create(
            name="dependent",
            version="1.0.0",
            domain="test",
            description="Dependent",
            permissions=[],
            dependencies={"nonexistent": DependencyType.REQUIRED}
        )

        with pytest.raises(ValueError):
            registry.register(descriptor)

    def test_revoked_capability_fails(self):
        """Revoked capability must fail validation"""
        descriptor = CapabilityDescriptor.create(
            name="test",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )

        # Manually set status to revoked
        descriptor.status = CapabilityStatus.REVOKED

        assert descriptor.validate() == False

    def test_duplicate_registration_fails(self):
        """Duplicate registration must fail"""
        registry = DomainRegistry()

        descriptor = CapabilityDescriptor.create(
            name="test",
            version="1.0.0",
            domain="test",
            description="Test",
            permissions=[]
        )

        registry.register(descriptor)

        with pytest.raises(ValueError):
            registry.register(descriptor)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
