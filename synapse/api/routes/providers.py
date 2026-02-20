"""LLM Providers API Routes.

Protocol Version: 1.0
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime

PROTOCOL_VERSION: str = "1.0"

router = APIRouter()

# In-memory storage (will be replaced with database)
providers_db: Dict[str, Dict] = {}


# === Models ===

class ProviderCreate(BaseModel):
    name: str
    api_key: str
    models: List[str] = []
    priority: int = 3
    base_url: Optional[str] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    priority: Optional[int] = None
    base_url: Optional[str] = None


class PriorityUpdate(BaseModel):
    priority: int


# === Service (will be moved to services/) ===

class ProviderService:
    """Provider service for business logic."""
    
    def __init__(self):
        self.providers = providers_db
    
    def list_providers(self) -> List[Dict]:
        return list(self.providers.values())
    
    def get_provider(self, provider_id: str) -> Optional[Dict]:
        return self.providers.get(provider_id)
    
    def create_provider(self, data: ProviderCreate) -> Dict:
        provider_id = data.name.lower().replace(" ", "_")
        provider = {
            "id": provider_id,
            "name": data.name,
            "api_key": "***",  # Never expose API key
            "models": data.models,
            "priority": data.priority,
            "base_url": data.base_url,
            "created_at": datetime.utcnow().isoformat(),
            "protocol_version": PROTOCOL_VERSION
        }
        self.providers[provider_id] = provider
        return provider
    
    def update_provider(self, provider_id: str, data: ProviderUpdate) -> Optional[Dict]:
        if provider_id not in self.providers:
            return None
        provider = self.providers[provider_id]
        update_data = data.model_dump(exclude_unset=True)
        provider.update(update_data)
        provider["updated_at"] = datetime.utcnow().isoformat()
        return provider
    
    def delete_provider(self, provider_id: str) -> bool:
        if provider_id in self.providers:
            del self.providers[provider_id]
            return True
        return False
    
    def test_connection(self, provider_id: str) -> Dict:
        # Simulate connection test
        if provider_id not in self.providers:
            return {"success": False, "error": "Provider not found"}
        return {"success": True, "latency_ms": 150, "model": "test"}
    
    def list_models(self, provider_id: str) -> List[Dict]:
        if provider_id not in self.providers:
            return []
        return [
            {"id": m, "name": m, "context_window": 128000}
            for m in self.providers[provider_id].get("models", [])
        ]
    
    def set_priority(self, provider_id: str, priority: int) -> Optional[Dict]:
        if provider_id not in self.providers:
            return None
        self.providers[provider_id]["priority"] = priority
        return self.providers[provider_id]


provider_service = ProviderService()


# === Routes ===

@router.get("")
async def list_providers():
    """List all LLM providers."""
    providers = provider_service.list_providers()
    return {
        "providers": providers,
        "protocol_version": PROTOCOL_VERSION
    }


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    """Get a specific provider."""
    provider = provider_service.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("", status_code=201)
async def create_provider(data: ProviderCreate):
    """Create a new provider."""
    provider = provider_service.create_provider(data)
    return provider


@router.put("/{provider_id}")
async def update_provider(provider_id: str, data: ProviderUpdate):
    """Update a provider."""
    provider = provider_service.update_provider(provider_id, data)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(provider_id: str):
    """Delete a provider."""
    success = provider_service.delete_provider(provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")


@router.post("/{provider_id}/test")
async def test_provider_connection(provider_id: str):
    """Test provider connection."""
    result = provider_service.test_connection(provider_id)
    return result


@router.get("/{provider_id}/models")
async def list_provider_models(provider_id: str):
    """List models for a provider."""
    models = provider_service.list_models(provider_id)
    return {"models": models, "protocol_version": PROTOCOL_VERSION}


@router.patch("/{provider_id}/priority")
async def set_provider_priority(provider_id: str, data: PriorityUpdate):
    """Set provider priority."""
    provider = provider_service.set_priority(provider_id, data.priority)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider
