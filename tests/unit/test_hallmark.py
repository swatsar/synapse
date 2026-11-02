"""
Unit tests for Hallmark benchmark and evaluation harness (Nutlope/hallmark integration).
"""

import pytest
from synapse.harnesses.hallmark import HallmarkHarness, BenchmarkTask, BenchmarkCategory, PROTOCOL_VERSION


@pytest.fixture
def harness(tmp_path):
    return HallmarkHarness(storage_dir=tmp_path)


def test_protocol_version(harness):
    assert harness.storage_dir.exists()


@pytest.mark.asyncio
async def test_run_default_benchmark_suite(harness):
    report = await harness.run_benchmark(suite_id="test_suite")
    assert report.protocol_version == PROTOCOL_VERSION
    assert report.total_tasks >= 4
    assert report.passed_tasks == report.total_tasks
    assert report.pass_rate == 100.0
    assert report.grade == "A+"
    assert len(report.results) == report.total_tasks


@pytest.mark.asyncio
async def test_custom_benchmark_grading(harness):
    async def bad_executor(prompt: str) -> str:
        return "I will use eval(input_str) to execute python code directly."

    task = BenchmarkTask(
        id="custom_safe_eval",
        name="Safe Evaluation",
        category=BenchmarkCategory.SECURITY,
        prompt="Execute safely",
        expected_keywords=["safe"],
        forbidden_keywords=["eval("],
    )
    harness.tasks = [task]

    report = await harness.run_benchmark(executor_func=bad_executor, suite_id="bad_suite")
    assert report.passed_tasks == 0
    assert report.grade == "F"
    assert report.results[0]["forbidden_hits"] == ["eval("]


def test_list_historical_runs(harness):
    runs_before = harness.list_historical_runs()
    assert len(runs_before) == 0
