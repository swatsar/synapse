"""Tests for independent task verification.

Training must never treat an executor's own success flag as verification.
These tests pin the deterministic criteria that can make a task eligible.
"""
from __future__ import annotations

import pytest

from synapse.experience.verification import verify_task_outcome


def test_missing_criteria_are_not_verification(tmp_path):
    result = verify_task_outcome(
        {}, {"action_result": {"outputs": [{"content": "done"}]}},
        workspace_root=tmp_path,
    )
    assert result["passed"] is None
    assert result["status"] == "no_criteria"
    assert result["eligibility"] == "ineligible"


def test_file_exists_and_contains(tmp_path):
    target = tmp_path / "report.txt"
    target.write_text("revenue: 42", encoding="utf-8")
    result = verify_task_outcome(
        {"acceptance_criteria": [
            "file_exists:report.txt",
            "file_contains:report.txt::revenue: 42",
            "file_not_contains:report.txt::loss",
        ]},
        {},
        workspace_root=tmp_path,
    )
    assert result["passed"] is True
    assert result["status"] == "passed"
    assert result["eligibility"] == "eligible"


def test_failed_file_criterion_blocks_eligibility(tmp_path):
    (tmp_path / "report.txt").write_text("revenue: 0", encoding="utf-8")
    result = verify_task_outcome(
        {"acceptance_criteria": ["file_contains:report.txt::revenue: 42"]},
        {},
        workspace_root=tmp_path,
    )
    assert result["passed"] is False
    assert result["status"] == "failed"
    assert result["eligibility"] == "ineligible"


def test_path_outside_workspace_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    result = verify_task_outcome(
        {"acceptance_criteria": [f"file_exists:{outside}"]},
        {},
        workspace_root=tmp_path,
    )
    assert result["passed"] is False
    assert result["checks"][0]["reason"] == "path_outside_workspace"


def test_output_criteria_use_real_response_text(tmp_path):
    result = verify_task_outcome(
        {"acceptance_criteria": [
            "output_contains:The answer is 4",
            "output_not_contains:error",
        ]},
        {"action_result": {"outputs": [{"content": "The answer is 4."}]}},
        workspace_root=tmp_path,
    )
    assert result["passed"] is True


def test_dict_criteria_are_supported(tmp_path):
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
    result = verify_task_outcome(
        {"verification": {"type": "file_contains", "path": "ok.txt", "text": "ok"}},
        {},
        workspace_root=tmp_path,
    )
    assert result["passed"] is True


def test_unsupported_criterion_fails_closed(tmp_path):
    result = verify_task_outcome(
        {"acceptance_criteria": ["run_arbitrary_code:whatever"]},
        {},
        workspace_root=tmp_path,
    )
    assert result["passed"] is False
    assert result["checks"][0]["reason"] == "unsupported_criterion"


def test_deterministic_tool_output_is_not_model_training_text(tmp_path):
    """A verified file read must not be attributed to the router's provider."""
    from synapse.experience.verification import build_training_feedback

    result = {
        "action_result": {
            "outputs": [{"content": "file contents", "success": True}],
        }
    }
    feedback = build_training_feedback("Read a file", result)

    assert feedback["model_backed"] is False
    assert feedback["training_ready"] is False
    assert feedback["training_text"] is None
    assert feedback["provider"] is None


def test_model_output_provides_truthful_attribution_and_training_text():
    from synapse.experience.verification import build_training_feedback

    result = {
        "action_result": {
            "outputs": [{
                "content": "The answer to 2 + 2 is 4.",
                "provider": "local_transformers",
                "model": "local/qwen",
            }],
        }
    }
    feedback = build_training_feedback("What is 2 + 2?", result)

    assert feedback["model_backed"] is True
    assert feedback["training_ready"] is True
    assert feedback["provider"] == "local_transformers"
    assert feedback["model"] == "local/qwen"
    assert feedback["training_text"] == (
        "User: What is 2 + 2?\nAssistant: The answer to 2 + 2 is 4."
    )


def test_empty_model_answer_is_not_training_text():
    from synapse.experience.verification import build_training_feedback

    result = {
        "action_result": {
            "outputs": [{"content": "   ", "provider": "local_transformers"}],
        }
    }
    feedback = build_training_feedback("Say nothing", result)

    assert feedback["model_backed"] is True
    assert feedback["training_ready"] is False
    assert feedback["training_text"] is None
