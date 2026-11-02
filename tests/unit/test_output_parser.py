"""Unit tests for Output Parsers. Phase 3 — LangChain patterns.

TDD per LANGCHAIN_INTEGRATION.md §4.
"""
import pytest

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase3
@pytest.mark.unit
class TestJsonOutputParser:
    @pytest.fixture
    def parser(self):
        from synapse.llm.output_parser import JsonOutputParser
        return JsonOutputParser()

    def test_parse_clean_json(self, parser):
        result = parser.parse('{"key": "value", "num": 42}')
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_parse_json_with_markdown_fences(self, parser):
        text = "```json\n{\"success\": true}\n```"
        result = parser.parse(text)
        assert result["success"] is True

    def test_parse_raises_on_invalid_json(self, parser):
        from synapse.llm.output_parser import ParseError
        with pytest.raises(ParseError):
            parser.parse("this is not json")

    def test_format_instructions_exist(self, parser):
        instructions = parser.get_format_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 10


@pytest.mark.phase3
@pytest.mark.unit
class TestListOutputParser:
    @pytest.fixture
    def parser(self):
        from synapse.llm.output_parser import ListOutputParser
        return ListOutputParser()

    def test_parse_numbered_list(self, parser):
        text = "1. First item\n2. Second item\n3. Third item"
        result = parser.parse(text)
        assert len(result) == 3
        assert result[0] == "First item"

    def test_parse_bulleted_list(self, parser):
        text = "- Alpha\n- Beta\n- Gamma"
        result = parser.parse(text)
        assert len(result) == 3
        assert "Alpha" in result


@pytest.mark.phase3
@pytest.mark.unit
class TestBooleanOutputParser:
    @pytest.fixture
    def parser(self):
        from synapse.llm.output_parser import BooleanOutputParser
        return BooleanOutputParser()

    def test_parse_yes(self, parser):
        assert parser.parse("yes") is True
        assert parser.parse("Yes, approved") is True

    def test_parse_no(self, parser):
        assert parser.parse("no") is False
        assert parser.parse("No, denied") is False

    def test_parse_true_false(self, parser):
        assert parser.parse("true") is True
        assert parser.parse("false") is False

    def test_parse_raises_on_ambiguous(self, parser):
        from synapse.llm.output_parser import ParseError
        with pytest.raises(ParseError):
            parser.parse("maybe")


@pytest.mark.phase3
@pytest.mark.unit
class TestStructuredOutputParser:
    @pytest.fixture
    def parser(self):
        from synapse.llm.output_parser import StructuredOutputParser
        return StructuredOutputParser(required_keys=["task", "result"])

    def test_parse_json_with_required_keys(self, parser):
        text = '{"task": "do it", "result": "done"}'
        result = parser.parse(text)
        assert result["task"] == "do it"
        assert result["result"] == "done"
        assert result["protocol_version"] == PROTOCOL_VERSION

    def test_raises_on_missing_required_keys(self, parser):
        from synapse.llm.output_parser import ParseError
        with pytest.raises(ParseError):
            parser.parse('{"task": "only task"}')


@pytest.mark.phase3
@pytest.mark.unit
class TestPydanticOutputParser:
    def test_parse_into_pydantic_model(self):
        from pydantic import BaseModel
        from synapse.llm.output_parser import PydanticOutputParser

        class EvalResponse(BaseModel):
            success: bool
            score: float
            feedback: str

        parser = PydanticOutputParser(EvalResponse)
        text = '{"success": true, "score": 0.9, "feedback": "Great work"}'
        result = parser.parse(text)
        assert isinstance(result, EvalResponse)
        assert result.success is True
        assert result.score == 0.9
