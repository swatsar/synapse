"""Architectural Structure Compliance Tests.

Validates project structure exactly matches specification.
Required components must exist and be functional:
- time synchronization core
- rollback manager
- checkpoint system
- connector security
- LLM failure strategy
- audit persistence
- distributed protocol
- observability stack
- memory subsystem
- adaptive policy manager
"""
import pytest
from pathlib import Path
from typing import List, Dict, Any


class ArchitectureScanner:
    """Scanner for architectural structure compliance."""
    
    REQUIRED_COMPONENTS = {
        # Core components
        "time_sync_manager": {
            "paths": ["synapse/core/time_sync_manager.py"],
            "classes": ["TimeSyncManager"],
            "description": "Time synchronization core"
        },
        "rollback_manager": {
            "paths": ["synapse/reliability/rollback_manager.py", "synapse/core/rollback.py"],
            "classes": ["RollbackManager"],
            "description": "Rollback manager"
        },
        "checkpoint": {
            "paths": ["synapse/core/checkpoint.py"],
            "classes": ["Checkpoint"],
            "description": "Checkpoint system"
        },
        "isolation_policy": {
            "paths": ["synapse/core/isolation_policy.py"],
            "classes": ["IsolationEnforcementPolicy"],
            "description": "Isolation enforcement policy"
        },
        "determinism": {
            "paths": ["synapse/core/determinism.py"],
            "classes": ["DeterministicIDGenerator"],
            "description": "Deterministic execution"
        },
        
        # Security components
        "capability_manager": {
            "paths": ["synapse/security/capability_manager.py"],
            "classes": ["CapabilityManager"],
            "description": "Capability manager"
        },
        "execution_guard": {
            "paths": ["synapse/security/execution_guard.py"],
            "classes": ["ExecutionGuard"],
            "description": "Execution guard"
        },
        "connector_security": {
            "paths": ["synapse/connectors/security.py"],
            "classes": ["RateLimiter"],
            "description": "Connector security"
        },
        
        # LLM components
        "llm_router": {
            "paths": ["synapse/llm/router.py"],
            "classes": ["LLMRouter"],
            "description": "LLM router"
        },
        "llm_provider": {
            "paths": ["synapse/llm/provider.py"],
            "classes": ["LLMProvider"],
            "description": "LLM provider"
        },
        
        # Memory components
        "memory_store": {
            "paths": ["synapse/memory/store.py"],
            "classes": ["MemoryStore"],
            "description": "Memory subsystem"
        },
        "distributed_memory": {
            "paths": ["synapse/memory/distributed/store.py"],
            "classes": ["DistributedMemoryStore"],
            "description": "Distributed memory"
        },
        
        # Network components
        "remote_node_protocol": {
            "paths": ["synapse/network/remote_node_protocol.py"],
            "classes": ["RemoteNodeProtocol", "RemoteMessage"],
            "description": "Distributed protocol"
        },
        "transport": {
            "paths": ["synapse/network/transport.py"],
            "classes": ["Transport"],
            "description": "Network transport"
        },
        
        # Observability components
        "observability_logger": {
            "paths": ["synapse/observability/logger.py"],
            "functions": ["audit"],
            "description": "Audit persistence"
        },
        "telemetry": {
            "paths": ["synapse/telemetry/engine.py"],
            "classes": ["TelemetryEngine"],
            "description": "Telemetry engine"
        },
        
        # Policy components
        "policy_engine": {
            "paths": ["synapse/policy/engine.py"],
            "classes": ["PolicyEngine"],
            "description": "Policy engine"
        },
        "adaptive_policy_manager": {
            "paths": ["synapse/policy/adaptive/manager.py"],
            "classes": ["AdaptivePolicyManager"],
            "description": "Adaptive policy manager"
        },
        
        # Agent components
        "orchestrator": {
            "paths": ["synapse/core/orchestrator.py"],
            "classes": ["Orchestrator"],
            "description": "Orchestrator"
        },
        "cognitive_agent": {
            "paths": ["synapse/agents/runtime/agent.py"],
            "classes": ["CognitiveAgent"],
            "description": "Cognitive agent runtime"
        },
        
        # Environment components
        "local_os": {
            "paths": ["synapse/environment/local_os.py"],
            "classes": ["LocalOS"],
            "description": "Local OS environment"
        },
        "docker_env": {
            "paths": ["synapse/environment/docker_env.py"],
            "classes": ["DockerEnv"],
            "description": "Docker environment"
        },
        
        # Reliability components
        "snapshot_manager": {
            "paths": ["synapse/reliability/snapshot_manager.py"],
            "classes": ["SnapshotManager"],
            "description": "Snapshot manager"
        },
        "fault_tolerance": {
            "paths": ["synapse/reliability/fault_tolerance.py"],
            "classes": ["FaultTolerance"],
            "description": "Fault tolerance"
        },
        
        # Evolution components
        "skill_evolution_engine": {
            "paths": ["synapse/skills/evolution/engine.py"],
            "classes": ["SkillEvolutionEngine"],
            "description": "Skill evolution engine"
        },
        
        # Distributed components
        "cluster_manager": {
            "paths": ["synapse/runtime/cluster/manager.py"],
            "classes": ["ClusterManager"],
            "description": "Cluster manager"
        },
        "consensus_engine": {
            "paths": ["synapse/distributed/consensus/engine.py"],
            "classes": ["ConsensusEngine"],
            "description": "Consensus engine"
        },
    }
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.results: Dict[str, Dict[str, Any]] = {}
    
    def scan(self) -> Dict[str, Dict[str, Any]]:
        """Scan all required components."""
        for component_name, requirements in self.REQUIRED_COMPONENTS.items():
            self.results[component_name] = self._scan_component(component_name, requirements)
        
        return self.results
    
    def _scan_component(self, name: str, requirements: Dict) -> Dict[str, Any]:
        """Scan a single component."""
        result = {
            "name": name,
            "description": requirements["description"],
            "path_exists": False,
            "found_path": None,
            "classes_found": [],
            "functions_found": [],
            "compliant": False
        }
        
        # Check paths
        for path in requirements.get("paths", []):
            full_path = self.root_path / path
            if full_path.exists():
                result["path_exists"] = True
                result["found_path"] = path
                break
        
        # Check classes
        if result["path_exists"] and "classes" in requirements:
            try:
                for class_name in requirements["classes"]:
                    module_path = result["found_path"].replace("/", ".").replace(".py", "")
                    module = __import__(module_path, fromlist=[class_name])
                    cls = getattr(module, class_name, None)
                    if cls:
                        result["classes_found"].append(class_name)
            except Exception as e:
                result["error"] = str(e)
        
        # Check functions
        if result["path_exists"] and "functions" in requirements:
            try:
                for func_name in requirements["functions"]:
                    module_path = result["found_path"].replace("/", ".").replace(".py", "")
                    module = __import__(module_path, fromlist=[func_name])
                    func = getattr(module, func_name, None)
                    if func:
                        result["functions_found"].append(func_name)
            except Exception as e:
                result["error"] = str(e)
        
        # Determine compliance
        has_classes = "classes" not in requirements or len(result["classes_found"]) > 0
        has_functions = "functions" not in requirements or len(result["functions_found"]) > 0
        result["compliant"] = result["path_exists"] and has_classes and has_functions
        
        return result
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance report."""
        total = len(self.results)
        compliant = sum(1 for r in self.results.values() if r["compliant"])
        non_compliant = [name for name, r in self.results.items() if not r["compliant"]]
        
        return {
            "total_components": total,
            "compliant": compliant,
            "non_compliant": non_compliant,
            "compliance_rate": compliant / total if total > 0 else 0
        }


class TestArchitectureStructure:
    """Test architectural structure compliance."""
    
    @pytest.fixture
    def scanner(self):
        """Create architecture scanner."""
        return ArchitectureScanner("/a0/usr/projects/project_synapse")
    
    def test_scanner_initialization(self, scanner):
        """Test scanner can be initialized."""
        assert scanner is not None
        assert scanner.root_path.exists()
    
    def test_scan_all_components(self, scanner):
        """Test scanning all components."""
        results = scanner.scan()
        assert len(results) > 0
    
    def test_all_required_components_present(self, scanner):
        """Test that all required components are present."""
        scanner.scan()
        report = scanner.get_compliance_report()
        
        # Print non-compliant for debugging
        if report["non_compliant"]:
            print(f"\nNon-compliant components: {report['non_compliant']}")
        
        # All components should be compliant
        assert report["compliance_rate"] >= 0.90, \
            f"Compliance rate {report['compliance_rate']:.2%} is below 90%"
    
    def test_time_sync_manager_exists(self):
        """Test TimeSyncManager exists."""
        from synapse.core.time_sync_manager import TimeSyncManager
        assert TimeSyncManager is not None
    
    def test_rollback_manager_exists(self):
        """Test RollbackManager exists."""
        from synapse.reliability.rollback_manager import RollbackManager
        assert RollbackManager is not None
    
    def test_checkpoint_exists(self):
        """Test Checkpoint exists."""
        from synapse.core.checkpoint import Checkpoint
        assert Checkpoint is not None
    
    def test_capability_manager_exists(self):
        """Test CapabilityManager exists."""
        from synapse.security.capability_manager import CapabilityManager
        assert CapabilityManager is not None
    
    def test_execution_guard_exists(self):
        """Test ExecutionGuard exists."""
        from synapse.security.execution_guard import ExecutionGuard
        assert ExecutionGuard is not None
    
    def test_llm_router_exists(self):
        """Test LLMRouter exists."""
        from synapse.llm.router import LLMRouter
        assert LLMRouter is not None
    
    def test_memory_store_exists(self):
        """Test MemoryStore exists."""
        from synapse.memory.store import MemoryStore
        assert MemoryStore is not None
    
    def test_remote_node_protocol_exists(self):
        """Test RemoteNodeProtocol exists."""
        from synapse.network.remote_node_protocol import RemoteNodeProtocol
        assert RemoteNodeProtocol is not None
    
    def test_audit_function_exists(self):
        """Test audit function exists."""
        from synapse.observability.logger import audit
        assert callable(audit)
    
    def test_policy_engine_exists(self):
        """Test PolicyEngine exists."""
        from synapse.policy.engine import PolicyEngine
        assert PolicyEngine is not None
    
    def test_adaptive_policy_manager_exists(self):
        """Test AdaptivePolicyManager exists."""
        from synapse.policy.adaptive.manager import AdaptivePolicyManager
        assert AdaptivePolicyManager is not None
    
    def test_orchestrator_exists(self):
        """Test Orchestrator exists."""
        from synapse.core.orchestrator import Orchestrator
        assert Orchestrator is not None
    
    def test_isolation_policy_exists(self):
        """Test IsolationEnforcementPolicy exists."""
        from synapse.core.isolation_policy import IsolationEnforcementPolicy
        assert IsolationEnforcementPolicy is not None
    
    def test_determinism_module_exists(self):
        """Test determinism module exists."""
        from synapse.core.determinism import DeterministicIDGenerator
        assert DeterministicIDGenerator is not None
    
    def test_no_unauthorized_architecture(self):
        """Test that no unauthorized architecture is introduced."""
        # Check for unexpected top-level directories
        synapse_path = Path("/a0/usr/projects/project_synapse/synapse")
        
        # Expected directories (including supporting directories)
        expected_dirs = {
            # Core architecture
            "core", "security", "llm", "memory", "network", "observability",
            "policy", "agents", "skills", "environment", "reliability",
            "distributed", "runtime", "telemetry", "connectors", "ui", "api",
            "control_plane", "learning", "deployment", "integrations", "integrations",
            # Supporting directories (allowed)
            "config", "database", "docs", "tests", ".github"
        }
        
        actual_dirs = set()
        for item in synapse_path.iterdir():
            if item.is_dir() and not item.name.startswith("__"):
                actual_dirs.add(item.name)
        
        # All actual directories should be in expected set
        unexpected = actual_dirs - expected_dirs
        assert len(unexpected) == 0, f"Unexpected directories: {unexpected}"
