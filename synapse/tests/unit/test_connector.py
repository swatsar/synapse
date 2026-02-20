PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"

PROTOCOL_VERSION: str = "1.0"
import pytest
from synapse.connectors.base.connector import Connector

class EchoConnector(Connector):
    def __init__(self):
        self.events = []
    async def handle_event(self, event):
        self.events.append(event)

@pytest.mark.asyncio
async def test_echo_connector():
    conn = EchoConnector()
    await conn.handle_event({"type": "msg", "payload": "hello"})
    assert conn.events == [{"type": "msg", "payload": "hello"}]
