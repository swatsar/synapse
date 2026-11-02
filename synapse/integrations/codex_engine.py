"""
Codex Multi-File Patch & AST Intelligence Engine for Synapse v3.4.1.

Adapted from openai/codex patterns.
Provides multi-file unified diff parsing, atomic transactional patching,
Python AST analysis, and automated test scaffolding generation.

Protocol Version: 1.0
Specification: 3.4.1
"""

from __future__ import annotations

import ast
import difflib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROTOCOL_VERSION: str = "1.0"
logger = logging.getLogger("synapse.integrations.codex_engine")


@dataclass
class FilePatch:
    file_path: str
    original_content: str
    updated_content: str
    diff_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "diff_text": self.diff_text,
        }


@dataclass
class ASTSymbol:
    name: str
    kind: str  # function, class, async_function
    lineno: int
    docstring: Optional[str] = None
    args: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "lineno": self.lineno,
            "docstring": self.docstring,
            "args": self.args,
        }


class CodexEngine:
    """Atomic multi-file patch applicator and AST intelligence analyzer."""

    def __init__(self, workspace_root: Optional[str | Path] = None):
        self.workspace_root = Path(workspace_root or os.getenv("SYNAPSE_WORKSPACE_ROOT", os.getcwd())).resolve()

    def generate_diff(self, file_path: str, original: str, updated: str) -> str:
        """Generate unified diff string."""
        orig_lines = original.splitlines(keepends=True)
        updated_lines = updated.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            updated_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    def create_patch(self, file_path: str, updated_content: str) -> FilePatch:
        """Create a patch object comparing workspace file against updated content."""
        target = (self.workspace_root / file_path).resolve()
        if not target.is_relative_to(self.workspace_root):
            raise PermissionError(f"Target path {file_path} escapes workspace root")

        orig_text = target.read_text(encoding="utf-8") if target.exists() else ""
        diff = self.generate_diff(file_path, orig_text, updated_content)
        return FilePatch(
            file_path=file_path,
            original_content=orig_text,
            updated_content=updated_content,
            diff_text=diff,
        )

    def apply_patches_atomically(self, patches: list[FilePatch]) -> dict[str, Any]:
        """Apply a batch of file patches transactionally, rolling back on error."""
        applied: list[Tuple[Path, Optional[str]]] = []  # (path, backup_original_content)

        try:
            for patch in patches:
                target = (self.workspace_root / patch.file_path).resolve()
                if not target.is_relative_to(self.workspace_root):
                    raise PermissionError(f"Path escape violation: {patch.file_path}")

                orig_text = target.read_text(encoding="utf-8") if target.exists() else None
                applied.append((target, orig_text))

                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(patch.updated_content, encoding="utf-8")

            return {
                "success": True,
                "applied_files": [p.file_path for p in patches],
                "patches_count": len(patches),
                "protocol_version": PROTOCOL_VERSION,
            }
        except Exception as e:
            logger.error("Transactional patch failed, rolling back %d files: %s", len(applied), e)
            for path, orig in applied:
                try:
                    if orig is not None:
                        path.write_text(orig, encoding="utf-8")
                    elif path.exists():
                        path.unlink()
                except Exception as rollback_err:
                    logger.critical("Rollback failure on %s: %s", path, rollback_err)
            raise e

    def analyze_python_ast(self, code: str) -> list[ASTSymbol]:
        """Parse Python source and extract symbols (classes, functions, async functions)."""
        tree = ast.parse(code)
        symbols: list[ASTSymbol] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args if a.arg != "self"]
                symbols.append(
                    ASTSymbol(
                        name=node.name,
                        kind="function",
                        lineno=node.lineno,
                        docstring=ast.get_docstring(node),
                        args=args,
                    )
                )
            elif isinstance(node, ast.AsyncFunctionDef):
                args = [a.arg for a in node.args.args if a.arg != "self"]
                symbols.append(
                    ASTSymbol(
                        name=node.name,
                        kind="async_function",
                        lineno=node.lineno,
                        docstring=ast.get_docstring(node),
                        args=args,
                    )
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    ASTSymbol(
                        name=node.name,
                        kind="class",
                        lineno=node.lineno,
                        docstring=ast.get_docstring(node),
                    )
                )

        return symbols

    def scaffold_tests_for_module(self, module_name: str, code: str) -> str:
        """Generate pytest test scaffold based on AST symbols."""
        symbols = self.analyze_python_ast(code)
        lines = [
            f'"""Automated test scaffold for {module_name}."""',
            "import pytest",
            f"from {module_name} import *",
            "",
        ]

        for sym in symbols:
            if sym.kind in {"function", "async_function"}:
                is_async = sym.kind == "async_function"
                if is_async:
                    lines.append("@pytest.mark.asyncio")
                    lines.append(f"async def test_{sym.name}():")
                else:
                    lines.append(f"def test_{sym.name}():")
                lines.append(f'    """Test placeholder for {sym.name}."""')
                lines.append("    # TODO: Verify expected inputs and outputs")
                lines.append("    pass\n")

        return "\n".join(lines)


_default_codex_engine: Optional[CodexEngine] = None


def get_codex_engine(workspace_root: Optional[str | Path] = None) -> CodexEngine:
    global _default_codex_engine
    if _default_codex_engine is None:
        _default_codex_engine = CodexEngine(workspace_root)
    return _default_codex_engine
