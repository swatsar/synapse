"""Unit tests for Developer Agent (CreateSkill pipeline). Phase 4 — Self-Evolution.

TDD per AGENT_ZERO_INTEGRATION.md §1 + §4.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

PROTOCOL_VERSION = "1.0"


@pytest.mark.phase4
@pytest.mark.unit
@pytest.mark.security
class TestDeveloperAgentASTScan:
    @pytest.fixture
    def developer(self):
        from synapse.agents.developer import DeveloperAgent
        return DeveloperAgent()

    def test_blocks_os_import(self, developer):
        code = "import os\nresult = os.getcwd()"
        issues = developer._ast_security_scan(code)
        assert any("os" in i for i in issues)

    def test_blocks_subprocess(self, developer):
        code = "import subprocess\nsubprocess.run(['ls'])"
        issues = developer._ast_security_scan(code)
        assert len(issues) > 0

    def test_blocks_eval(self, developer):
        code = "eval('print(1)')"
        issues = developer._ast_security_scan(code)
        assert any("eval" in i for i in issues)

    def test_blocks_exec(self, developer):
        code = "exec('x = 1')"
        issues = developer._ast_security_scan(code)
        assert any("exec" in i for i in issues)

    def test_allows_pathlib(self, developer):
        code = "from pathlib import Path\nresult = Path('.').read_text()"
        issues = developer._ast_security_scan(code)
        assert len(issues) == 0

    def test_allows_json(self, developer):
        code = "import json\nresult = json.loads('{}')"
        issues = developer._ast_security_scan(code)
        assert len(issues) == 0

    def test_detects_syntax_error(self, developer):
        issues = developer._ast_security_scan("def broken(: pass")
        assert len(issues) > 0


@pytest.mark.phase4
@pytest.mark.unit
class TestDeveloperAgentGeneration:
    @pytest.fixture
    def developer_no_llm(self):
        from synapse.agents.developer import DeveloperAgent
        return DeveloperAgent()

    @pytest.fixture
    def developer_with_llm(self):
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value={
            "content": "result = {'status': 'ok', 'data': kwargs.get('data', {})}",
            "usage": {}
        })
        from synapse.agents.developer import DeveloperAgent
        return DeveloperAgent(llm_provider=mock_llm)

    @pytest.mark.asyncio
    async def test_generate_returns_skill_object(self, developer_no_llm):
        result = await developer_no_llm.generate_skill("read a CSV file")
        assert "skill" in result
        skill = result["skill"]
        assert skill.name
        assert skill.code
        assert skill.tests

    @pytest.mark.asyncio
    async def test_skill_code_contains_base_class(self, developer_no_llm):
        result = await developer_no_llm.generate_skill("fetch URL content")
        assert "BaseSkill" in result["skill"].code

    @pytest.mark.asyncio
    async def test_skill_code_has_execute_method(self, developer_no_llm):
        result = await developer_no_llm.generate_skill("process text data")
        assert "async def execute" in result["skill"].code

    @pytest.mark.asyncio
    async def test_skill_has_protocol_version(self, developer_no_llm):
        result = await developer_no_llm.generate_skill("do something")
        assert result["skill"].protocol_version == PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_skill_infers_capabilities(self, developer_no_llm):
        result = await developer_no_llm.generate_skill("read file contents")
        caps = result["skill"].required_capabilities
        assert any("fs:read" in c for c in caps)

    @pytest.mark.asyncio
    async def test_skill_with_llm_provider(self, developer_with_llm):
        result = await developer_with_llm.generate_skill("transform JSON data")
        assert result["skill"].code
        assert result["skill"].passed_ast_scan is True

    @pytest.mark.asyncio
    async def test_tests_contain_pytest_class(self, developer_no_llm):
        result = await developer_no_llm.generate_skill("analyze logs")
        assert "class Test" in result["skill"].tests
        assert "pytest" in result["skill"].tests

    def test_task_to_skill_name(self, developer_no_llm):
        name = developer_no_llm._task_to_skill_name("Read a CSV file from disk")
        assert "_" in name
        assert name.islower()

    def test_to_class_name(self, developer_no_llm):
        cls = developer_no_llm._to_class_name("read_csv_file")
        assert cls == "ReadCsvFileSkill"

    def test_infer_http_capability(self, developer_no_llm):
        caps = developer_no_llm._infer_capabilities("fetch data from HTTP API endpoint")
        assert "net:http" in caps

    def test_infer_risk_from_caps(self, developer_no_llm):
        risk = developer_no_llm._infer_risk(["os:process"])
        assert risk >= 4
        safe_risk = developer_no_llm._infer_risk(["memory:read"])
        assert safe_risk <= 2
