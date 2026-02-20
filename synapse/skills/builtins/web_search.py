# Dummy web search skill – returns a static response containing the queried URL
from synapse.core.models import ExecutionContext


PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

class WebSearchSkill:
    async def execute(self, ctx: ExecutionContext, query: str):
        # Capability check – placeholder
        if not any("net:http" in c for c in ctx.capabilities):
            return {"success": False, "error": "Network capability missing"}
        # Return a deterministic dummy response
        return {"success": True, "response": {"url": f"http://{query}"}}
