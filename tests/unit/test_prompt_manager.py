"""Unit tests for Prompt Version Manager. Phase 4 — Self-Evolution.

TDD per AGENT_ZERO_INTEGRATION.md §5 + ANTHROPIC_PATTERNS_INTEGRATION.md §3.
"""
import pytest

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase4
@pytest.mark.unit
class TestPromptVersion:
    def test_prompt_version_hash(self):
        from synapse.llm.prompt_manager import PromptVersion
        pv = PromptVersion(version="1.0.0", template="Hello {name}")
        assert pv.hash
        assert len(pv.hash) == 12

    def test_prompt_render_with_variables(self):
        from synapse.llm.prompt_manager import PromptVersion
        pv = PromptVersion(version="1.0.0", template="Task: {task}\nSkills: {skills}", variables=["task", "skills"])
        rendered = pv.render(task="analyze logs", skills="read_file, web_search")
        assert "analyze logs" in rendered
        assert "read_file" in rendered

    def test_prompt_render_missing_variable_raises(self):
        from synapse.llm.prompt_manager import PromptVersion
        pv = PromptVersion(version="1.0.0", template="Task: {task}", variables=["task"])
        with pytest.raises(ValueError):
            pv.render(wrong_key="value")

    def test_prompt_version_to_dict(self):
        from synapse.llm.prompt_manager import PromptVersion
        pv = PromptVersion(version="1.0.0", template="test", description="Test prompt")
        d = pv.to_dict()
        assert d["version"] == "1.0.0"
        assert d["protocol_version"] == PROTOCOL_VERSION


@pytest.mark.phase4
@pytest.mark.unit
class TestPromptManager:
    @pytest.fixture
    def manager(self):
        from synapse.llm.prompt_manager import PromptManager
        return PromptManager()

    def test_default_prompts_loaded(self, manager):
        names = manager.list_names()
        assert "planner_system" in names
        assert "critic_eval" in names
        assert "developer_codegen" in names

    def test_get_active_prompt(self, manager):
        pv = manager.get_active("planner_system")
        assert pv is not None
        assert pv.is_active is True
        assert pv.protocol_version == PROTOCOL_VERSION

    def test_render_prompt(self, manager):
        rendered = manager.render("planner_system",
                                  task="analyze data", skills="read_file", memory="none")
        assert "analyze data" in rendered
        assert "read_file" in rendered

    def test_register_new_version(self, manager):
        from synapse.llm.prompt_manager import PromptVersion
        v2 = PromptVersion(
            version="2.0.0",
            template="New template: {task}",
            variables=["task"],
            description="Updated planner prompt",
        )
        manager.register("planner_system", v2)
        active = manager.get_active("planner_system")
        assert active.version == "2.0.0"

    def test_rollback_to_previous_version(self, manager):
        from synapse.llm.prompt_manager import PromptVersion
        v2 = PromptVersion(version="2.0.0", template="V2 {task}", variables=["task"])
        manager.register("planner_system", v2)
        manager.rollback("planner_system")
        active = manager.get_active("planner_system")
        assert active.version == "1.0.0"

    def test_update_performance_score(self, manager):
        manager.update_performance("planner_system", 0.87)
        pv = manager.get_active("planner_system")
        assert pv.performance_score == 0.87

    def test_register_new_prompt(self, manager):
        from synapse.llm.prompt_manager import PromptVersion
        pv = PromptVersion(version="1.0.0", template="Custom: {input}", variables=["input"])
        manager.register("custom_prompt", pv)
        assert "custom_prompt" in manager.list_names()
        active = manager.get_active("custom_prompt")
        assert active.version == "1.0.0"

    def test_list_prompts_structure(self, manager):
        prompts = manager.list_prompts()
        assert isinstance(prompts, dict)
        for name, versions in prompts.items():
            assert isinstance(versions, list)
            for v in versions:
                assert "version" in v
                assert "protocol_version" in v
