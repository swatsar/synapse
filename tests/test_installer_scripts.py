"""
Tests for Windows Installer Configuration.

Protocol Version: 1.0
Spec Version: 3.1
"""

import pytest
from pathlib import Path


@pytest.mark.phase6
@pytest.mark.unit
class TestWindowsInstaller:
    """Tests for Windows installer configuration."""

    def test_installer_windows_dir_exists(self):
        """Check installer/windows directory exists."""
        assert Path("installer/windows").exists()

    def test_nsis_script_exists(self):
        """Check NSIS script exists."""
        assert Path("installer/windows/synapse_installer.nsi").exists()

    def test_nsis_protocol_version(self):
        """Check protocol_version in NSIS script."""
        with open("installer/windows/synapse_installer.nsi", "r") as f:
            content = f.read()
        assert "PROTOCOL_VERSION" in content
        assert "1.0" in content

    def test_nsis_version(self):
        """Check version in NSIS script."""
        with open("installer/windows/synapse_installer.nsi", "r") as f:
            content = f.read()
        assert "SYNAPSE_VERSION" in content
        assert "3.1" in content

    def test_nsis_install_dir(self):
        """Check install directory in NSIS script."""
        with open("installer/windows/synapse_installer.nsi", "r") as f:
            content = f.read()
        assert "InstallDir" in content

    def test_nsis_registry(self):
        """Check registry entries in NSIS script."""
        with open("installer/windows/synapse_installer.nsi", "r") as f:
            content = f.read()
        assert "WriteRegStr" in content or "HKLM" in content

    def test_nsis_uninstall(self):
        """Check uninstall section in NSIS script."""
        with open("installer/windows/synapse_installer.nsi", "r") as f:
            content = f.read()
        assert "Uninstall" in content

    def test_build_script_exists(self):
        """Check build script exists."""
        assert Path("installer/scripts/build_windows.py").exists()


@pytest.mark.phase6
@pytest.mark.unit
class TestMacOSInstaller:
    """Tests for macOS installer configuration."""

    def test_installer_macos_dir_exists(self):
        """Check installer/macos directory exists."""
        assert Path("installer/macos").exists()

    def test_py2app_setup_exists(self):
        """Check py2app setup.py exists."""
        assert Path("installer/macos/setup.py").exists()

    def test_info_plist_exists(self):
        """Check Info.plist exists."""
        assert Path("installer/macos/Info.plist").exists()

    def test_info_plist_protocol_version(self):
        """Check protocol_version in Info.plist."""
        with open("installer/macos/Info.plist", "r") as f:
            content = f.read()
        assert "ProtocolVersion" in content or "protocol" in content.lower()

    def test_entitlements_exists(self):
        """Check entitlements.plist exists."""
        assert Path("installer/macos/entitlements.plist").exists()


@pytest.mark.phase6
@pytest.mark.unit
class TestLinuxInstaller:
    """Tests for Linux installer configuration."""

    def test_installer_linux_dir_exists(self):
        """Check installer/linux directory exists."""
        assert Path("installer/linux").exists()

    def test_debian_control_exists(self):
        """Check debian control file exists."""
        assert Path("installer/linux/debian/control").exists()

    def test_debian_control_package_name(self):
        """Check package name in debian control."""
        with open("installer/linux/debian/control", "r") as f:
            content = f.read()
        assert "synapse-agent" in content or "synapse" in content

    def test_debian_control_dependencies(self):
        """Check dependencies in debian control."""
        with open("installer/linux/debian/control", "r") as f:
            content = f.read()
        assert "python3" in content

    def test_desktop_entry_exists(self):
        """Check desktop entry exists."""
        assert Path("installer/linux/synapse.desktop").exists()

    def test_desktop_entry_protocol_version(self):
        """Check protocol_version in desktop entry."""
        with open("installer/linux/synapse.desktop", "r") as f:
            content = f.read()
        assert "Protocol" in content or "synapse" in content.lower()

    def test_rpm_spec_exists(self):
        """Check RPM spec file exists."""
        assert Path("installer/linux/rpm/synapse.spec").exists()
