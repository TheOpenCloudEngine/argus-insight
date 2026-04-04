"""Utilities for parsing Kubernetes resource notation.

Converts K8s CPU and memory strings to normalized numeric values
for quota comparison.
"""

import re
from decimal import Decimal, InvalidOperation

# K8s memory suffixes → multiplier to convert to MiB
_MEMORY_MULTIPLIERS: dict[str, Decimal] = {
    "Ki": Decimal("1") / Decimal("1024"),    # KiB → MiB
    "Mi": Decimal("1"),                       # MiB → MiB
    "Gi": Decimal("1024"),                    # GiB → MiB
    "Ti": Decimal("1048576"),                 # TiB → MiB
    "K": Decimal("1000") / Decimal("1048576"),
    "M": Decimal("1000000") / Decimal("1048576"),
    "G": Decimal("1000000000") / Decimal("1048576"),
    "T": Decimal("1000000000000") / Decimal("1048576"),
}

_MEMORY_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(Ki|Mi|Gi|Ti|K|M|G|T)?$")


def parse_cpu(value: str) -> Decimal:
    """Parse K8s CPU notation to cores as Decimal.

    Examples:
        "250m"  → Decimal("0.250")
        "2"     → Decimal("2")
        "1.5"   → Decimal("1.5")
        "500m"  → Decimal("0.500")
    """
    value = value.strip()
    if not value:
        return Decimal("0")
    try:
        if value.endswith("m"):
            return Decimal(value[:-1]) / Decimal("1000")
        return Decimal(value)
    except InvalidOperation:
        return Decimal("0")


def parse_memory_to_mib(value: str) -> int:
    """Parse K8s memory notation to MiB as integer.

    Examples:
        "512Mi"  → 512
        "2Gi"    → 2048
        "256Ki"  → 0 (rounds down)
        "1G"     → 953 (decimal GB to MiB)
    """
    value = value.strip()
    if not value:
        return 0
    m = _MEMORY_RE.match(value)
    if not m:
        return 0
    num = Decimal(m.group(1))
    suffix = m.group(2)
    if suffix:
        mib = num * _MEMORY_MULTIPLIERS[suffix]
    else:
        # Plain bytes → MiB
        mib = num / Decimal("1048576")
    return int(mib)
