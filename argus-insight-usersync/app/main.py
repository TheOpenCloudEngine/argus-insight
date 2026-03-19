"""Argus Insight UserSync - Standalone batch job entry point.

Synchronizes users and groups from external sources (LDAP/Unix/File)
to Apache Ranger Admin. Designed to run as a daily cron/systemd timer job.

Usage:
    argus-insight-usersync
    argus-insight-usersync --config-yaml /path/to/config.yml
    argus-insight-usersync --config-yaml config.yml --config-properties config.properties
    argus-insight-usersync --dry-run
    python -m app.main
"""

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="argus-insight-usersync",
        description="Sync users and groups from LDAP/Unix/File to Apache Ranger Admin",
    )
    parser.add_argument(
        "--config-yaml",
        dest="config_yaml",
        help="Path to YAML config file (config.yml)",
    )
    parser.add_argument(
        "--config-properties",
        dest="config_properties",
        help="Path to properties variable file (config.properties)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from source and log what would be synced without modifying Ranger",
    )
    return parser.parse_args()


def run_dry(source_type: str) -> None:
    """Execute a dry run: fetch from source and report without syncing."""
    from app.core.config import settings
    from app.source.base import SyncSource

    def _create_source() -> SyncSource:
        if source_type == "ldap":
            from app.source.ldap_source import LdapSource

            return LdapSource()
        elif source_type == "file":
            from app.source.file_source import FileSource

            return FileSource()
        else:
            from app.source.unix_source import UnixSource

            return UnixSource()

    source = _create_source()
    users = source.get_users()
    groups = source.get_groups()

    logger.info("=== DRY RUN RESULTS ===")
    logger.info("Source: %s", source_type)
    logger.info("Ranger URL: %s", settings.ranger_url)
    logger.info("Users found: %d", len(users))
    for u in users:
        logger.info("  User: %s (groups: %s)", u.name, ", ".join(u.group_names))
    logger.info("Groups found: %d", len(groups))
    for g in groups:
        logger.info("  Group: %s (members: %s)", g.name, ", ".join(g.member_names))
    logger.info("=== END DRY RUN ===")


def main() -> None:
    """Main entry point for the usersync batch job."""
    args = parse_args()

    # Initialize config with CLI overrides (must happen before importing settings-dependent modules)
    if args.config_yaml or args.config_properties:
        from app.core.config import init_settings

        init_settings(
            yaml_path=args.config_yaml,
            properties_path=args.config_properties,
        )

    from app.core.config import settings
    from app.core.logging import setup_logging

    setup_logging()

    logger.info(
        "Argus Insight UserSync %s starting (source=%s, ranger=%s)",
        settings.app_version,
        settings.sync_source,
        settings.ranger_url,
    )

    if args.dry_run:
        run_dry(settings.sync_source)
        sys.exit(0)

    from app.sync.engine import SyncEngine

    engine = SyncEngine()
    result = engine.run()

    if result.success:
        logger.info("UserSync completed successfully")
        sys.exit(0)
    else:
        logger.error("UserSync completed with %d error(s)", len(result.errors))
        for err in result.errors:
            logger.error("  - %s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
