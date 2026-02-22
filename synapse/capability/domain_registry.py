"""
Domain Capability Registry for Multi-Tenant Runtime
Preparation layer for Phase 7 capability marketplace

PROTOCOL_VERSION = "1.0"
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import threading


class CapabilityStatus(str, Enum):
    """Status of capability"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


class DependencyType(str, Enum):
    """Type of dependency"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONFLICT = "conflict"


@dataclass
class CapabilityDescriptor:
    """
    Descriptor for a capability.

    Requirements:
    - Versioned capabilities
    - Domain-scoped capability sets
    - Dependency graph
    - Deterministic resolution
    - Policy validation
    """
    capability_id: str
    name: str
    version: str
    domain: str
    description: str
    permissions: List[str]
    dependencies: Dict[str, DependencyType]
    policies: Dict[str, Any]
    status: CapabilityStatus
    created_at: str
    updated_at: str
    descriptor_hash: str
    protocol_version: str = "1.0"

    @classmethod
    def create(
        cls,
        name: str,
        version: str,
        domain: str,
        description: str,
        permissions: List[str],
        dependencies: Optional[Dict[str, DependencyType]] = None,
        policies: Optional[Dict[str, Any]] = None
    ) -> "CapabilityDescriptor":
        """Create new capability descriptor"""
        capability_id = cls._generate_id(name, version, domain)

        now = datetime.utcnow().isoformat()

        descriptor = cls(
            capability_id=capability_id,
            name=name,
            version=version,
            domain=domain,
            description=description,
            permissions=sorted(permissions),
            dependencies=dependencies or {},
            policies=policies or {},
            status=CapabilityStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            descriptor_hash="",  # Will be calculated
            protocol_version="1.0"
        )

        descriptor.descriptor_hash = descriptor._calculate_hash()

        return descriptor

    def validate(self) -> bool:
        """Validate descriptor integrity"""
        # Verify hash
        expected_hash = self._calculate_hash()
        if self.descriptor_hash != expected_hash:
            return False

        # Verify required fields
        if not self.name or not self.version or not self.domain:
            return False

        # Verify status
        if self.status == CapabilityStatus.REVOKED:
            return False

        return True

    def check_dependency(
        self,
        other_capability: "CapabilityDescriptor"
    ) -> DependencyType:
        """Check dependency relationship with another capability"""
        return self.dependencies.get(other_capability.capability_id, DependencyType.OPTIONAL)

    def is_compatible_with(
        self,
        other_capabilities: List["CapabilityDescriptor"]
    ) -> bool:
        """Check if compatible with other capabilities"""
        for other in other_capabilities:
            dep_type = self.check_dependency(other)

            # Check conflicts
            if dep_type == DependencyType.CONFLICT:
                return False

            # Check required dependencies
            if dep_type == DependencyType.REQUIRED:
                if other.status != CapabilityStatus.ACTIVE:
                    return False

        return True

    def _calculate_hash(self) -> str:
        """Calculate descriptor hash"""
        data = {
            "capability_id": self.capability_id,
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "permissions": self.permissions,
            "dependencies": {k: v.value for k, v in self.dependencies.items()},
            "policies": self.policies,
            "status": self.status.value,
            "protocol_version": self.protocol_version
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    @classmethod
    def _generate_id(cls, name: str, version: str, domain: str) -> str:
        """Generate deterministic capability ID"""
        data = f"{domain}:{name}:{version}:1.0"
        hash_part = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"cap_{hash_part}"


class DomainRegistry:
    """
    Registry for domain-scoped capabilities.

    Requirements:
    - Versioned capabilities
    - Domain-scoped capability sets
    - Dependency graph
    - Deterministic resolution
    - Policy validation
    - Registry must be read-only at runtime
    """

    PROTOCOL_VERSION = "1.0"

    def __init__(self):
        self._capabilities: Dict[str, CapabilityDescriptor] = {}
        self._domains: Dict[str, Set[str]] = {}  # domain -> capability_ids
        self._dependency_graph: Dict[str, Set[str]] = {}  # capability_id -> dependency_ids
        self._lock = threading.Lock()
        self._sealed: bool = False

    def register(self, descriptor: CapabilityDescriptor) -> bool:
        """
        Register capability descriptor.

        Registry must be read-only at runtime.

        Args:
            descriptor: Capability descriptor to register

        Returns:
            True if successful

        Raises:
            RuntimeError: If registry is sealed
            ValueError: If descriptor invalid or conflict
        """
        with self._lock:
            if self._sealed:
                raise RuntimeError("Registry is sealed and read-only")

            # Validate descriptor
            if not descriptor.validate():
                raise ValueError(f"Invalid descriptor: {descriptor.capability_id}")

            # Check for existing version
            if descriptor.capability_id in self._capabilities:
                raise ValueError(f"Capability already registered: {descriptor.capability_id}")

            # Check dependencies exist
            for dep_id, dep_type in descriptor.dependencies.items():
                if dep_type == DependencyType.REQUIRED:
                    if dep_id not in self._capabilities:
                        raise ValueError(f"Missing required dependency: {dep_id}")

            # Register capability
            self._capabilities[descriptor.capability_id] = descriptor

            # Update domain index
            if descriptor.domain not in self._domains:
                self._domains[descriptor.domain] = set()
            self._domains[descriptor.domain].add(descriptor.capability_id)

            # Update dependency graph
            self._dependency_graph[descriptor.capability_id] = set(
                dep_id for dep_id, dep_type in descriptor.dependencies.items()
                if dep_type != DependencyType.CONFLICT
            )

            return True

    def seal(self) -> bool:
        """
        Seal registry to make it read-only.

        Returns:
            True if successful
        """
        with self._lock:
            self._sealed = True
            return True

    def is_sealed(self) -> bool:
        """Check if registry is sealed"""
        with self._lock:
            return self._sealed

    def get_capability(self, capability_id: str) -> Optional[CapabilityDescriptor]:
        """Get capability by ID"""
        with self._lock:
            return self._capabilities.get(capability_id)

    def get_capabilities_by_domain(self, domain: str) -> List[CapabilityDescriptor]:
        """Get all capabilities in a domain"""
        with self._lock:
            if domain not in self._domains:
                return []
            return [
                self._capabilities[cid]
                for cid in self._domains[domain]
                if cid in self._capabilities
            ]

    def resolve_capabilities(
        self,
        requested: List[str]
    ) -> List[CapabilityDescriptor]:
        """
        Deterministically resolve capability set.

        Args:
            requested: List of requested capability IDs

        Returns:
            Resolved capability descriptors in deterministic order

        Raises:
            ValueError: If resolution fails
        """
        with self._lock:
            resolved: Dict[str, CapabilityDescriptor] = {}

            # Sort for deterministic order
            sorted_requested = sorted(requested)

            for cap_id in sorted_requested:
                if cap_id not in self._capabilities:
                    raise ValueError(f"Capability not found: {cap_id}")

                descriptor = self._capabilities[cap_id]

                # Check status
                if descriptor.status != CapabilityStatus.ACTIVE:
                    raise ValueError(f"Capability not active: {cap_id}")

                # Resolve dependencies first
                deps = self._resolve_dependencies(cap_id, resolved)
                resolved.update(deps)

                # Add this capability
                resolved[cap_id] = descriptor

            # Return in deterministic order
            return [resolved[cid] for cid in sorted(resolved.keys())]

    def validate_policy(
        self,
        capability_id: str,
        policy_name: str,
        policy_value: Any
    ) -> bool:
        """
        Validate policy for capability.

        Args:
            capability_id: Capability ID
            policy_name: Policy name
            policy_value: Policy value

        Returns:
            True if policy is valid
        """
        with self._lock:
            if capability_id not in self._capabilities:
                return False

            descriptor = self._capabilities[capability_id]

            if policy_name not in descriptor.policies:
                return False

            # Check policy matches
            expected = descriptor.policies[policy_name]
            return policy_value == expected

    def check_compatibility(
        self,
        capability_ids: List[str]
    ) -> bool:
        """
        Check if capabilities are compatible.

        Args:
            capability_ids: List of capability IDs

        Returns:
            True if all capabilities are compatible
        """
        with self._lock:
            descriptors = [
                self._capabilities[cid]
                for cid in capability_ids
                if cid in self._capabilities
            ]

            for i, desc in enumerate(descriptors):
                others = descriptors[:i] + descriptors[i+1:]
                if not desc.is_compatible_with(others):
                    return False

            return True

    def list_domains(self) -> List[str]:
        """List all domains"""
        with self._lock:
            return sorted(self._domains.keys())

    def list_capabilities(self) -> List[str]:
        """List all capability IDs"""
        with self._lock:
            return sorted(self._capabilities.keys())

    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """Get dependency graph"""
        with self._lock:
            return {k: v.copy() for k, v in self._dependency_graph.items()}

    def _resolve_dependencies(
        self,
        capability_id: str,
        already_resolved: Dict[str, CapabilityDescriptor]
    ) -> Dict[str, CapabilityDescriptor]:
        """Recursively resolve dependencies"""
        resolved = {}

        if capability_id not in self._dependency_graph:
            return resolved

        for dep_id in self._dependency_graph[capability_id]:
            # Skip if already resolved
            if dep_id in already_resolved or dep_id in resolved:
                continue

            if dep_id not in self._capabilities:
                raise ValueError(f"Missing dependency: {dep_id}")

            dep_descriptor = self._capabilities[dep_id]

            if dep_descriptor.status != CapabilityStatus.ACTIVE:
                raise ValueError(f"Dependency not active: {dep_id}")

            # Recursively resolve transitive dependencies
            transitive = self._resolve_dependencies(dep_id, already_resolved)
            resolved.update(transitive)

            resolved[dep_id] = dep_descriptor

        return resolved


__all__ = [
    "CapabilityStatus",
    "DependencyType",
    "CapabilityDescriptor",
    "DomainRegistry"
]
