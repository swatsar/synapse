#!/usr/bin/env python3
"""Synapse Agent Platform - Main Entry Point.

from __future__ import annotations

Protocol Version: 1.0
Spec Version: 3.1
"""
import argparse
import asyncio
import logging
import os
import sys
from typing import Final, Optional

PROTOCOL_VERSION: Final[str] = "1.0"
SPEC_VERSION: Final[str] = "3.1"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("synapse")


def print_banner() -> None:
    """Print startup banner."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ███████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗║
║   ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝║
║   ███████╗ ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗  ║
║   ╚════██║  ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝  ║
║   ███████║   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗║
║   ╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝║
║                                                              ║
║   Universal Autonomous Agent Platform                        ║
║   Protocol v{PROTOCOL_VERSION} | Spec v{SPEC_VERSION}                              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


async def run_web_ui(host: str = "0.0.0.0", port: int = 8080) -> None:  # nosec B104
    """Run the Web UI server."""
    import uvicorn

    from synapse.api.app import app

    logger.info(f"Starting Web UI on http://{host}:{port}")
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_agent(mode: str = "local") -> None:
    """Run the agent in specified mode."""
    from synapse.core.determinism import (
        DeterministicIDGenerator,
        DeterministicSeedManager,
    )
    from synapse.core.orchestrator import Orchestrator
    from synapse.core.security import SecurityManager
    from synapse.memory.store import MemoryStore

    logger.info(f"Starting Synapse Agent in {mode} mode")

    # Initialize components
    seed_manager = DeterministicSeedManager()
    id_generator = DeterministicIDGenerator()
    security = SecurityManager()
    memory = MemoryStore()
    Orchestrator(seed_manager, id_generator, memory, security)

    logger.info("Agent initialized successfully")
    logger.info("Waiting for tasks...")

    # Keep running
    while True:
        await asyncio.sleep(1)


async def run_full(host: str = "0.0.0.0", api_port: int = 8000, web_port: int = 8080) -> None:  # nosec B104
    """Run both API and Web UI."""
    import uvicorn

    from synapse.api.app import app

    print_banner()
    logger.info("Starting Synapse Platform")
    logger.info(f"API Server: http://{host}:{api_port}")
    logger.info(f"Web Dashboard: http://{host}:{web_port}")
    logger.info(f"Health Check: http://{host}:{api_port}/health")

    # Run API server (which also serves the dashboard at /)
    config = uvicorn.Config(
        app,
        host=host,
        port=api_port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Synapse Agent Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--mode",
        choices=["local", "docker", "distributed"],
        default="local",
        help="Execution mode"
    )
    parser.add_argument(
        "--web-ui",
        action="store_true",
        help="Start Web UI dashboard"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",  # nosec B104
        help="Host to bind to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API port"
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="Web UI port"
    )

    args = parser.parse_args()

    # Set environment
    os.environ["MODE"] = args.mode
    os.environ["PROTOCOL_VERSION"] = PROTOCOL_VERSION
    os.environ["SPEC_VERSION"] = SPEC_VERSION

    try:
        if args.web_ui or args.mode == "docker":
            # Run full platform with Web UI
            asyncio.run(run_full(
                host=args.host,
                api_port=args.port,
                web_port=args.web_port
            ))
        else:
            # Run agent only
            print_banner()
            asyncio.run(run_agent(mode=args.mode))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        print("""
👋 Synapse stopped. Goodbye!""")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
