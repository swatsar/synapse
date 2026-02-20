PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

import os
from synapse.core.models import ExecutionContext


PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

class ReadFileSkill:
    async def execute(self, ctx: ExecutionContext, path: str):
        # Simple capability check – allow if any capability starts with fs:read
        if not any(p.startswith("fs:read") for p in ctx.capabilities):
            return {"success": False, "error": "Capability denied"}
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
