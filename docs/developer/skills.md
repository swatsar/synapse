# Skill Development Guide

**Protocol Version:** 1.0  
**Spec Version:** 3.1  

---

## Overview

Skills are the building blocks of Synapse's capabilities. This guide covers creating, testing, and deploying custom skills.

---

## Skill Architecture

### Skill Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  GENERATED  │────▶│   TESTED    │────▶│  VERIFIED   │
│  (Created)  │     │ (Auto Test) │     │ (Sec Scan)  │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  ARCHIVED   │◀────│  DEPRECATED │◀────│   ACTIVE    │
│  (Removed)  │     │ (Retired)   │     │ (In Use)    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Trust Levels

| Level | Description | Isolation |
|-------|-------------|-----------|
| `unverified` | New skill, not reviewed | Container |
| `verified` | Passed security scan | Subprocess |
| `trusted` | Reviewed and approved | Subprocess |
| `builtin` | Built-in skill | Main Process |

---

## Creating a New Skill

### Step 1: Define Manifest

Create `my_skill/manifest.yaml`:

```yaml
skill:
  name: "my_custom_skill"
  version: "1.0.0"
  description: "Custom skill for specific task"
  author: "your_name"

inputs:
  input_path:
    type: "string"
    description: "Path to input file"
    required: true
  output_path:
    type: "string"
    description: "Path to output file"
    required: true
  options:
    type: "object"
    description: "Additional options"
    required: false
    default: {}

outputs:
  result:
    type: "string"
    description: "Processing result"
  files_created:
    type: "array"
    description: "List of created files"

capabilities:
  - "fs:read:/workspace/**"
  - "fs:write:/workspace/output/**"

security:
  risk_level: 2
  requires_approval: false
  isolation_type: "subprocess"

resources:
  timeout_seconds: 60
  memory_mb: 256
  cpu_quota: 0.5

lifecycle:
  status: "generated"
  trust_level: "unverified"

metadata:
  protocol_version: "1.0"
  tags: ["file", "processing"]
  license: "MIT"
```

### Step 2: Implement Skill Class

Create `my_skill/skill.py`:

```python
"""
My Custom Skill

Protocol Version: 1.0
"""
from typing import Dict, Any, Optional
from skills.base import BaseSkill, SkillManifest, SkillResult
from core.models import ExecutionContext


class MyCustomSkill(BaseSkill):
    """
    Custom skill for processing files.
    
    Protocol Version: 1.0
    """
    
    # Skill manifest
    manifest = SkillManifest(
        name="my_custom_skill",
        version="1.0.0",
        description="Custom skill for specific task",
        author="your_name",
        required_capabilities=[
            "fs:read:/workspace/**",
            "fs:write:/workspace/output/**"
        ],
        risk_level=2,
        isolation_type="subprocess",
        timeout_seconds=60,
        protocol_version="1.0"  # Required
    )
    
    async def execute(
        self, 
        context: ExecutionContext, 
        **kwargs
    ) -> SkillResult:
        """
        Execute the skill.
        
        Args:
            context: Execution context with capabilities and resources
            **kwargs: Skill-specific arguments
            
        Returns:
            SkillResult with success status and outputs
        """
        # Step 1: Validate inputs
        input_path = kwargs.get('input_path')
        output_path = kwargs.get('output_path')
        options = kwargs.get('options', {})
        
        if not input_path:
            return SkillResult(
                success=False,
                error="input_path is required",
                metrics={}
            )
        
        # Step 2: Check capabilities (CRITICAL)
        if not await self._check_capabilities(context):
            return SkillResult(
                success=False,
                error="Missing required capabilities",
                metrics={}
            )
        
        # Step 3: Check resource limits
        if not await self._check_resources(context):
            return SkillResult(
                success=False,
                error="Resource limits exceeded",
                metrics={}
            )
        
        try:
            # Step 4: Read input file
            content = await self._read_file(context, input_path)
            
            # Step 5: Process content
            processed = await self._process(content, options)
            
            # Step 6: Write output
            if output_path:
                await self._write_file(context, output_path, processed)
            
            # Step 7: Return success result
            return SkillResult(
                success=True,
                result={
                    'result': processed,
                    'files_created': [output_path] if output_path else []
                },
                metrics={
                    'input_size_bytes': len(content),
                    'output_size_bytes': len(processed),
                    'protocol_version': '1.0'
                }
            )
            
        except Exception as e:
            # Step 8: Handle errors gracefully
            return SkillResult(
                success=False,
                error=str(e),
                metrics={
                    'error_type': type(e).__name__,
                    'protocol_version': '1.0'
                }
            )
    
    async def _check_capabilities(self, context: ExecutionContext) -> bool:
        """Check if required capabilities are present."""
        required = self.manifest.required_capabilities
        available = context.capabilities
        
        for cap in required:
            if not self._matches_capability(cap, available):
                return False
        
        return True
    
    async def _check_resources(self, context: ExecutionContext) -> bool:
        """Check if resources are within limits."""
        limits = context.resource_limits
        
        # Check timeout
        if self.manifest.timeout_seconds > limits.cpu_seconds:
            return False
        
        # Check memory
        if self.manifest.memory_mb > limits.memory_mb:
            return False
        
        return True
    
    async def _read_file(
        self, 
        context: ExecutionContext, 
        path: str
    ) -> str:
        """Read file content."""
        import aiofiles
        
        async with aiofiles.open(path, 'r') as f:
            return await f.read()
    
    async def _write_file(
        self, 
        context: ExecutionContext, 
        path: str, 
        content: str
    ) -> None:
        """Write content to file."""
        import aiofiles
        import os
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        async with aiofiles.open(path, 'w') as f:
            await f.write(content)
    
    async def _process(
        self, 
        content: str, 
        options: Dict[str, Any]
    ) -> str:
        """Process the content."""
        # Implement your processing logic here
        return content.upper()  # Example: convert to uppercase
    
    def _matches_capability(
        self, 
        required: str, 
        available: list
    ) -> bool:
        """Check if required capability matches available."""
        # Simple matching - implement glob matching if needed
        return required in available
```

### Step 3: Write Tests

Create `my_skill/tests/test_skill.py`:

```python
"""
Tests for My Custom Skill

Protocol Version: 1.0
"""
import pytest
import tempfile
import os
from pathlib import Path

from skills.my_custom_skill import MyCustomSkill
from core.models import ExecutionContext, ResourceLimits


@pytest.mark.phase4
@pytest.mark.asyncio
async def test_skill_basic_execution(test_context, test_workspace):
    """Test basic skill execution."""
    # Setup
    skill = MyCustomSkill()
    input_file = test_workspace / "input.txt"
    output_file = test_workspace / "output.txt"
    
    input_file.write_text("hello world")
    
    # Execute
    result = await skill.execute(
        test_context,
        input_path=str(input_file),
        output_path=str(output_file)
    )
    
    # Verify
    assert result.success == True
    assert result.result['result'] == "HELLO WORLD"
    assert output_file.exists()


@pytest.mark.phase4
@pytest.mark.asyncio
async def test_skill_missing_input(test_context):
    """Test skill with missing input."""
    skill = MyCustomSkill()
    
    result = await skill.execute(
        test_context,
        output_path="/tmp/output.txt"
    )
    
    assert result.success == False
    assert "input_path is required" in result.error


@pytest.mark.phase4
@pytest.mark.asyncio
async def test_skill_capability_check(test_context):
    """Test capability validation."""
    skill = MyCustomSkill()
    
    # Remove capabilities
    test_context.capabilities = []
    
    result = await skill.execute(
        test_context,
        input_path="/tmp/input.txt"
    )
    
    assert result.success == False
    assert "Missing required capabilities" in result.error


@pytest.mark.phase4
@pytest.mark.asyncio
async def test_skill_protocol_version(test_context, test_workspace):
    """Test protocol version is included."""
    skill = MyCustomSkill()
    
    input_file = test_workspace / "input.txt"
    input_file.write_text("test")
    
    result = await skill.execute(
        test_context,
        input_path=str(input_file)
    )
    
    assert result.metrics.get('protocol_version') == "1.0"
```

### Step 4: Create Package Structure

```
my_skill/
├── __init__.py
├── skill.py           # Main skill implementation
├── manifest.yaml      # Skill manifest
├── tests/
│   ├── __init__.py
│   └── test_skill.py
└── README.md
```

---

## Skill Manifest Reference

### Required Fields

```yaml
skill:
  name: string           # Unique skill name
  version: string        # Semantic version
  description: string    # Brief description
  author: string         # Author name

inputs:                  # Input parameters
  param_name:
    type: string         # string, integer, boolean, object, array
    description: string
    required: boolean
    default: any         # Optional default value

outputs:                 # Output structure
  output_name:
    type: string
    description: string

capabilities:            # Required capabilities
  - "capability:pattern"

security:
  risk_level: int        # 1-5
  requires_approval: bool
  isolation_type: string # main_process, subprocess, container

resources:
  timeout_seconds: int
  memory_mb: int
  cpu_quota: float

lifecycle:
  status: string         # generated, tested, verified, active, deprecated, archived
  trust_level: string    # unverified, verified, trusted, builtin

metadata:
  protocol_version: "1.0"  # Required
  tags: [string]
  license: string
```

---

## Security Requirements

### Dangerous Patterns (Forbidden)

```python
# ❌ FORBIDDEN
import os
os.system("command")

import subprocess
subprocess.Popen("command", shell=True)

eval("code")
exec("code")

import pickle
pickle.load(file)

import yaml
yaml.load(file)  # Use yaml.safe_load instead
```

### Safe Alternatives

```python
# ✅ SAFE
import subprocess
result = subprocess.run(
    ["command", "arg1"],
    capture_output=True,
    text=True,
    timeout=30
)

import yaml
data = yaml.safe_load(file)

import json
data = json.load(file)
```

### Security Scan

All skills undergo AST analysis:

```bash
# Run security scan
synapse skills scan my_skill/

# Output:
# ✅ No dangerous imports found
# ✅ No eval/exec usage
# ✅ Capabilities properly declared
# ✅ Protocol version present
```

---

## Testing Skills

### Unit Tests

```bash
# Run skill tests
pytest tests/skills/my_skill/ -v

# With coverage
pytest tests/skills/my_skill/ --cov=my_skill
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_skill_integration():
    """Integration test with full system."""
    from core.orchestrator import Orchestrator
    
    orchestrator = Orchestrator()
    
    result = await orchestrator.execute_skill(
        skill_name="my_custom_skill",
        inputs={
            "input_path": "/workspace/test.txt"
        }
    )
    
    assert result.success == True
```

### Performance Tests

```python
@pytest.mark.performance
@pytest.mark.asyncio
async def test_skill_performance():
    """Test skill performance."""
    import time
    
    skill = MyCustomSkill()
    
    start = time.perf_counter()
    result = await skill.execute(context, input_path="large_file.txt")
    elapsed = time.perf_counter() - start
    
    assert elapsed < 5.0  # Must complete in 5 seconds
```

---

## Deploying Skills

### Local Deployment

```bash
# Copy to skills directory
cp -r my_skill/ ~/.local/share/synapse/skills/

# Register skill
synapse skills register my_skill/

# Verify
synapse skills list
```

### Docker Deployment

```bash
# Mount skills directory
docker run -v ./my_skill:/app/skills/my_skill synapse/core

# Or in docker-compose.yml
volumes:
  - ./skills:/app/skills
```

### Approval Workflow

1. **Submit Skill:**
   ```bash
   synapse skills submit my_skill/
   ```

2. **Automatic Tests:** Run automatically

3. **Security Scan:** AST analysis

4. **Human Approval:** Via GUI or CLI
   ```bash
   synapse skills approve my_custom_skill
   ```

5. **Skill Active:** Ready for use

---

## Best Practices

### 1. Always Check Capabilities

```python
async def execute(self, context, **kwargs):
    if not await self._check_capabilities(context):
        return SkillResult(success=False, error="Missing capabilities")
```

### 2. Include Protocol Version

```python
return SkillResult(
    success=True,
    result={...},
    metrics={'protocol_version': '1.0'}
)
```

### 3. Handle Errors Gracefully

```python
try:
    result = await risky_operation()
except SpecificError as e:
    return SkillResult(success=False, error=str(e))
```

### 4. Respect Resource Limits

```python
if context.resource_limits.memory_mb < required_memory:
    return SkillResult(success=False, error="Insufficient memory")
```

### 5. Log Important Actions

```python
await context.logger.info(
    f"Processing file: {input_path}",
    extra={'protocol_version': '1.0'}
)
```

---

## Troubleshooting

### "Capability denied"
- Check required capabilities in manifest
- Grant capabilities via GUI or API

### "Timeout exceeded"
- Increase timeout_seconds in manifest
- Optimize skill implementation

### "Security scan failed"
- Remove dangerous imports
- Use safe alternatives
- Check for eval/exec usage

---

**Protocol Version:** 1.0  
**Need Help?** Check [API Reference](api.md) or open an issue on GitHub.
