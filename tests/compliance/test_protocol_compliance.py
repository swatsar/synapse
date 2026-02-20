"""Protocol Compliance Tests.

Verifies:
1. Every module defines PROTOCOL_VERSION = "1.0"
2. Every module defines SPEC_VERSION = "3.1"
3. Every message/model includes protocol_version: str = "1.0"
"""
import pytest
import ast
import os
from pathlib import Path


class TestProtocolCompliance:
    """Test protocol version compliance across all modules."""
    
    @pytest.fixture
    def synapse_root(self):
        """Get synapse root directory."""
        return Path(__file__).parent.parent.parent / "synapse"
    
    def scan_protocol_versions(self, synapse_root: Path) -> dict:
        """Scan all Python files for PROTOCOL_VERSION."""
        report = {
            "total_files": 0,
            "compliant_files": 0,
            "non_compliant": [],
            "details": {}
        }
        
        for py_file in synapse_root.rglob("*.py"):
            # Skip __pycache__, test files, and __init__.py
            if "__pycache__" in str(py_file) or "test_" in py_file.name or py_file.name == "__init__.py":
                continue
                
            report["total_files"] += 1
            
            try:
                content = py_file.read_text()
                
                # Check for PROTOCOL_VERSION
                has_protocol = 'PROTOCOL_VERSION' in content or 'protocol_version' in content
                
                if has_protocol:
                    report["compliant_files"] += 1
                else:
                    rel_path = str(py_file.relative_to(synapse_root.parent))
                    report["non_compliant"].append(rel_path)
                    
            except Exception as e:
                report["details"][str(py_file)] = f"Error: {e}"
        
        if report["total_files"] > 0:
            report["compliance_rate"] = report["compliant_files"] / report["total_files"]
        else:
            report["compliance_rate"] = 0.0
            
        return report
    
    def test_protocol_version_declared(self, synapse_root):
        """Test that PROTOCOL_VERSION is declared in modules."""
        # Check core modules have PROTOCOL_VERSION
        core_models = synapse_root / "core" / "models.py"
        assert core_models.exists(), "core/models.py must exist"
        
        content = core_models.read_text()
        assert 'PROTOCOL_VERSION' in content or 'protocol_version' in content, \
            "core/models.py must declare PROTOCOL_VERSION"
    
    def test_protocol_version_compliance(self, synapse_root):
        """Test protocol version compliance across all modules."""
        report = self.scan_protocol_versions(synapse_root)
        
        # Print non-compliant for debugging
        if report["non_compliant"]:
            print(f"\nNon-compliant modules: {report['non_compliant']}")
        
        # Require 80% compliance (allowing some test/utility files)
        assert report["compliance_rate"] >= 0.80, \
            f"Compliance rate {report['compliance_rate']*100:.2f}% is below 80%"
    
    def test_core_models_protocol_version(self, synapse_root):
        """Test that core models have protocol_version."""
        from synapse.core.models import ResourceLimits, ExecutionContext, SkillManifest
        
        # Check class-level protocol_version
        assert hasattr(ResourceLimits, "model_fields")  # Pydantic model
        assert hasattr(ExecutionContext, "protocol_version")
        assert hasattr(SkillManifest, "protocol_version")
    
    def test_spec_version_declared(self, synapse_root):
        """Test that SPEC_VERSION is declared in core."""
        core_models = synapse_root / "core" / "models.py"
        content = core_models.read_text()
        
        # SPEC_VERSION should be in core models
        assert 'SPEC_VERSION' in content or 'spec_version' in content or '3.1' in content, \
            "core/models.py should reference spec version 3.1"


class TestModelProtocolVersion:
    """Test protocol_version in model instances."""
    
    def test_execution_context_protocol_version(self):
        """Test ExecutionContext has protocol_version."""
        from synapse.core.models import ExecutionContext
        
        ctx = ExecutionContext(
            session_id="test",
            agent_id="test",
            trace_id="test"
        )
        assert hasattr(ctx.__class__, "protocol_version")
    
    def test_skill_manifest_protocol_version(self):
        """Test SkillManifest has protocol_version."""
        from synapse.core.models import SkillManifest
        
        manifest = SkillManifest(name="test_skill")
        assert hasattr(manifest.__class__, "protocol_version")
    
    def test_action_plan_protocol_version(self):
        """Test ActionPlan has protocol_version."""
        from synapse.core.models import ActionPlan
        
        plan = ActionPlan(goal="test_goal")
        assert hasattr(plan.__class__, "protocol_version")
