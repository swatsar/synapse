"""Worker environment must expose CLI install roots for OpenCode discovery."""
from __future__ import annotations

from pathlib import Path

import synapse.integrations.opencode_bridge as bridge
from synapse.runtime.worker_backend import IsolatedWorkerBackend


def test_clean_env_keeps_cli_install_roots(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    monkeypatch.setenv("ProgramFiles", r"C:\Program Files")
    monkeypatch.setenv("ChocolateyInstall", r"C:\ProgramData\chocolatey")

    env = IsolatedWorkerBackend._build_clean_env()

    assert env["LOCALAPPDATA"] == r"C:\Users\test\AppData\Local"
    assert env["APPDATA"] == r"C:\Users\test\AppData\Roaming"
    assert env["ProgramFiles"] == r"C:\Program Files"
    assert env["ChocolateyInstall"] == r"C:\ProgramData\chocolatey"


def test_discovery_uses_home_install_roots_without_appdata(monkeypatch, tmp_path):
    """A worker without LOCALAPPDATA must still find a user-scoped install."""
    fake_home = tmp_path / "home"
    cli = (
        fake_home / "AppData" / "Local" / "Programs" / "velly" / "resources"
        / "app.asar.unpacked" / "node_modules" / "@opencode"
        / "cli-windows-x64" / "bin" / "opencode.exe"
    )
    cli.parent.mkdir(parents=True)
    cli.write_text("", encoding="utf-8")

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    for name in ("LOCALAPPDATA", "APPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(bridge.shutil, "which", lambda name: None)

    candidates = bridge._opencode_cli_candidates()

    assert cli in candidates
