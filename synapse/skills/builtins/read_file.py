"""Built-in UTF-8 file reader with an optional workspace boundary."""
from pathlib import Path

from synapse.core.models import ExecutionContext

PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


class ReadFileSkill:
    """Read a file without allowing paths to escape the configured workspace."""

    def __init__(self, workspace_root: str | Path | None = None):
        self.workspace_root = (
            Path(workspace_root).expanduser().resolve()
            if workspace_root is not None
            else None
        )

    async def execute(self, ctx: ExecutionContext, path: str):
        if not any(p.startswith("fs:read") for p in ctx.capabilities):
            return {"success": False, "error": "Capability denied"}
        try:
            file_path = Path(path).expanduser()
            if self.workspace_root is not None:
                if not file_path.is_absolute():
                    file_path = self.workspace_root / file_path
                # resolve() also resolves existing symlinks and normalizes '..'.
                file_path = file_path.resolve(strict=True)
                if not file_path.is_relative_to(self.workspace_root):
                    return {"success": False, "error": "Path is outside the workspace"}
            if not file_path.is_file():
                return {"success": False, "error": "Path is not a regular file"}
            with file_path.open("r", encoding="utf-8") as file:
                content = file.read()
            return {"success": True, "content": content, "path": str(file_path)}
        except (OSError, UnicodeError, ValueError) as exc:
            return {"success": False, "error": str(exc)}
