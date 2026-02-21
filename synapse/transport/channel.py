"""
Communication Channel for orchestrator-node communication
"""

from typing import Optional
from synapse.transport.message import ExecutionRequest, ExecutionResult
import asyncio

class CommunicationChannel:
    """Communication channel between orchestrator and node"""
    
    def __init__(self):
        self._request_queue = asyncio.Queue()
        self._result_queue = asyncio.Queue()
    
    async def send_request(self, request: ExecutionRequest):
        """Send execution request"""
        await self._request_queue.put(request)
    
    async def receive_request(self) -> Optional[ExecutionRequest]:
        """Receive execution request"""
        try:
            return await asyncio.wait_for(self._request_queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            return None
    
    async def send_result(self, result: ExecutionResult):
        """Send execution result"""
        await self._result_queue.put(result)
    
    async def receive_result(self) -> Optional[ExecutionResult]:
        """Receive execution result"""
        try:
            return await asyncio.wait_for(self._result_queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            return None
