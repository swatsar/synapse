PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

from pathlib import Path

from synapse.core.models import ExecutionContext


class WriteFileSkill:
    """Write a UTF-8 text file, optionally bounded to a workspace root."""

    def __init__(self, workspace_root: str | Path | None = None):
        self.workspace_root = (
            Path(workspace_root).expanduser().resolve()
            if workspace_root is not None
            else None
        )

    async def execute(self, ctx: ExecutionContext, path: str, content: str):
        # Simple capability check – allow if any capability starts with fs:write
        if not any(p.startswith("fs:write") for p in getattr(ctx, "capabilities", [])):
            return {"success": False, "error": "Capability denied"}
        try:
            file_path = Path(path).expanduser()
            if self.workspace_root is not None:
                if not file_path.is_absolute():
                    file_path = self.workspace_root / file_path
                # Resolve the parent so '..' cannot escape the workspace even
                # when the target file does not exist yet.
                parent = file_path.parent.resolve()
                if not parent.is_relative_to(self.workspace_root):
                    return {"success": False, "error": "Path is outside the workspace"}
                file_path = parent / file_path.name
            elif not file_path.is_absolute():
                file_path = Path.cwd() / file_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": str(file_path), "bytes": len(content.encode("utf-8"))}
        except (OSError, UnicodeError, ValueError) as e:
            return {"success": False, "error": str(e)}
