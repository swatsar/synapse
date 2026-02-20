# Plugin Development Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## Overview

Plugins extend Synapse's functionality with custom connectors, processors, and integrations. This guide covers creating, testing, and deploying plugins.

---

## Plugin Architecture

### Plugin Types

| Type | Description | Example |
|------|-------------|----------|
| `connector` | External service integration | Slack, Email, Database |
| `processor` | Data transformation | PDF parser, Image analyzer |
| `llm_provider` | LLM backend | Custom model, Local LLM |
| `memory_backend` | Storage backend | Custom vector DB |
| `skill_pack` | Collection of skills | Data analysis pack |

### Plugin Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DISCOVERED │────▶│   SCANNED   │────▶│   LOADED    │
│  (Found)    │     │ (Security)  │     │ (Active)    │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                     ┌─────────────┐     ┌─────────────┐
                     │  UNLOADED   │◀────│   RUNNING   │
                     │ (Stopped)   │     │ (In Use)    │
                     └─────────────┘     └─────────────┘
```

---

## Creating a Plugin

### Plugin Structure

```
my-plugin/
├── manifest.json       # Plugin metadata
├── main.py             # Plugin entry point
├── requirements.txt    # Dependencies
├── config.yaml         # Default configuration
├── tests/
│   ├── __init__.py
│   └── test_plugin.py
└── README.md
```

### manifest.json

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Custom plugin for Synapse",
  "author": "your_name",
  "type": "connector",
  
  "entry_point": "main.py",
  "class_name": "MyPlugin",
  
  "required_capabilities": [
    "network:http:*.example.com"
  ],
  
  "provides": {
    "connectors": ["my_connector"],
    "skills": ["my_skill"]
  },
  
  "dependencies": {
    "python": ">=3.11",
    "packages": ["aiohttp>=3.8.0"]
  },
  
  "configuration": {
    "api_key": {
      "type": "string",
      "required": true,
      "secret": true
    },
    "timeout": {
      "type": "integer",
      "default": 30
    }
  },
  
  "security": {
    "risk_level": 2,
    "permissions": ["network:http"]
  },
  
  "protocol_version": "1.0"
}
```

### main.py

```python
"""
My Custom Plugin

Protocol Version: 1.0
"""
from typing import Dict, Any, Optional
from synapse.plugins import BasePlugin, PluginContext
from synapse.core.models import PROTOCOL_VERSION


class MyPlugin(BasePlugin):
    """
    Custom plugin implementation.
    
    Protocol Version: 1.0
    """
    
    PROTOCOL_VERSION: str = "1.0"
    
    def __init__(self):
        super().__init__()
        self.name = "my-plugin"
        self.version = "1.0.0"
        self._config: Dict[str, Any] = {}
        self._initialized = False
    
    async def initialize(self, context: PluginContext) -> bool:
        """
        Initialize the plugin.
        
        Args:
            context: Plugin context with configuration
            
        Returns:
            True if initialization successful
        """
        try:
            # Load configuration
            self._config = context.config
            
            # Validate required settings
            if 'api_key' not in self._config:
                raise ValueError("api_key is required")
            
            # Initialize resources
            # ... custom initialization code ...
            
            self._initialized = True
            
            # Log initialization
            await context.logger.info(
                f"Plugin {self.name} initialized",
                extra={'protocol_version': self.PROTOCOL_VERSION}
            )
            
            return True
            
        except Exception as e:
            await context.logger.error(
                f"Plugin initialization failed: {e}",
                extra={'protocol_version': self.PROTOCOL_VERSION}
            )
            return False
    
    async def shutdown(self, context: PluginContext) -> bool:
        """
        Shutdown the plugin.
        
        Args:
            context: Plugin context
            
        Returns:
            True if shutdown successful
        """
        try:
            # Cleanup resources
            # ... custom cleanup code ...
            
            self._initialized = False
            
            await context.logger.info(
                f"Plugin {self.name} shutdown",
                extra={'protocol_version': self.PROTOCOL_VERSION}
            )
            
            return True
            
        except Exception as e:
            await context.logger.error(
                f"Plugin shutdown failed: {e}",
                extra={'protocol_version': self.PROTOCOL_VERSION}
            )
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check plugin health.
        
        Returns:
            Health status dict
        """
        return {
            'healthy': self._initialized,
            'name': self.name,
            'version': self.version,
            'protocol_version': self.PROTOCOL_VERSION
        }
    
    # Plugin-specific methods
    
    async def connect(self, endpoint: str) -> bool:
        """Connect to external service."""
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        
        # Implementation
        return True
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data."""
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        
        # Implementation
        return {
            'processed': True,
            'protocol_version': self.PROTOCOL_VERSION
        }
```

---

## Plugin Types

### Connector Plugin

```python
from synapse.plugins import ConnectorPlugin
from synapse.connectors.base import BaseConnector

class MyConnector(BaseConnector):
    """Custom connector implementation."""
    
    async def connect(self) -> bool:
        """Establish connection."""
        pass
    
    async def disconnect(self) -> bool:
        """Close connection."""
        pass
    
    async def send(self, message: dict) -> bool:
        """Send message."""
        pass
    
    async def receive(self) -> list:
        """Receive messages."""
        pass


class MyConnectorPlugin(ConnectorPlugin):
    """Connector plugin."""
    
    def __init__(self):
        super().__init__()
        self.connector_class = MyConnector
```

### LLM Provider Plugin

```python
from synapse.plugins import LLMProviderPlugin
from synapse.llm.base import BaseLLMProvider

class MyLLMProvider(BaseLLMProvider):
    """Custom LLM provider."""
    
    async def generate(
        self,
        prompt: str,
        **kwargs
    ) -> str:
        """Generate response."""
        pass
    
    async def embed(
        self,
        text: str
    ) -> list:
        """Generate embedding."""
        pass


class MyLLMPlugin(LLMProviderPlugin):
    """LLM provider plugin."""
    
    def __init__(self):
        super().__init__()
        self.provider_class = MyLLMProvider
```

### Memory Backend Plugin

```python
from synapse.plugins import MemoryBackendPlugin
from synapse.memory.base import BaseMemoryStore

class MyMemoryStore(BaseMemoryStore):
    """Custom memory store."""
    
    async def store(self, entry: dict) -> str:
        """Store entry."""
        pass
    
    async def recall(self, query: dict) -> list:
        """Recall entries."""
        pass
    
    async def delete(self, entry_id: str) -> bool:
        """Delete entry."""
        pass


class MyMemoryPlugin(MemoryBackendPlugin):
    """Memory backend plugin."""
    
    def __init__(self):
        super().__init__()
        self.store_class = MyMemoryStore
```

---

## Configuration

### config.yaml

```yaml
# Plugin configuration
my_plugin:
  api_key: "${MY_PLUGIN_API_KEY}"
  timeout: 30
  retry_count: 3
  
  # Advanced settings
  advanced:
    cache_enabled: true
    cache_ttl: 3600
```

### Environment Variables

```bash
# .env
MY_PLUGIN_API_KEY=your_api_key_here
```

---

## Security Requirements

### Forbidden Patterns

```python
# ❌ FORBIDDEN
import os
os.system("command")

eval("code")
exec("code")

import pickle
pickle.loads(data)

import subprocess
subprocess.call("command", shell=True)
```

### Security Scan

All plugins undergo security scanning:

```bash
synapse plugins scan my-plugin/

# Output:
# ✅ No dangerous imports
# ✅ No eval/exec usage
# ✅ Capabilities declared
# ✅ Protocol version present
```

### Capability Declaration

```json
{
  "required_capabilities": [
    "network:http:api.example.com",
    "fs:read:/data/**"
  ]
}
```

---

## Testing Plugins

### Unit Tests

```python
"""
Tests for My Plugin

Protocol Version: 1.0
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from my_plugin import MyPlugin
from synapse.plugins import PluginContext


@pytest.mark.asyncio
async def test_plugin_initialization():
    """Test plugin initialization."""
    plugin = MyPlugin()
    context = PluginContext(
        config={'api_key': 'test_key'},
        logger=MagicMock()
    )
    
    result = await plugin.initialize(context)
    
    assert result == True
    assert plugin._initialized == True


@pytest.mark.asyncio
async def test_plugin_shutdown():
    """Test plugin shutdown."""
    plugin = MyPlugin()
    context = PluginContext(
        config={'api_key': 'test_key'},
        logger=MagicMock()
    )
    
    await plugin.initialize(context)
    result = await plugin.shutdown(context)
    
    assert result == True
    assert plugin._initialized == False


@pytest.mark.asyncio
async def test_plugin_health_check():
    """Test health check."""
    plugin = MyPlugin()
    context = PluginContext(
        config={'api_key': 'test_key'},
        logger=MagicMock()
    )
    
    await plugin.initialize(context)
    health = await plugin.health_check()
    
    assert health['healthy'] == True
    assert health['protocol_version'] == "1.0"


@pytest.mark.asyncio
async def test_plugin_missing_config():
    """Test missing configuration."""
    plugin = MyPlugin()
    context = PluginContext(
        config={},  # Missing api_key
        logger=MagicMock()
    )
    
    result = await plugin.initialize(context)
    
    assert result == False
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_plugin_integration():
    """Integration test with Synapse."""
    from synapse.core.orchestrator import Orchestrator
    
    orchestrator = Orchestrator()
    
    # Load plugin
    await orchestrator.load_plugin('my-plugin')
    
    # Use plugin
    result = await orchestrator.use_connector(
        'my_connector',
        action='send',
        data={'message': 'test'}
    )
    
    assert result['success'] == True
```

---

## Deploying Plugins

### Local Deployment

```bash
# Copy to plugins directory
cp -r my-plugin/ ~/.local/share/synapse/plugins/

# Register plugin
synapse plugins register my-plugin/

# Verify
synapse plugins list
```

### Docker Deployment

```yaml
# docker-compose.yml
services:
  synapse:
    volumes:
      - ./plugins:/app/plugins
```

### Approval Workflow

1. **Submit Plugin:**
   ```bash
   synapse plugins submit my-plugin/
   ```

2. **Security Scan:** Automatic

3. **Human Approval:** Via GUI

4. **Plugin Active:** Ready for use

---

## Plugin API Reference

### BasePlugin Methods

| Method | Description |
|--------|-------------|
| `initialize(context)` | Initialize plugin |
| `shutdown(context)` | Shutdown plugin |
| `health_check()` | Check health |
| `get_config()` | Get configuration |
| `set_config(config)` | Set configuration |

### PluginContext

| Attribute | Type | Description |
|-----------|------|-------------|
| `config` | dict | Plugin configuration |
| `logger` | Logger | Logging instance |
| `event_bus` | EventBus | Event system |
| `capabilities` | list | Available capabilities |

---

## Best Practices

### 1. Always Include Protocol Version

```python
self.PROTOCOL_VERSION = "1.0"
```

### 2. Handle Errors Gracefully

```python
try:
    result = await risky_operation()
except Exception as e:
    await context.logger.error(f"Operation failed: {e}")
    return False
```

### 3. Validate Configuration

```python
if 'api_key' not in self._config:
    raise ValueError("api_key is required")
```

### 4. Implement Health Check

```python
async def health_check(self) -> Dict[str, Any]:
    return {
        'healthy': self._initialized,
        'protocol_version': self.PROTOCOL_VERSION
    }
```

### 5. Clean Up Resources

```python
async def shutdown(self, context: PluginContext) -> bool:
    # Close connections
    # Release resources
    # Clear caches
    return True
```

---

## Troubleshooting

### "Plugin not found"
- Check plugin directory
- Verify manifest.json exists
- Check plugin name matches

### "Security scan failed"
- Remove dangerous imports
- Check for eval/exec usage
- Declare all capabilities

### "Initialization failed"
- Check configuration
- Verify dependencies installed
- Check logs for errors

---

**Protocol Version:** 1.0  
**Need Help?** Check [API Reference](api.md) or open an issue on GitHub.
