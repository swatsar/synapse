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
from typing import Final

PROTOCOL_VERSION: Final[str] = "1.0"
SPEC_VERSION: Final[str] = "3.1"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("synapse")


def print_banner() -> None:
    """Print a startup banner that also works in legacy Windows consoles."""
    print(f"Synapse Agent Platform | Protocol v{PROTOCOL_VERSION} | Spec v{SPEC_VERSION}")


async def run_full(
    host: str = "127.0.0.1", api_port: int = 8000, *, require_api_key: bool = False,
) -> None:
    """Run the API and the Web Dashboard on one local server."""
    import uvicorn

    from synapse.api.app import app
    from synapse.api.middleware import LocalDesktopAccess, is_loopback_address

    local_access = not require_api_key and (host == "localhost" or is_loopback_address(host))
    if not local_access and not os.getenv("SYNAPSE_API_KEY", "").strip():
        raise ValueError("SYNAPSE_API_KEY is required for a protected or non-loopback listener")
    application = LocalDesktopAccess(app) if local_access else app

    print_banner()
    logger.info("API and Web Dashboard: http://%s:%s", host, api_port)
    logger.info("Health Check: http://%s:%s/health", host, api_port)
    config = uvicorn.Config(
        application, host=host, port=api_port, log_level="info", proxy_headers=not local_access,
    )
    await uvicorn.Server(config).serve()


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
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--web-ui",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: local computer only)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API and Web Dashboard port"
    )

    parser.add_argument(
        "--require-api-key", action="store_true",
        help="Require SYNAPSE_API_KEY even on the loopback listener",
    )

    args = parser.parse_args()

    os.environ["PROTOCOL_VERSION"] = PROTOCOL_VERSION
    os.environ["SPEC_VERSION"] = SPEC_VERSION

    try:
        asyncio.run(run_full(host=args.host, api_port=args.port, require_api_key=args.require_api_key))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception:
        logger.exception("Synapse failed to start")
        sys.exit(1)


if __name__ == "__main__":
    main()
