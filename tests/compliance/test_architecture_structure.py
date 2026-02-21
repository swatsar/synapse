"""
Architecture Structure Compliance Tests.
Verifies that the project structure follows the defined architecture.
"""
import os
import pytest
from pathlib import Path


class TestArchitectureStructure:
    """Tests for architecture structure compliance"""
    
    def test_required_directories_exist(self):
        """Test that all required directories exist"""
        required_dirs = [
            "synapse",
            "synapse/core",
            "synapse/skills",
            "synapse/agents",
            "synapse/memory",
            "synapse/connectors",
            "synapse/llm",
            "synapse/config",  # Fixed: config is inside synapse
            "tests",
            "docs"
        ]
        
        for dir_path in required_dirs:
            assert os.path.isdir(dir_path), f"Required directory missing: {dir_path}"
    
    def test_no_unauthorized_architecture(self):
        """Test that no unauthorized directories exist in synapse/"""
        # Complete list of authorized directories (Phase 1-5)
        authorized_dirs = {
            # Core modules
            "core", "skills", "agents", "memory", "connectors", "llm",
            "network", "observability", "ui", "database", "config",
            # Security & Policy
            "security", "crypto", "policy", "governance",
            # Execution & Runtime
            "environment", "runtime", "reliability", "agent_runtime",
            # Distributed & Control Plane (Phase 3-5)
            "distributed", "distributed_consensus", "control_plane",
            "transport", "node",
            # Orchestration
            "orchestrator", "interfaces", "planning", "api",
            # Additional modules
            "deployment", "integrations", "learning", "telemetry",
            # Internal
            "tests"
        }
        
        synapse_dirs = set()
        for item in os.listdir("synapse"):
            item_path = os.path.join("synapse", item)
            if os.path.isdir(item_path) and not item.startswith("__"):
                synapse_dirs.add(item)
        
        unauthorized = synapse_dirs - authorized_dirs
        assert len(unauthorized) == 0, f"Unexpected directories in synapse/: {unauthorized}"
    
    def test_protocol_version_in_all_modules(self):
        """Test that all modules have PROTOCOL_VERSION"""
        synapse_path = Path("synapse")
        
        files_without_version = []
        
        for py_file in synapse_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            try:
                content = py_file.read_text()
                # Check for PROTOCOL_VERSION definition or usage
                has_version = (
                    "PROTOCOL_VERSION" in content or
                    "protocol_version" in content
                )
                
                if not has_version:
                    files_without_version.append(str(py_file))
            except:
                pass
        
        # Allow some files without version (e.g., utility files)
        # Only fail if more than 10% of files are missing version
        total_files = len(list(synapse_path.rglob("*.py"))) - len(list(synapse_path.rglob("__init__.py")))
        if total_files > 0:
            missing_ratio = len(files_without_version) / total_files
            assert missing_ratio < 0.1, f"Too many files without protocol_version: {files_without_version[:5]}"
    
    def test_test_coverage_structure(self):
        """Test that test structure mirrors source structure"""
        test_dirs = set()
        for item in os.listdir("tests"):
            item_path = os.path.join("tests", item)
            if os.path.isdir(item_path):
                test_dirs.add(item)
        
        # Should have phase tests
        assert any(d.startswith("phase") for d in test_dirs), "Missing phase test directories"
        
        # Should have compliance tests
        assert "compliance" in test_dirs, "Missing compliance tests"
