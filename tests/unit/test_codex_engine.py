"""
Unit tests for Codex Engine (openai/codex integration).
"""

import pytest
from pathlib import Path
from synapse.integrations.codex_engine import CodexEngine, FilePatch, PROTOCOL_VERSION


@pytest.fixture
def codex(tmp_path):
    return CodexEngine(workspace_root=tmp_path)


def test_protocol_version(codex):
    assert codex.workspace_root.exists()


def test_generate_diff_and_create_patch(codex, tmp_path):
    sample = tmp_path / "hello.py"
    sample.write_text("def run():\n    return 1\n", encoding="utf-8")

    updated = "def run():\n    return 2\n"
    patch = codex.create_patch("hello.py", updated)
    assert "return 1" in patch.diff_text
    assert "return 2" in patch.diff_text


def test_apply_patches_atomically(codex, tmp_path):
    f1 = tmp_path / "mod1.py"
    f1.write_text("x = 10", encoding="utf-8")

    patch1 = codex.create_patch("mod1.py", "x = 20")
    patch2 = codex.create_patch("mod2.py", "y = 30")

    res = codex.apply_patches_atomically([patch1, patch2])
    assert res["success"] is True
    assert res["patches_count"] == 2
    assert (tmp_path / "mod1.py").read_text(encoding="utf-8") == "x = 20"
    assert (tmp_path / "mod2.py").read_text(encoding="utf-8") == "y = 30"


def test_atomic_rollback_on_failure(codex, tmp_path):
    f1 = tmp_path / "safe.py"
    f1.write_text("initial = True", encoding="utf-8")

    patch_valid = codex.create_patch("safe.py", "initial = False")
    # Malformed patch that tries to escape workspace
    patch_malicious = FilePatch(
        file_path="../outside.py",
        original_content="",
        updated_content="evil = True",
        diff_text="",
    )

    with pytest.raises(PermissionError):
        codex.apply_patches_atomically([patch_valid, patch_malicious])

    # Ensure rollback restored initial content
    assert (tmp_path / "safe.py").read_text(encoding="utf-8") == "initial = True"


def test_ast_symbol_extraction_and_test_scaffold(codex):
    code = """
def calculate_metrics(data: list) -> dict:
    '''Calculate summary statistics.'''
    return {}

async def fetch_remote_state(url: str):
    '''Fetch async endpoint.'''
    pass

class DataPipeline:
    '''Pipeline coordinator.'''
    pass
    """
    symbols = codex.analyze_python_ast(code)
    assert len(symbols) == 3
    names = {s.name for s in symbols}
    assert "calculate_metrics" in names
    assert "fetch_remote_state" in names
    assert "DataPipeline" in names

    scaffold = codex.scaffold_tests_for_module("test_module", code)
    assert "def test_calculate_metrics():" in scaffold
    assert "@pytest.mark.asyncio" in scaffold
    assert "async def test_fetch_remote_state():" in scaffold


def test_reject_duplicate_paths_in_batch(codex, tmp_path):
    f1 = tmp_path / "dup.py"
    f1.write_text("x = 1", encoding="utf-8")

    patch1 = codex.create_patch("dup.py", "x = 2")
    patch2 = codex.create_patch("dup.py", "x = 3")

    with pytest.raises(ValueError, match="Duplicate file path in patch batch"):
        codex.apply_patches_atomically([patch1, patch2])
    # Ensure working tree unchanged
    assert f1.read_text(encoding="utf-8") == "x = 1"


def test_reject_preimage_hash_mismatch(codex, tmp_path):
    f1 = tmp_path / "stale.py"
    f1.write_text("v1", encoding="utf-8")

    patch = codex.create_patch("stale.py", "v2")
    # Simulate concurrent modification to disk file
    f1.write_text("v1_modified_by_another_process", encoding="utf-8")

    with pytest.raises(ValueError, match="Preimage hash mismatch"):
        codex.apply_patches_atomically([patch])
    # Disk remains modified by concurrent process, not overwritten with v2
    assert f1.read_text(encoding="utf-8") == "v1_modified_by_another_process"

