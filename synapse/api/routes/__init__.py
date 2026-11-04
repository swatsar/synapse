"""API Routes Module.

Protocol Version: 1.0
"""
from fastapi import APIRouter

from synapse.api.routes import agents, providers, router, runtime_config, settings, tools_platform, training

PROTOCOL_VERSION: str = "1.0"

api_router = APIRouter()

# Include all route modules
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(runtime_config.router, prefix="/runtime-config", tags=["runtime-config"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(router.router, prefix="/router", tags=["router"])
api_router.include_router(tools_platform.router, prefix="/platform", tags=["platform"])
