"""Structured Output Parser with Pydantic validation.

Protocol Version: 1.0
Specification: 3.1

Adapted from LangChain output parser patterns (LANGCHAIN_INTEGRATION.md §4).
Synapse additions: security validation, protocol versioning, audit logging.
"""
import json
import re
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from synapse.observability.logger import audit

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)

T = TypeVar("T")


class ParseError(Exception):
    """Raised when output parsing fails."""
    pass


class BaseOutputParser(ABC, Generic[T]):
    """Abstract output parser.

    Adapted from LangChain BaseOutputParser (LANGCHAIN_INTEGRATION.md §4.1).
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    @abstractmethod
    def parse(self, text: str) -> T:
        """Parse LLM output text into structured result."""

    def get_format_instructions(self) -> str:
        """Return format instructions for the LLM prompt."""
        return "Provide a well-structured response."


class JsonOutputParser(BaseOutputParser[Dict[str, Any]]):
    """Parse JSON from LLM output, stripping markdown fences."""

    def parse(self, text: str) -> Dict[str, Any]:
        # Strip markdown fences
        cleaned = text.strip()
        cleaned = re.sub(r"```json\s*", "", cleaned)
        cleaned = re.sub(r"```\s*", "", cleaned)
        cleaned = cleaned.strip()
        # Find JSON object or array
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        try:
            result = json.loads(cleaned)
            audit(event="json_parse_success", keys=list(result.keys()) if isinstance(result, dict) else [], protocol_version=PROTOCOL_VERSION)
            return result
        except json.JSONDecodeError as e:
            audit(event="json_parse_error", error=str(e), preview=text[:100], protocol_version=PROTOCOL_VERSION)
            raise ParseError(f"Failed to parse JSON: {e}\nText: {text[:200]}")

    def get_format_instructions(self) -> str:
        return 'Return your answer as a valid JSON object. Do not include markdown or explanations.'


class PydanticOutputParser(BaseOutputParser[T]):
    """Parse LLM output into a Pydantic model.

    Adapted from LangChain PydanticOutputParser (LANGCHAIN_INTEGRATION.md §4.1).
    """

    def __init__(self, pydantic_class: Type[T]):
        self.pydantic_class = pydantic_class
        self._json_parser = JsonOutputParser()

    def parse(self, text: str) -> T:
        data = self._json_parser.parse(text)
        try:
            result = self.pydantic_class(**data)
            audit(event="pydantic_parse_success", model=self.pydantic_class.__name__, protocol_version=PROTOCOL_VERSION)
            return result
        except Exception as e:
            audit(event="pydantic_parse_error", model=self.pydantic_class.__name__, error=str(e), protocol_version=PROTOCOL_VERSION)
            raise ParseError(f"Pydantic validation failed ({self.pydantic_class.__name__}): {e}")

    def get_format_instructions(self) -> str:
        try:
            schema = self.pydantic_class.model_json_schema()
            return f"Return JSON matching this schema: {json.dumps(schema, indent=2)}"
        except Exception:
            return f"Return JSON matching the {self.pydantic_class.__name__} schema."


class ListOutputParser(BaseOutputParser[List[str]]):
    """Parse a numbered or bulleted list from LLM output."""

    def parse(self, text: str) -> List[str]:
        lines = text.strip().split("\n")
        items: List[str] = []
        for line in lines:
            line = line.strip()
            # Remove common list prefixes
            line = re.sub(r"^[\d]+[.)\s]+", "", line)
            line = re.sub(r"^[-*•]\s+", "", line)
            if line:
                items.append(line)
        audit(event="list_parse_success", count=len(items), protocol_version=PROTOCOL_VERSION)
        return items

    def get_format_instructions(self) -> str:
        return "Return a numbered list, one item per line."


class BooleanOutputParser(BaseOutputParser[bool]):
    """Parse yes/no or true/false response."""

    def parse(self, text: str) -> bool:
        t = text.strip().lower()
        if any(w in t for w in ["yes", "true", "correct", "approved", "1"]):
            return True
        if any(w in t for w in ["no", "false", "incorrect", "denied", "0"]):
            return False
        raise ParseError(f"Cannot parse boolean from: {text[:100]}")

    def get_format_instructions(self) -> str:
        return "Answer with exactly 'yes' or 'no'."


class StructuredOutputParser(BaseOutputParser[Dict[str, Any]]):
    """Parse structured key:value output with schema validation.

    Adapted from LangChain StructuredOutputParser (LANGCHAIN_INTEGRATION.md §4.1).
    """

    def __init__(self, required_keys: Optional[List[str]] = None):
        self.required_keys = required_keys or []
        self._json_parser = JsonOutputParser()

    def parse(self, text: str) -> Dict[str, Any]:
        # Try JSON first
        try:
            data = self._json_parser.parse(text)
        except ParseError:
            # Fall back to key: value parsing
            data = {}
            for line in text.strip().split("\n"):
                if ":" in line:
                    k, _, v = line.partition(":")
                    data[k.strip().lower()] = v.strip()

        # Validate required keys
        missing = [k for k in self.required_keys if k not in data]
        if missing:
            raise ParseError(f"Missing required fields: {missing}")

        data["protocol_version"] = PROTOCOL_VERSION
        return data

    def get_format_instructions(self) -> str:
        if self.required_keys:
            return f"Return JSON with these required fields: {self.required_keys}"
        return "Return a structured JSON object."
