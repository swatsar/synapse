PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

import aiofiles
"""File operations skill.
PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"
"""
from typing import Any, Dict

# Simple async file read/write skills used by the orchestrator

async def read_file(path: str) -> Dict[str, Any]:
    async with aiofiles.open(path, mode='r') as f:
        content = await f.read()
    return {"content": content}

# Attach required attributes for the execution guard
read_file.trust_level = "trusted"
read_file.risk_level = 1

async def write_file(path: str, data: str) -> Dict[str, Any]:
    async with aiofiles.open(path, mode='w') as f:
        await f.write(data)
    return {"status": "ok"}

write_file.trust_level = "verified"
write_file.risk_level = 2
