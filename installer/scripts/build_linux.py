"""
Synapse Agent - Linux Package Build Script

Protocol Version: 1.0
Spec Version: 3.1
"""

import subprocess
import shutil
from pathlib import Path


def build_debian_package() -> bool:
    """Build Debian package."""
    print("Building Debian package...")

    installer_dir = Path(__file__).parent.parent / "linux"
    debian_dir = installer_dir / "debian"

    # Build .deb package
    result = subprocess.run(
        ["dpkg-deb", "--build", str(debian_dir)],
        cwd=installer_dir,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("Debian package built successfully!")
        return True
    else:
        print(f"ERROR: {result.stderr}")
        return False


def build_rpm_package() -> bool:
    """Build RPM package."""
    print("Building RPM package...")

    installer_dir = Path(__file__).parent.parent / "linux"
    rpm_dir = installer_dir / "rpm"
    spec_file = rpm_dir / "synapse.spec"

    # Build .rpm package
    result = subprocess.run(
        ["rpmbuild", "-bb", str(spec_file)],
        cwd=rpm_dir,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("RPM package built successfully!")
        return True
    else:
        print(f"ERROR: {result.stderr}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "deb":
            success = build_debian_package()
        elif sys.argv[1] == "rpm":
            success = build_rpm_package()
        else:
            print("Usage: build_linux.py [deb|rpm]")
            success = False
    else:
        # Build both
        success = build_debian_package() and build_rpm_package()

    exit(0 if success else 1)
