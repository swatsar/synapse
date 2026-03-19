"""LLM Evaluation Framework.

Protocol Version: 1.0
Specification: 3.1

Adapted from LangSmith evaluation patterns (LANGSMITH_SDK_INTEGRATION.md §3).
"""
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


@dataclass
class EvalExample:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    input: Dict[str, Any] = field(default_factory=dict)
    expected_output: Any = None
    actual_output: Any = None
    score: Optional[float] = None
    pass_fail: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "expected_output": self.expected_output,
            "actual_output": self.actual_output,
            "score": self.score,
            "pass_fail": self.pass_fail,
            "protocol_version": self.protocol_version,
        }


@dataclass
class EvalDataset:
    name: str
    version: str = "1.0"
    examples: List[EvalExample] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol_version: str = PROTOCOL_VERSION

    def add(self, input_data: Dict, expected: Any, metadata: Optional[Dict] = None) -> EvalExample:
        ex = EvalExample(input=input_data, expected_output=expected, metadata=metadata or {})
        self.examples.append(ex)
        return ex

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "count": len(self.examples),
            "created_at": self.created_at,
            "protocol_version": self.protocol_version,
        }


@dataclass
class EvalResult:
    dataset_name: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    total: int = 0
    passed: int = 0
    failed: int = 0
    avg_score: float = 0.0
    examples: List[EvalExample] = field(default_factory=list)
    ran_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol_version: str = PROTOCOL_VERSION

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset_name": self.dataset_name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "avg_score": round(self.avg_score, 4),
            "ran_at": self.ran_at,
            "protocol_version": self.protocol_version,
        }


def exact_match_evaluator(expected: Any, actual: Any) -> float:
    return 1.0 if str(expected).strip() == str(actual).strip() else 0.0


def contains_evaluator(expected: str, actual: str) -> float:
    return 1.0 if str(expected).lower() in str(actual).lower() else 0.0


def json_keys_evaluator(expected_keys: List[str], actual: Any) -> float:
    if isinstance(actual, str):
        try:
            actual = json.loads(actual)
        except Exception:
            return 0.0
    if not isinstance(actual, dict):
        return 0.0
    found = sum(1 for k in expected_keys if k in actual)
    return found / len(expected_keys) if expected_keys else 1.0


def protocol_version_evaluator(expected_version: str, actual: Any) -> float:
    if isinstance(actual, dict):
        return 1.0 if actual.get("protocol_version") == expected_version else 0.0
    return 0.0


class LLMEvaluator:
    """Evaluation runner adapted from LangSmith SDK (LANGSMITH_SDK_INTEGRATION.md §3.1)."""

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    def __init__(self, llm_provider: Any = None):
        self.llm = llm_provider
        self._datasets: Dict[str, EvalDataset] = {}
        self._results: List[EvalResult] = []
        audit(event="evaluator_initialized", has_llm=bool(llm_provider), protocol_version=PROTOCOL_VERSION)

    def create_dataset(self, name: str, version: str = "1.0") -> EvalDataset:
        ds = EvalDataset(name=name, version=version)
        self._datasets[name] = ds
        return ds

    def get_dataset(self, name: str) -> Optional[EvalDataset]:
        return self._datasets.get(name)

    async def run(
        self,
        dataset_name: str,
        fn: Callable,
        scorer: Callable = exact_match_evaluator,
        threshold: float = 0.7,
    ) -> EvalResult:
        ds = self._datasets.get(dataset_name)
        if not ds:
            raise KeyError(f"Dataset not found: {dataset_name!r}")

        result = EvalResult(dataset_name=dataset_name, total=len(ds.examples))
        scores: List[float] = []

        for ex in ds.examples:
            try:
                actual = await fn(**ex.input)
                score = scorer(ex.expected_output, actual)
                ex.actual_output = actual
                ex.score = score
                ex.pass_fail = score >= threshold
                result.examples.append(ex)
                scores.append(score)
                if ex.pass_fail:
                    result.passed += 1
                else:
                    result.failed += 1
            except Exception as e:
                ex.actual_output = None
                ex.score = 0.0
                ex.pass_fail = False
                ex.metadata["error"] = str(e)
                result.examples.append(ex)
                scores.append(0.0)
                result.failed += 1

        result.avg_score = sum(scores) / len(scores) if scores else 0.0
        self._results.append(result)

        audit(
            event="evaluation_run_complete",
            dataset=dataset_name,
            run_id=result.run_id,
            pass_rate=round(result.pass_rate, 4),
            protocol_version=PROTOCOL_VERSION,
        )
        return result

    async def llm_judge(self, output: str, criteria: str) -> float:
        if not self.llm:
            return 0.5
        try:
            prompt = f"Rate 0.0-1.0: {criteria}\nOutput: {output}\nReturn only the number."
            response = await self.llm.generate(prompt)
            content = response.get("content", "0.5") if isinstance(response, dict) else str(response)
            import re
            numbers = re.findall(r"\d+(?:\.\d+)?", content)
            return max(0.0, min(1.0, float(numbers[0]))) if numbers else 0.5
        except Exception:
            return 0.5

    def get_results_summary(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._results]
