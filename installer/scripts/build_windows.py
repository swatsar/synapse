"""
Synapse Agent - Windows Installer Build Script

Protocol Version: 1.0
Spec Version: 3.1
"""

import subprocess
import shutil
from pathlib import Path


def build_windows_installer() -> bool:
    """Build Windows installer using NSIS."""
    print("Building Windows installer...")

    # Check NSIS is installed
    nsis_path = shutil.which("makensis")
    if not nsis_path:
        print("ERROR: NSIS not found. Please install NSIS.")
        return False

    # Build installer
    installer_dir = Path(__file__).parent.parent / "windows"
    nsi_script = installer_dir / "synapse_installer.nsi"

    result = subprocess.run(
        [nsis_path, str(nsi_script)],
        cwd=installer_dir,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("Windows installer built successfully!")
        return True
    else:
        print(f"ERROR: {result.stderr}")
        return False


if __name__ == "__main__":
    success = build_windows_installer()
    exit(0 if success else 1)
