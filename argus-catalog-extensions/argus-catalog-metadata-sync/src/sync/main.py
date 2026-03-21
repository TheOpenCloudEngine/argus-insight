"""CLI entry point for Argus Catalog Metadata Sync.

Usage:
    metadata-sync                  # Start API server (default)
    metadata-sync --mode server    # Start API server
    metadata-sync --mode batch     # Run one-shot sync and exit
    metadata-sync --mode batch --platform hive  # Sync specific platform
"""

import argparse
import logging
import sys

from sync.core.catalog_client import CatalogClient
from sync.core.config import settings, init_settings
from sync.platforms.hive.sync import HiveMetastoreSync


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_server() -> None:
    """Start the FastAPI sync API server."""
    import uvicorn

    uvicorn.run(
        "sync.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


def run_batch(platform: str | None = None) -> int:
    """Run a one-shot sync and exit. Returns 0 on success, 1 on failure."""
    client = CatalogClient(settings)
    exit_code = 0

    platforms_to_sync = []
    if platform:
        platforms_to_sync = [platform]
    else:
        # Sync all enabled platforms
        if settings.hive_enabled:
            platforms_to_sync.append("hive")

    if not platforms_to_sync:
        logging.warning("No platforms enabled for sync")
        return 0

    for p in platforms_to_sync:
        if p == "hive":
            sync = HiveMetastoreSync(client, settings)
            logging.info("Starting batch sync for Hive Metastore")
            try:
                if not sync.connect():
                    logging.error("Failed to connect to Hive Metastore")
                    exit_code = 1
                    continue
                result = sync.sync()
                logging.info(
                    "Hive sync result: created=%d, updated=%d, failed=%d",
                    result.created, result.updated, result.failed,
                )
                if not result.success:
                    exit_code = 1
            finally:
                sync.disconnect()
        else:
            logging.warning("Unknown platform: %s", p)
            exit_code = 1

    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Argus Catalog Metadata Sync")
    parser.add_argument(
        "--mode",
        choices=["server", "batch"],
        default="server",
        help="Run mode: 'server' starts the API server, 'batch' runs sync once and exits",
    )
    parser.add_argument(
        "--platform",
        help="Platform to sync (batch mode only). If omitted, syncs all enabled platforms.",
    )
    parser.add_argument(
        "--config",
        help="Path to config directory containing config.yml and config.properties",
    )
    args = parser.parse_args()

    setup_logging()

    if args.config:
        init_settings(
            yaml_path=f"{args.config}/config.yml",
            properties_path=f"{args.config}/config.properties",
        )

    if args.mode == "server":
        run_server()
    elif args.mode == "batch":
        code = run_batch(args.platform)
        sys.exit(code)


if __name__ == "__main__":
    main()
