"""Host management CLI.

Usage:
    python -m app.hostmgr.cli <command> [options]

Commands:
    hostname get                          Show current hostname
    hostname set <name>                   Change hostname
    hostname validate                     Validate hostname consistency

    hosts read                            Read /etc/hosts
    hosts update <file>                   Update /etc/hosts (content from file or stdin)
    hosts backup                          Backup /etc/hosts

    resolv read                           Read /etc/resolv.conf
    resolv update <file>                  Update /etc/resolv.conf
    resolv backup                         Backup /etc/resolv.conf
    resolv nameservers                    List nameservers from /etc/resolv.conf
    resolv set-nameservers <ns1> [ns2..]  Set nameservers in /etc/resolv.conf
"""

import argparse
import asyncio
import json
import sys

from app.hostmgr import service


def _to_json(obj) -> str:
    """Convert a pydantic model to JSON string."""
    return json.dumps(obj.model_dump(), indent=2, ensure_ascii=False)


def _read_content(file_path: str | None) -> str:
    """Read content from a file path or stdin."""
    if file_path and file_path != "-":
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


# ---------------------------------------------------------------------------
# Hostname
# ---------------------------------------------------------------------------


def cmd_hostname_get(_args: argparse.Namespace) -> None:
    result = asyncio.run(service.get_hostname())
    print(_to_json(result))


def cmd_hostname_set(args: argparse.Namespace) -> None:
    result = asyncio.run(service.change_hostname(args.name))
    print(_to_json(result))
    if not result.success:
        sys.exit(1)


def cmd_hostname_validate(_args: argparse.Namespace) -> None:
    result = asyncio.run(service.validate_hostname())
    print(_to_json(result))
    if not result.is_consistent:
        sys.exit(1)


# ---------------------------------------------------------------------------
# /etc/hosts
# ---------------------------------------------------------------------------


def cmd_hosts_read(_args: argparse.Namespace) -> None:
    try:
        result = service.read_hosts_file()
        print(result.content)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_hosts_update(args: argparse.Namespace) -> None:
    content = _read_content(args.file)
    result = service.update_hosts_file(content)
    print(_to_json(result))
    if not result.success:
        sys.exit(1)


def cmd_hosts_backup(_args: argparse.Namespace) -> None:
    result = service.backup_hosts_file()
    print(_to_json(result))
    if not result.success:
        sys.exit(1)


# ---------------------------------------------------------------------------
# /etc/resolv.conf
# ---------------------------------------------------------------------------


def cmd_resolv_read(_args: argparse.Namespace) -> None:
    try:
        result = service.read_resolv_conf()
        print(result.content)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_resolv_update(args: argparse.Namespace) -> None:
    content = _read_content(args.file)
    result = service.update_resolv_conf(content)
    print(_to_json(result))
    if not result.success:
        sys.exit(1)


def cmd_resolv_backup(_args: argparse.Namespace) -> None:
    result = service.backup_resolv_conf()
    print(_to_json(result))
    if not result.success:
        sys.exit(1)


def cmd_resolv_nameservers(_args: argparse.Namespace) -> None:
    result = service.get_nameservers()
    print(_to_json(result))


def cmd_resolv_set_nameservers(args: argparse.Namespace) -> None:
    result = service.update_nameservers(args.nameservers)
    print(_to_json(result))
    if not result.success:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="argus-host",
        description="Argus Insight Agent - Host management",
    )
    sub = parser.add_subparsers(dest="group", required=True)

    # --- hostname ---
    hn_parser = sub.add_parser("hostname", help="Hostname management")
    hn_sub = hn_parser.add_subparsers(dest="action", required=True)

    hn_sub.add_parser("get", help="Show current hostname")

    set_p = hn_sub.add_parser("set", help="Change hostname")
    set_p.add_argument("name", help="New hostname")

    hn_sub.add_parser("validate", help="Validate hostname consistency")

    # --- hosts ---
    hosts_parser = sub.add_parser("hosts", help="/etc/hosts management")
    hosts_sub = hosts_parser.add_subparsers(dest="action", required=True)

    hosts_sub.add_parser("read", help="Read /etc/hosts")

    hosts_update_p = hosts_sub.add_parser("update", help="Update /etc/hosts")
    hosts_update_p.add_argument(
        "file", nargs="?", default="-", help="Content file (default: stdin)"
    )

    hosts_sub.add_parser("backup", help="Backup /etc/hosts")

    # --- resolv ---
    resolv_parser = sub.add_parser("resolv", help="/etc/resolv.conf management")
    resolv_sub = resolv_parser.add_subparsers(dest="action", required=True)

    resolv_sub.add_parser("read", help="Read /etc/resolv.conf")

    resolv_update_p = resolv_sub.add_parser("update", help="Update /etc/resolv.conf")
    resolv_update_p.add_argument(
        "file", nargs="?", default="-", help="Content file (default: stdin)"
    )

    resolv_sub.add_parser("backup", help="Backup /etc/resolv.conf")
    resolv_sub.add_parser("nameservers", help="List nameservers")

    setns_p = resolv_sub.add_parser("set-nameservers", help="Set nameservers")
    setns_p.add_argument("nameservers", nargs="+", help="Nameserver IP addresses")

    return parser


_DISPATCH = {
    ("hostname", "get"): cmd_hostname_get,
    ("hostname", "set"): cmd_hostname_set,
    ("hostname", "validate"): cmd_hostname_validate,
    ("hosts", "read"): cmd_hosts_read,
    ("hosts", "update"): cmd_hosts_update,
    ("hosts", "backup"): cmd_hosts_backup,
    ("resolv", "read"): cmd_resolv_read,
    ("resolv", "update"): cmd_resolv_update,
    ("resolv", "backup"): cmd_resolv_backup,
    ("resolv", "nameservers"): cmd_resolv_nameservers,
    ("resolv", "set-nameservers"): cmd_resolv_set_nameservers,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = _DISPATCH.get((args.group, args.action))
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
