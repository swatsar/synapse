"""
Unit tests for Composable Skill Library (mattpocock/skills integration).
"""

import pytest
from synapse.skills.library import SkillLibrary, ComposableSkill, SkillParameter, PROTOCOL_VERSION


@pytest.fixture
def library():
    return SkillLibrary()


def test_protocol_version(library):
    skills = library.list_skills()
    assert len(skills) >= 4
    for skill in skills:
        assert skill.protocol_version == PROTOCOL_VERSION


@pytest.mark.asyncio
async def test_execute_builtin_memory_skill(library):
    skill = library.get("memory_recall")
    assert skill is not None
    result = await skill.execute({"query": "pytest windows"})
    assert result["success"] is True
    assert "memories" in result["result"]


@pytest.mark.asyncio
async def test_execute_builtin_model_route_skill(library):
    skill = library.get("model_route")
    assert skill is not None
    result = await skill.execute({"task": "Write an async python generator"})
    assert result["success"] is True
    assert "decision" in result["result"]


@pytest.mark.asyncio
async def test_custom_skill_registration_and_execution(library):
    def _reverse_text(text: str) -> str:
        return text[::-1]

    custom_skill = ComposableSkill(
        id="reverse_text",
        name="Reverse Text",
        description="Reverses the provided string",
        parameters=[SkillParameter(name="text", type_name="string", description="Input string", required=True)],
        required_capabilities=["text:transform"],
        risk_level=0,
        handler=_reverse_text,
    )
    library.register(custom_skill)

    res = await library.get("reverse_text").execute({"text": "synapse"})
    assert res["success"] is True
    assert res["result"] == "espanys"


@pytest.mark.asyncio
async def test_skill_pipeline_execution(library):
    pipeline = [
        {"skill_id": "code_review", "params": {"code": "def run():\n    print('debug')\n"}},
    ]
    results = await library.execute_pipeline(pipeline)
    assert len(results) == 1
    assert results[0]["skill_id"] == "code_review"
    assert len(results[0]["result"]["suggestions"]) >= 1
