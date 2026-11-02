"""
Synapse Agent - macOS App Bundle Build Script

Protocol Version: 1.0
Spec Version: 3.1
"""

import subprocess
import shutil
from pathlib import Path


def build_macos_app() -> bool:
    """Build macOS app bundle using py2app."""
    print("Building macOS app bundle...")

    # Check py2app is installed
    try:
        import py2app
    except ImportError:
        print("ERROR: py2app not found. Install with: pip install py2app")
        return False

    # Build app
    installer_dir = Path(__file__).parent.parent / "macos"
    setup_script = installer_dir / "setup.py"

    result = subprocess.run(
        ["python", str(setup_script), "py2app"],
        cwd=installer_dir,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("macOS app bundle built successfully!")
        return True
    else:
        print(f"ERROR: {result.stderr}")
        return False


if __name__ == "__main__":
    success = build_macos_app()
    exit(0 if success else 1)
