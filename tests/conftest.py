import os, sys
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

# Add the project root (parent of the tests directory) to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# ============================================================================
# Core Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def test_context():
    """Create a test execution context."""
    from synapse.core.models import ExecutionContext, ResourceLimits
    
    return ExecutionContext(
        session_id="test_session",
        agent_id="test_agent",
        trace_id="test_trace",
        capabilities=["fs:read:/workspace/**", "fs:write:/workspace/**"],
        memory_store=MagicMock(),
        logger=MagicMock(),
        resource_limits=ResourceLimits(
            cpu_seconds=60,
            memory_mb=512,
            disk_mb=100,
            network_kb=1024
        ),
        execution_seed=42,
        protocol_version="1.0"
    )


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = AsyncMock()
    provider.generate.return_value = "test response"
    provider.is_active = True
    provider.priority = 1
    return provider


@pytest.fixture
def mock_network():
    """Create a mock network for distributed tests."""
    network = AsyncMock()
    network.send = AsyncMock(return_value={"success": True})
    network.receive = AsyncMock(return_value={"data": "test"})
    return network


@pytest.fixture
def frozen_time():
    """Freeze time for deterministic tests."""
    from freezegun import freeze_time
    with freeze_time("2026-02-19 12:00:00"):
        yield


@pytest.fixture(autouse=True)
def set_deterministic_seed():
    """Ensure test reproducibility with deterministic seeds."""
    import random
    random.seed(42)
    yield
    random.seed()


# ============================================================================
# Security Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def capability_manager():
    """Create a capability manager for testing."""
    from synapse.security.capability_manager import CapabilityManager
    return CapabilityManager()


@pytest_asyncio.fixture
async def execution_guard():
    """Create an execution guard for testing."""
    from synapse.security.execution_guard import ExecutionGuard
    return ExecutionGuard()


# ============================================================================
# Memory Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def memory_store():
    """Create a memory store for testing."""
    from synapse.memory.store import MemoryStore
    store = MemoryStore()
    return store


# ============================================================================
# Distributed Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def coordination_service(capability_manager):
    """Create a coordination service for testing."""
    from synapse.distributed.coordination.service import ClusterCoordinationService
    return ClusterCoordinationService(caps=capability_manager)


@pytest_asyncio.fixture
async def consensus_engine(capability_manager):
    """Create a consensus engine for testing."""
    from synapse.distributed.consensus.engine import ConsensusEngine
    return ConsensusEngine(caps=capability_manager)


@pytest_asyncio.fixture
async def replication_manager():
    """Create a replication manager for testing."""
    from synapse.distributed.replication.manager import ReplicationManager
    return ReplicationManager()


# ============================================================================
# Checkpoint Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def checkpoint_manager():
    """Create a checkpoint manager for testing."""
    from synapse.core.checkpoint import CheckpointManager
    return CheckpointManager()


@pytest_asyncio.fixture
async def rollback_manager(checkpoint_manager, capability_manager):
    """Create a rollback manager for testing."""
    from synapse.core.rollback import RollbackManager
    from synapse.core.audit import AuditLogger
    
    audit = AuditLogger()
    return RollbackManager(
        cp_manager=checkpoint_manager,
        cap_manager=capability_manager,
        audit=audit
    )
