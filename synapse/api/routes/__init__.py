"""API Routes Module.

Protocol Version: 1.0
"""
from fastapi import APIRouter
from synapse.api.routes import providers, agents, settings

PROTOCOL_VERSION: str = "1.0"

api_router = APIRouter()

# Include all route modules
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
