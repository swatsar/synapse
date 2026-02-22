"""
Tests for Tenant Audit Chain
"""

import pytest
import hashlib
import json
from datetime import datetime

from synapse.audit.tenant_audit_chain import (
    TenantAuditChain,
    AuditHashTree,
    AuditEntry
)


class TestTenantAuditChainSpecification:
    """Specification tests for TenantAuditChain"""

    def test_audit_chain_exists(self):
        """Audit chain must exist"""
        chain = TenantAuditChain()
        assert chain is not None
        assert chain.PROTOCOL_VERSION == "1.0"

    def test_append_creates_entry(self):
        """Appending must create audit entry"""
        chain = TenantAuditChain()
        entry = chain.append(
            tenant_id="tenant_1",
            event_type="test_event",
            event_data={"key": "value"}
        )

        assert entry is not None
        assert entry.tenant_id == "tenant_1"
        assert entry.event_type == "test_event"
        assert entry.protocol_version == "1.0"

    def test_append_only(self):
        """Chain must be append-only"""
        chain = TenantAuditChain()

        # Append entry
        entry1 = chain.append(
            tenant_id="tenant_1",
            event_type="event_1",
            event_data={}
        )

        # Get chain
        entries = chain.get_chain("tenant_1")
        assert len(entries) == 1

        # Append another
        entry2 = chain.append(
            tenant_id="tenant_1",
            event_type="event_2",
            event_data={}
        )

        entries = chain.get_chain("tenant_1")
        assert len(entries) == 2
        assert entries[0].entry_id == entry1.entry_id
        assert entries[1].entry_id == entry2.entry_id

    def test_cryptographically_linked(self):
        """Entries must be cryptographically linked"""
        chain = TenantAuditChain()

        entry1 = chain.append(
            tenant_id="tenant_1",
            event_type="event_1",
            event_data={}
        )

        entry2 = chain.append(
            tenant_id="tenant_1",
            event_type="event_2",
            event_data={}
        )

        # Entry 2 must link to Entry 1
        assert entry2.previous_hash == entry1.entry_hash
        assert entry1.entry_hash != ""
        assert entry2.entry_hash != ""

    def test_tenant_scoped(self):
        """Audit must be tenant-scoped"""
        chain = TenantAuditChain()

        # Add entries for different tenants
        entry1 = chain.append(
            tenant_id="tenant_1",
            event_type="event",
            event_data={"data": "tenant1"}
        )

        entry2 = chain.append(
            tenant_id="tenant_2",
            event_type="event",
            event_data={"data": "tenant2"}
        )

        # Get chains
        chain1 = chain.get_chain("tenant_1")
        chain2 = chain.get_chain("tenant_2")

        assert len(chain1) == 1
        assert len(chain2) == 1
        assert chain1[0].event_data["data"] == "tenant1"
        assert chain2[0].event_data["data"] == "tenant2"

    def test_verify_chain(self):
        """Chain verification must work"""
        chain = TenantAuditChain()

        # Add entries
        for i in range(5):
            chain.append(
                tenant_id="tenant_1",
                event_type=f"event_{i}",
                event_data={"index": i}
            )

        # Verify
        assert chain.verify_chain("tenant_1") == True

    def test_replay_verifiable(self):
        """Chain must be replay-verifiable"""
        chain = TenantAuditChain()

        # Add entries
        entries = []
        for i in range(3):
            entry = chain.append(
                tenant_id="tenant_1",
                event_type=f"event_{i}",
                event_data={"index": i}
            )
            entries.append(entry)

        # Verify each entry hash
        for entry in entries:
            # Recalculate hash
            data = {
                "entry_id": entry.entry_id,
                "tenant_id": entry.tenant_id,
                "event_type": entry.event_type,
                "event_data": entry.event_data,
                "timestamp": entry.timestamp,
                "previous_hash": entry.previous_hash,
                "protocol_version": entry.protocol_version
            }
            expected_hash = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()

            assert entry.entry_hash == expected_hash

    def test_cross_tenant_contamination_impossible(self):
        """Cross-tenant contamination must be impossible"""
        chain = TenantAuditChain()

        # Add entries for tenant 1
        chain.append(
            tenant_id="tenant_1",
            event_type="event",
            event_data={"secret": "tenant1_secret"}
        )

        # Add entries for tenant 2
        chain.append(
            tenant_id="tenant_2",
            event_type="event",
            event_data={"secret": "tenant2_secret"}
        )

        # Verify tenant 1 chain doesn't contain tenant 2 data
        chain1 = chain.get_chain("tenant_1")
        for entry in chain1:
            assert entry.tenant_id == "tenant_1"
            assert "tenant2" not in str(entry.event_data)

        # Verify tenant 2 chain doesn't contain tenant 1 data
        chain2 = chain.get_chain("tenant_2")
        for entry in chain2:
            assert entry.tenant_id == "tenant_2"
            assert "tenant1" not in str(entry.event_data)


class TestAuditHashTreeSpecification:
    """Specification tests for AuditHashTree"""

    def test_hash_tree_exists(self):
        """Hash tree must exist"""
        tree = AuditHashTree()
        assert tree is not None
        assert tree.PROTOCOL_VERSION == "1.0"

    def test_merkle_structure(self):
        """Tree must have Merkle structure"""
        tree = AuditHashTree()
        chain = TenantAuditChain()

        # Add tenant leaves
        chain.append("tenant_1", "event", {})
        leaf1 = tree.add_tenant_leaf("cluster_1", "tenant_1", chain)

        chain.append("tenant_2", "event", {})
        leaf2 = tree.add_tenant_leaf("cluster_1", "tenant_2", chain)

        # Get root
        root = tree.get_root("cluster_1")

        assert root is not None
        assert root != ""

    def test_cluster_wide_audit_root(self):
        """Tree must provide cluster-wide audit root"""
        tree = AuditHashTree()
        chain = TenantAuditChain()

        # Add multiple tenants
        for i in range(3):
            tenant_id = f"tenant_{i}"
            chain.append(tenant_id, "event", {})
            tree.add_tenant_leaf("cluster_1", tenant_id, chain)

        root = tree.get_root("cluster_1")

        # Root must be deterministic
        root2 = tree.get_root("cluster_1")
        assert root == root2

    def test_deterministic_hash_generation(self):
        """Hash generation must be deterministic"""
        tree1 = AuditHashTree()
        tree2 = AuditHashTree()
        chain1 = TenantAuditChain()
        chain2 = TenantAuditChain()

        # Add same data to both
        chain1.append("tenant_1", "event", {"key": "value"})
        chain2.append("tenant_1", "event", {"key": "value"})

        tree1.add_tenant_leaf("cluster_1", "tenant_1", chain1)
        tree2.add_tenant_leaf("cluster_1", "tenant_1", chain2)

        # Roots must be identical
        assert tree1.get_root("cluster_1") == tree2.get_root("cluster_1")

    def test_verify_leaf(self):
        """Leaf verification must work"""
        tree = AuditHashTree()
        chain = TenantAuditChain()

        chain.append("tenant_1", "event", {})
        leaf_hash = tree.add_tenant_leaf("cluster_1", "tenant_1", chain)

        assert tree.verify_leaf("cluster_1", "tenant_1", leaf_hash) == True
        assert tree.verify_leaf("cluster_1", "tenant_2", leaf_hash) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
