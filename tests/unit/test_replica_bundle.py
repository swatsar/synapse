from __future__ import annotations

import json
from pathlib import Path

from synapse.replication import export_bundle, import_bundle, verify_bundle


def test_replica_bundle_exports_hash_manifest_and_excludes_secrets(tmp_path):
    root = tmp_path / "workspace"
    (root / ".synapse").mkdir(parents=True)
    (root / ".synapse" / "memory_vault.json").write_text('{"entries": []}', encoding="utf-8")
    (root / ".synapse" / "provider_secret.env").write_text("SECRET=do-not-copy", encoding="utf-8")
    destination = tmp_path / "replica.zip"

    manifest = export_bundle(destination, root=root)
    assert destination.is_file()
    assert manifest["secrets_excluded"] is True
    verification = verify_bundle(destination)
    assert verification["valid"] is True
    assert all("secret" not in item["path"].lower() for item in verification["manifest"]["files"])

    target = tmp_path / "restored"
    result = import_bundle(destination, root=target)
    assert result["valid"] is True
    assert (target / ".synapse" / "memory_vault.json").is_file()
    assert not (target / ".synapse" / "provider_secret.env").exists()
