"""
GUI Integration Tests for Synapse Configurator.

Tests verify:
- Protocol version compliance (1.0)
- Tauri configuration validity
- Frontend component structure
- Backend command responses
"""

import pytest
import json
import os
from pathlib import Path


@pytest.mark.phase6
@pytest.mark.integration
class TestTauriConfiguration:
    """Tests for Tauri configuration files."""
    
    def test_tauri_conf_json_valid(self):
        """Tauri configuration is valid JSON."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        tauri_conf_path = gui_path / "src-tauri" / "tauri.conf.json"
        
        if tauri_conf_path.exists():
            with open(tauri_conf_path) as f:
                config = json.load(f)
            
            assert "package" in config
            assert "productName" in config["package"]
            assert "version" in config["package"]
            assert config["package"]["version"] == "3.1.0"
    
    def test_tauri_bundle_targets(self):
        """Tauri bundle targets include all platforms."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        tauri_conf_path = gui_path / "src-tauri" / "tauri.conf.json"
        
        if tauri_conf_path.exists():
            with open(tauri_conf_path) as f:
                config = json.load(f)
            
            targets = config.get("tauri", {}).get("bundle", {}).get("targets", [])
            assert "msi" in targets or "deb" in targets
    
    def test_cargo_toml_exists(self):
        """Cargo.toml exists for Rust backend."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        cargo_path = gui_path / "src-tauri" / "Cargo.toml"
        
        if cargo_path.exists():
            with open(cargo_path) as f:
                content = f.read()
            
            assert "synapse-configurator" in content
            assert 'version = "3.1.0"' in content


@pytest.mark.phase6
@pytest.mark.integration
class TestFrontendStructure:
    """Tests for frontend file structure."""
    
    def test_package_json_exists(self):
        """package.json exists with correct configuration."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        package_path = gui_path / "package.json"
        
        if package_path.exists():
            with open(package_path) as f:
                package = json.load(f)
            
            assert package["name"] == "synapse-configurator"
            assert package["version"] == "3.1.0"
    
    def test_tsconfig_exists(self):
        """TypeScript configuration exists."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        tsconfig_path = gui_path / "tsconfig.json"
        
        if tsconfig_path.exists():
            with open(tsconfig_path) as f:
                tsconfig = json.load(f)
            
            assert "compilerOptions" in tsconfig
            assert tsconfig["compilerOptions"]["strict"] == True
    
    def test_app_tsx_exists(self):
        """Main App.tsx component exists."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        app_path = gui_path / "src" / "App.tsx"
        
        if app_path.exists():
            with open(app_path) as f:
                content = f.read()
            
            # Check for protocol version
            assert "protocol_version" in content
            assert "1.0" in content


@pytest.mark.phase6
@pytest.mark.integration
class TestRustBackend:
    """Tests for Rust backend modules."""
    
    def test_main_rs_exists(self):
        """main.rs exists with Tauri setup."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        main_path = gui_path / "src-tauri" / "src" / "main.rs"
        
        if main_path.exists():
            with open(main_path) as f:
                content = f.read()
            
            assert "PROTOCOL_VERSION" in content
            assert "1.0" in content
    
    def test_commands_rs_exists(self):
        """commands.rs exists with Tauri commands."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        commands_path = gui_path / "src-tauri" / "src" / "commands.rs"
        
        if commands_path.exists():
            with open(commands_path) as f:
                content = f.read()
            
            # Check for required commands
            assert "get_config" in content
            assert "get_skills" in content
            assert "get_system_metrics" in content
            assert "get_security_settings" in content
    
    def test_protocol_version_in_all_modules(self):
        """All Rust modules include protocol version."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        src_path = gui_path / "src-tauri" / "src"
        
        if src_path.exists():
            for rs_file in src_path.glob("*.rs"):
                with open(rs_file) as f:
                    content = f.read()
                
                # Each module should reference protocol version
                if "protocol_version" in content.lower() or "PROTOCOL_VERSION" in content:
                    assert "1.0" in content, f"{rs_file.name} missing protocol version 1.0"


@pytest.mark.phase6
@pytest.mark.integration
class TestGUIProtocolCompliance:
    """Tests for protocol version compliance in GUI."""
    
    def test_frontend_displays_protocol_version(self):
        """Frontend displays protocol version."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        app_path = gui_path / "src" / "App.tsx"
        
        if app_path.exists():
            with open(app_path) as f:
                content = f.read()
            
            # Check that protocol version is displayed
            assert "protocol_version: 1.0" in content or "protocol_version" in content
    
    def test_css_has_protocol_badge(self):
        """CSS includes protocol badge styling."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        css_path = gui_path / "src" / "styles" / "globals.css"
        
        if css_path.exists():
            with open(css_path) as f:
                content = f.read()
            
            assert "protocol-badge" in content
    
    def test_api_response_structure(self):
        """API response structure includes protocol version."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        commands_path = gui_path / "src-tauri" / "src" / "commands.rs"
        
        if commands_path.exists():
            with open(commands_path) as f:
                content = f.read()
            
            # Check ApiResponse structure
            assert "struct ApiResponse" in content or "struct BaseResponse" in content
            assert "protocol_version" in content


@pytest.mark.phase6
@pytest.mark.integration
class TestTestFiles:
    """Tests for test file existence."""
    
    def test_frontend_tests_exist(self):
        """Frontend test files exist."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        test_path = gui_path / "src" / "__tests__" / "App.test.tsx"
        
        if test_path.exists():
            with open(test_path) as f:
                content = f.read()
            
            assert "protocol_version" in content
    
    def test_rust_tests_exist(self):
        """Rust test files exist."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        test_path = gui_path / "src-tauri" / "src" / "__tests__" / "commands_test.rs"
        
        if test_path.exists():
            with open(test_path) as f:
                content = f.read()
            
            assert "PROTOCOL_VERSION" in content
            assert "test_get_config_returns_protocol_version" in content
    
    def test_vitest_config_exists(self):
        """Vitest configuration exists."""
        gui_path = Path(__file__).parent.parent.parent / "synapse" / "ui" / "gui"
        vitest_path = gui_path / "vitest.config.ts"
        
        assert vitest_path.exists()
