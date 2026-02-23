"""Web Server - Minimal control plane."""
from typing import Dict, Any, Optional
from dataclasses import dataclass

PROTOCOL_VERSION: str = "1.0"


@dataclass
class WebServerConfig:
    """Web server configuration."""
    host: str = "0.0.0.0"  # nosec B104
    port: int = 8080
    debug: bool = False
    protocol_version: str = PROTOCOL_VERSION


class WebServer:
    """Minimal web server for control plane."""
    protocol_version: str = PROTOCOL_VERSION
    
    def __init__(self, config: WebServerConfig = None, dashboard=None):
        self.config = config or WebServerConfig()
        self._dashboard = dashboard
        self._running = False
    
    def start(self) -> None:
        """Start the web server."""
        self._running = True
    
    def stop(self) -> None:
        """Stop the web server."""
        self._running = False
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        """Get server status."""
        return {
            "running": self._running,
            "host": self.config.host,
            "port": self.config.port,
            "protocol_version": PROTOCOL_VERSION
        }
