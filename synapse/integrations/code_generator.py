"""
Code Generator for Synapse.

Generates code via LLM with AST-based security scanning, test generation,
and documentation. Falls back to meaningful templates when no LLM is available.

Protocol Version: 1.0
Specification: 3.1
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
import ast
import logging

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger(__name__)


class CodeLanguage(str, Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"


class CodeSecurityLevel(str, Enum):
    """Security level of generated code."""
    SAFE = "safe"
    REVIEW_REQUIRED = "review_required"
    UNSAFE = "unsafe"


@dataclass
class GeneratedCode:
    """Generated code result."""
    code: str
    language: CodeLanguage
    security_level: CodeSecurityLevel = CodeSecurityLevel.SAFE
    security_issues: List[str] = field(default_factory=list)
    tests: Optional[str] = None
    documentation: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION
    trace_id: str = ""


class CodeGenerator:
    """
    Code generator with security scanning and test generation.

    Features:
    - Multi-language code generation via LLM (with template fallback)
    - AST-based security scanning for Python
    - Pattern-based scanning for all languages
    - Automatic test generation
    - Documentation generation
    - Protocol versioning compliance
    """

    PROTOCOL_VERSION: str = PROTOCOL_VERSION

    DANGEROUS_PATTERNS: Dict[CodeLanguage, List[str]] = {
        CodeLanguage.PYTHON: [
            "eval(", "exec(", "os.system(", "subprocess.Popen(",
            "__import__", "compile(", "input(",
        ],
        CodeLanguage.JAVASCRIPT: [
            "eval(", "Function(", "innerHTML =", "document.write(",
        ],
        CodeLanguage.TYPESCRIPT: [
            "eval(", "Function(",
        ],
        CodeLanguage.GO: [
            "exec.Command(", "os.Remove(", "os.RemoveAll(",
        ],
        CodeLanguage.RUST: [
            "std::process::Command", "fs::remove", "unsafe {",
        ],
    }

    def __init__(
        self,
        llm_provider: Any = None,
        security_manager: Any = None,
        audit_logger: Any = None,
    ):
        self.llm = llm_provider
        self.security = security_manager
        self.audit = audit_logger

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def generate(
        self,
        task_description: str,
        language: CodeLanguage = CodeLanguage.PYTHON,
        context: Optional[Dict[str, Any]] = None,
    ) -> GeneratedCode:
        """Generate code for a task with security scanning and tests."""
        context = context or {}

        if self.llm:
            code = await self._generate_with_llm(task_description, language)
        else:
            code = self._generate_template_code(task_description, language)

        security_level, issues = await self._scan_security(code, language)
        tests = await self._generate_tests(code, language)
        documentation = await self._generate_documentation(code, language, task_description)

        result = GeneratedCode(
            code=code,
            language=language,
            security_level=security_level,
            security_issues=issues,
            tests=tests,
            documentation=documentation,
            trace_id=context.get("trace_id", ""),
            protocol_version=self.PROTOCOL_VERSION,
        )

        if self.audit:
            try:
                await self.audit.emit_event(
                    event_type="code_generated",
                    details={
                        "language": language.value,
                        "security_level": security_level.value,
                        "issues_count": len(issues),
                        "protocol_version": self.PROTOCOL_VERSION,
                    },
                )
            except Exception:
                pass

        return result

    # -------------------------------------------------------------------------
    # Code Generation
    # -------------------------------------------------------------------------

    async def _generate_with_llm(self, task: str, language: CodeLanguage) -> str:
        """Generate code using LLM."""
        prompt = (
            f"Generate {language.value} code for the following task:\n{task}\n\n"
            "Requirements:\n"
            f"1. Follow best practices for {language.value}\n"
            "2. Include error handling\n"
            "3. Include type hints/annotations\n"
            '4. Include PROTOCOL_VERSION = "1.0" constant\n'
            "5. Do NOT use dangerous functions (eval, exec, os.system)\n\n"
            "Return ONLY the code, no explanations."
        )
        try:
            if hasattr(self.llm, "generate"):
                return await self.llm.generate(prompt)
            return self._generate_template_code(task, language)
        except Exception as e:
            logger.warning("LLM code generation failed: %s — using template", e)
            return self._generate_template_code(task, language)

    def _generate_template_code(self, task_description: str, language: CodeLanguage) -> str:
        """Return a working code template when no LLM is available."""
        safe = re.sub(r"[^a-z0-9_]", "_", task_description.lower()[:40]).strip("_") or "execute_task"

        if language == CodeLanguage.PYTHON:
            indent = "    "
            lines = [
                '"""',
                f"Auto-generated stub for: {task_description}",
                "Protocol Version: 1.0",
                '"""',
                "from typing import Any, Dict, Optional",
                "import logging",
                "",
                'PROTOCOL_VERSION: str = "1.0"',
                "logger = logging.getLogger(__name__)",
                "",
                "",
                f"def {safe}(",
                f"{indent}input_data: Dict[str, Any],",
                f"{indent}context: Optional[Dict[str, Any]] = None,",
                ") -> Dict[str, Any]:",
                f'{indent}"""Execute: {task_description}',
                "",
                f"{indent}Args:",
                f"{indent}{indent}input_data: Input parameters",
                f"{indent}{indent}context: Optional execution context",
                "",
                f"{indent}Returns:",
                f"{indent}{indent}Dict with result and protocol_version",
                f'{indent}"""',
                f"{indent}context = context or {{}}",
                f'{indent}logger.info("Executing: {task_description}")',
                f"{indent}# TODO: implement logic for: {task_description}",
                f"{indent}return {{",
                f'{indent}{indent}"status": "not_implemented",',
                f'{indent}{indent}"task": "{task_description}",',
                f'{indent}{indent}"input": input_data,',
                f'{indent}{indent}"protocol_version": PROTOCOL_VERSION,',
                f"{indent}}}",
            ]
            return "\n".join(lines) + "\n"

        if language == CodeLanguage.JAVASCRIPT:
            lines = [
                f"// Auto-generated stub for: {task_description}",
                "// Protocol Version: 1.0",
                "",
                'const PROTOCOL_VERSION = "1.0";',
                "",
                "/**",
                f" * Execute: {task_description}",
                " * @param {Object} inputData",
                " * @param {Object} [context={}]",
                " * @returns {Promise<Object>}",
                " */",
                "async function executeTask(inputData, context = {}) {",
                f"  // TODO: implement: {task_description}",
                "  return {",
                "    status: 'not_implemented',",
                f"    task: '{task_description}',",
                "    protocol_version: PROTOCOL_VERSION,",
                "  };",
                "}",
                "",
                "module.exports = { executeTask };",
            ]
            return "\n".join(lines) + "\n"

        return f"// Auto-generated stub for: {task_description}\n// TODO: implement\n"

    # -------------------------------------------------------------------------
    # Security Scanning
    # -------------------------------------------------------------------------

    async def _scan_security(
        self,
        code: str,
        language: CodeLanguage,
    ) -> Tuple[CodeSecurityLevel, List[str]]:
        """Scan code for security issues using patterns + AST."""
        issues: List[str] = []
        dangerous = self.DANGEROUS_PATTERNS.get(language, [])

        for pattern in dangerous:
            if pattern in code:
                issues.append(f"Dangerous pattern found: {pattern}")

        if language == CodeLanguage.PYTHON:
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in ("pickle", "marshal", "shelve"):
                                issues.append(f"Potentially unsafe import: {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module in ("pickle", "marshal"):
                            issues.append(f"Potentially unsafe import from: {node.module}")
            except SyntaxError as e:
                issues.append(f"Syntax error in generated code: {e}")

        if issues:
            return (CodeSecurityLevel.UNSAFE, issues)
        return (CodeSecurityLevel.SAFE, [])

    # -------------------------------------------------------------------------
    # Test Generation
    # -------------------------------------------------------------------------

    async def _generate_tests(self, code: str, language: CodeLanguage) -> str:
        """Generate tests using LLM if available, otherwise static analysis."""
        if self.llm:
            prompt = (
                f"Generate pytest unit tests for this {language.value} code.\n"
                "Return ONLY the test code, no explanations.\n\n"
                f"Code to test:\n{code}\n\n"
                "Requirements: use pytest, test happy path and edge cases."
            )
            try:
                result = await self.llm.generate(prompt)
                if result:
                    return result
            except Exception:
                pass

        # Fallback: static analysis
        if language == CodeLanguage.PYTHON:
            func_names: List[str] = []
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            func_names.append(node.name)
            except SyntaxError:
                pass

            test_lines = [
                '"""Auto-generated tests."""',
                "import pytest",
                "",
            ]
            for fn in func_names:
                test_lines += [
                    f"def test_{fn}_is_callable():",
                    f'    """Test that {fn} exists."""',
                    f"    # Import the module under test and verify {fn} is callable",
                    f"    pass  # TODO: add real assertions for {fn}",
                    "",
                ]
            if not func_names:
                test_lines.append("# No public functions found — add assertions manually")
                test_lines.append("")
            test_lines += [
                "def test_protocol_version():",
                '    """Protocol version must be 1.0."""',
                '    assert PROTOCOL_VERSION == "1.0"',
                "",
            ]
            return "\n".join(test_lines)

        return f"// Auto-generated tests for {language.value}\n// TODO: add assertions\n"

    # -------------------------------------------------------------------------
    # Documentation
    # -------------------------------------------------------------------------

    async def _generate_documentation(
        self,
        code: str,
        language: CodeLanguage,
        task: str,
    ) -> str:
        """Generate markdown documentation for generated code."""
        lines = [
            "# Generated Code Documentation",
            "",
            "## Task",
            task,
            "",
            "## Language",
            language.value,
            "",
            f"## Protocol Version",
            PROTOCOL_VERSION,
            "",
            "## Generated At",
            datetime.now(timezone.utc).isoformat(),
            "",
            "## Code",
            f"```{language.value}",
            code,
            "```",
        ]
        return "\n".join(lines)


# Skill manifest for registry registration
SKILL_MANIFEST = {
    "name": "code_generator",
    "version": "1.0.0",
    "description": "Multi-language code generator with AST security scanning and test generation",
    "author": "synapse_core",
    "inputs": {
        "task_description": "str",
        "language": "str",
    },
    "outputs": {
        "code": "str",
        "security_level": "str",
        "tests": "str",
        "documentation": "str",
    },
    "required_capabilities": ["code:generate"],
    "risk_level": 3,
    "isolation_type": "container",
    "protocol_version": PROTOCOL_VERSION,
}
