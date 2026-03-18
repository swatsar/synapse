#!/usr/bin/env python3
"""Synapse UI Configurator and Entry Point.

Provides configuration interface for Synapse platform.
"""
import sys
import argparse
import logging
import asyncio

from synapse.ui.web.server import WebServer
from synapse.ui.web.dashboard import Dashboard


PROTOCOL_VERSION: str = "1.0"
SPEC_VERSION: str = "3.1"


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("synapse-ui-configurator")


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   Synapse UI Configurator                                    ║
║   Protocol v{} | Spec v{}                              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""".format(PROTOCOL_VERSION, SPEC_VERSION))


async def run_configurator_server(host: str = "0.0.0.0", port: int = 8080):  # nosec B104
    """Run the UI configurator server."""
    logger.info(f"Starting Synapse UI Configurator on http://{host}:{port}")

    # Initialize components
    dashboard = Dashboard()
    server = WebServer(dashboard=dashboard)

    try:
        server.start()
        logger.info("UI Configurator server started successfully")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down UI Configurator...")
        server.stop()
    except Exception as e:
        logger.error(f"Error: {e}")
        server.stop()
        sys.exit(1)


def main():
    """Main entry point for Synapse UI Configurator."""
    parser = argparse.ArgumentParser(
        description="Synapse UI Configurator - Configuration interface for Synapse platform"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",  # nosec B104
        help="Host to bind to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version information"
    )

    args = parser.parse_args()

    if args.version:
        print(f"Synapse UI Configurator v{PROTOCOL_VERSION}")
        print(f"Protocol: {PROTOCOL_VERSION}, Spec: {SPEC_VERSION}")
        return

    print_banner()

    try:
        asyncio.run(run_configurator_server(args.host, args.port))
    except KeyboardInterrupt:
        print("\n👋 UI Configurator stopped. Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
