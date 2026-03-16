"""System information collector for heartbeat.

Kernel and OS version are collected once at module load time and cached
in module-level variables since they do not change at runtime.
"""

import platform
import socket

import psutil

# --- Static info: collected once at import time ---

_hostname: str = socket.gethostname()
_kernel_version: str = platform.release()


def _detect_os_version() -> str:
    """Read /etc/os-release for PRETTY_NAME, fall back to platform.platform()."""
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            info: dict[str, str] = {}
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    info[k] = v.strip('"')
            return info.get("PRETTY_NAME", platform.platform())
    except FileNotFoundError:
        return platform.platform()


_os_version: str = _detect_os_version()


def get_static_info() -> dict[str, str | int]:
    """Return hostname, kernel_version, os_version, cpu/core counts, total_memory (cached)."""
    return {
        "hostname": _hostname,
        "kernel_version": _kernel_version,
        "os_version": _os_version,
        "cpu_count": psutil.cpu_count(logical=True) or 1,
        "core_count": psutil.cpu_count(logical=False) or 1,
        "total_memory": psutil.virtual_memory().total,
    }


def get_dynamic_info() -> dict[str, str | float]:
    """Return ip_address, cpu_usage, memory_usage, disk_swap_percent (collected each call)."""
    ip = _detect_ip_address()
    swap = psutil.swap_memory()
    disk_swap_percent = (swap.used / swap.total * 100) if swap.total > 0 else 0.0
    return {
        "ip_address": ip,
        "cpu_usage": psutil.cpu_percent(interval=0),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_swap_percent": round(disk_swap_percent, 1),
    }


def _detect_ip_address() -> str:
    """Find the first non-loopback IPv4 address."""
    for iface, addrs in psutil.net_if_addrs().items():
        if iface == "lo":
            continue
        for addr in addrs:
            if addr.family.name == "AF_INET":
                return addr.address
    return "127.0.0.1"
