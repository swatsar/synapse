import os
from synapse.core.models import ExecutionContext


PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

class WriteFileSkill:
    async def execute(self, ctx: ExecutionContext, path: str, content: str):
        # Simple capability check – allow if any capability starts with fs:write
        if not any(p.startswith("fs:write") for p in ctx.capabilities):
            return {"success": False, "error": "Capability denied"}
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
