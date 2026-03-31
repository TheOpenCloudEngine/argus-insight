"""Impala runtime profile parser.

Parses the text-based runtime profile produced by Impala into a structured tree
of execution nodes with typed metrics.  The profile can be obtained from:
  - Impala daemon web UI: GET http://<host>:25000/queries/<qid>?json
  - Cloudera Manager API:  GET /api/v{ver}/clusters/{c}/services/{s}/impalaQueries/{qid}

The parser is intentionally lenient — unknown sections or metrics are silently
skipped so that it works across Impala/CDH/CDP versions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_TIME_UNITS = {
    "h": 3_600_000_000_000,
    "m": 60_000_000_000,
    "s": 1_000_000_000,
    "ms": 1_000_000,
    "us": 1_000,
    "ns": 1,
}

_BYTE_UNITS = {
    "B": 1,
    "KB": 1_024,
    "MB": 1_024**2,
    "GB": 1_024**3,
    "TB": 1_024**4,
}


@dataclass
class ProfileMetric:
    """A single metric extracted from a profile node."""

    name: str
    raw_value: str
    numeric_value: float | None = None
    unit: str | None = None  # "ns", "bytes", "count", "pct"

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "raw_value": self.raw_value}
        if self.numeric_value is not None:
            d["numeric_value"] = self.numeric_value
        if self.unit:
            d["unit"] = self.unit
        return d


@dataclass
class ProfileNode:
    """A single execution node in the profile tree."""

    node_type: str  # HDFS_SCAN_NODE, HASH_JOIN_NODE, EXCHANGE_NODE, etc.
    node_id: int | None = None
    label: str = ""
    detail: str = ""  # Additional info (e.g. join type, table name)
    metrics: dict[str, ProfileMetric] = field(default_factory=dict)
    children: list[ProfileNode] = field(default_factory=list)
    # Per-instance breakdown (for averaged vs individual comparisons)
    instances: list[ProfileNode] = field(default_factory=list)

    # Convenience accessors
    def metric_ns(self, name: str) -> int | None:
        """Get a time metric value in nanoseconds."""
        m = self.metrics.get(name)
        if m and m.unit == "ns" and m.numeric_value is not None:
            return int(m.numeric_value)
        return None

    def metric_bytes(self, name: str) -> int | None:
        """Get a byte metric value."""
        m = self.metrics.get(name)
        if m and m.unit == "bytes" and m.numeric_value is not None:
            return int(m.numeric_value)
        return None

    def metric_count(self, name: str) -> int | None:
        """Get a count metric value."""
        m = self.metrics.get(name)
        if m and m.unit == "count" and m.numeric_value is not None:
            return int(m.numeric_value)
        return None

    def to_dict(self) -> dict:
        d: dict = {
            "node_type": self.node_type,
            "label": self.label,
        }
        if self.node_id is not None:
            d["node_id"] = self.node_id
        if self.detail:
            d["detail"] = self.detail
        if self.metrics:
            d["metrics"] = {k: v.to_dict() for k, v in self.metrics.items()}
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        if self.instances:
            d["instances"] = [i.to_dict() for i in self.instances]
        return d


@dataclass
class ParsedProfile:
    """Complete parsed Impala query profile."""

    query_id: str = ""
    query_type: str | None = None
    query_state: str | None = None
    total_time_ns: int | None = None
    planning_time_ns: int | None = None
    fragments: list[ProfileNode] = field(default_factory=list)
    summary: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
    # Flattened list of all execution nodes (for easy iteration)
    all_nodes: list[ProfileNode] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {"query_id": self.query_id}
        if self.query_type:
            d["query_type"] = self.query_type
        if self.query_state:
            d["query_state"] = self.query_state
        if self.total_time_ns is not None:
            d["total_time_ms"] = round(self.total_time_ns / 1_000_000, 3)
        if self.planning_time_ns is not None:
            d["planning_time_ms"] = round(self.planning_time_ns / 1_000_000, 3)
        if self.summary:
            d["summary"] = self.summary
        if self.fragments:
            d["fragments"] = [f.to_dict() for f in self.fragments]
        return d


# ---------------------------------------------------------------------------
# Metric value parsers
# ---------------------------------------------------------------------------

# Pattern for time values like "1h2m3s456ms", "123.456ms", "1s234ms", "0.000ns"
_RE_TIME = re.compile(
    r"(?:(\d+)h)?\s*(?:(\d+)m(?!s))?\s*(?:(\d+(?:\.\d+)?)s)?\s*"
    r"(?:(\d+(?:\.\d+)?)ms)?\s*(?:(\d+(?:\.\d+)?)us)?\s*(?:(\d+(?:\.\d+)?)ns)?",
)

# Pattern for byte values like "1.23 GB", "456 MB", "0 B", "1.23GB"
_RE_BYTES = re.compile(r"([\d.]+)\s*(TB|GB|MB|KB|B)\b")

# Pattern for percentage values like "12.34%"
_RE_PCT = re.compile(r"([\d.]+)%")

# Pattern for node labels like "03:HASH_JOIN_NODE [INNER JOIN, BROADCAST]"
_RE_NODE = re.compile(
    r"(\d+):(\w+(?:_NODE|_SINK|SCAN)?\w*)"
    r"(?:\s*\[([^\]]*)\])?"
    r"(?:\s*\[([^\]]*)\])?",
)

# Pattern for fragment headers like "Averaged Fragment F01"
_RE_FRAGMENT = re.compile(r"(?:Averaged\s+)?Fragment\s+(F\d+)")

# Pattern for instance headers like "Instance ... (host=node1:22000)"
_RE_INSTANCE = re.compile(r"Instance\s+\S+\s*\(host=([^)]+)\)")

# Metric line: "   - MetricName: value"
_RE_METRIC = re.compile(r"^\s*-\s+(\w[\w\s]*\w|\w+):\s+(.+)$")

# Summary key-value: "  Key: Value"
_RE_SUMMARY_KV = re.compile(r"^\s{2,}(\w[\w\s]*\w|\w+):\s+(.+)$")

# Query ID pattern
_RE_QUERY_ID = re.compile(r"Query\s*\(id=([^)]+)\)")


def parse_time_value(raw: str) -> tuple[float | None, str | None]:
    """Parse a time string into nanoseconds.

    Handles: "1h2m3s456ms", "123.456ms", "1s234ms", "0.000ns"
    Returns (nanoseconds, "ns") or (None, None).
    """
    raw = raw.strip()
    m = _RE_TIME.fullmatch(raw)
    if not m:
        # Try partial match
        m = _RE_TIME.search(raw)
        if not m or not any(m.groups()):
            return None, None

    total_ns: float = 0
    hours, mins, secs, ms, us, ns = m.groups()
    if hours:
        total_ns += float(hours) * _TIME_UNITS["h"]
    if mins:
        total_ns += float(mins) * _TIME_UNITS["m"]
    if secs:
        total_ns += float(secs) * _TIME_UNITS["s"]
    if ms:
        total_ns += float(ms) * _TIME_UNITS["ms"]
    if us:
        total_ns += float(us) * _TIME_UNITS["us"]
    if ns:
        total_ns += float(ns) * _TIME_UNITS["ns"]

    if total_ns == 0 and not any([hours, mins, secs, ms, us, ns]):
        return None, None

    return total_ns, "ns"


def parse_byte_value(raw: str) -> tuple[float | None, str | None]:
    """Parse a byte string into bytes.

    Handles: "1.23 GB", "456 MB", "0 B"
    Returns (bytes, "bytes") or (None, None).
    """
    m = _RE_BYTES.search(raw.strip())
    if not m:
        return None, None
    value = float(m.group(1))
    unit = m.group(2)
    return value * _BYTE_UNITS[unit], "bytes"


def parse_count_value(raw: str) -> tuple[float | None, str | None]:
    """Parse a numeric count value.

    Handles: "1234", "1.23K", "1.23M", integers with commas like "1,234,567"
    Returns (count, "count") or (None, None).
    """
    raw = raw.strip()

    # Handle K/M/B suffixes
    m = re.match(r"^([\d.]+)\s*([KMB])$", raw)
    if m:
        value = float(m.group(1))
        suffix = m.group(2)
        multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
        return value * multipliers[suffix], "count"

    # Handle plain integers (with optional commas)
    cleaned = raw.replace(",", "")
    try:
        return float(cleaned), "count"
    except ValueError:
        return None, None


def parse_metric_value(name: str, raw: str) -> ProfileMetric:
    """Parse a metric value, auto-detecting the type from the name and value."""
    raw = raw.strip()

    # Time metrics (name hints or value format)
    time_hints = {"Time", "Latency", "Duration", "Wait", "Delay"}
    if any(h in name for h in time_hints) or re.search(r"\d+[hms]", raw):
        val, unit = parse_time_value(raw)
        if val is not None:
            return ProfileMetric(name=name, raw_value=raw, numeric_value=val, unit=unit)

    # Byte metrics
    byte_hints = {"Bytes", "Memory", "Buffer", "Spill", "DataSize"}
    if any(h in name for h in byte_hints) or _RE_BYTES.search(raw):
        val, unit = parse_byte_value(raw)
        if val is not None:
            return ProfileMetric(name=name, raw_value=raw, numeric_value=val, unit=unit)

    # Percentage
    pct_match = _RE_PCT.fullmatch(raw)
    if pct_match:
        return ProfileMetric(
            name=name, raw_value=raw,
            numeric_value=float(pct_match.group(1)), unit="pct",
        )

    # Count (rows, partitions, etc.)
    val, unit = parse_count_value(raw)
    if val is not None:
        return ProfileMetric(name=name, raw_value=raw, numeric_value=val, unit=unit)

    # Fallback: store raw string without numeric interpretation
    return ProfileMetric(name=name, raw_value=raw)


# ---------------------------------------------------------------------------
# Profile text parser
# ---------------------------------------------------------------------------

class ImpalaProfileParser:
    """Parses Impala text-format runtime profiles into structured data."""

    def parse(self, profile_text: str) -> ParsedProfile:
        """Parse a complete Impala runtime profile text."""
        result = ParsedProfile(raw_text=profile_text)

        lines = profile_text.splitlines()
        idx = 0

        # Extract query ID from first line
        if lines:
            m = _RE_QUERY_ID.search(lines[0])
            if m:
                result.query_id = m.group(1)

        # Parse summary section
        idx = self._parse_summary(lines, idx, result)

        # Parse execution profile (fragments and nodes)
        self._parse_fragments(lines, idx, result)

        # Extract key timing from summary
        if "TotalTime" in result.summary:
            val, _ = parse_time_value(result.summary["TotalTime"])
            if val is not None:
                result.total_time_ns = int(val)
        if "PlanningTime" in result.summary:
            val, _ = parse_time_value(result.summary["PlanningTime"])
            if val is not None:
                result.planning_time_ns = int(val)

        # Extract query type and state from summary
        result.query_type = result.summary.get("Query Type")
        result.query_state = result.summary.get("Query State")

        # Flatten all nodes into all_nodes list
        result.all_nodes = self._flatten_nodes(result.fragments)

        return result

    def _parse_summary(
        self, lines: list[str], start: int, result: ParsedProfile,
    ) -> int:
        """Parse the Summary section, return the line index after it."""
        in_summary = False
        idx = start

        for idx, line in enumerate(lines[start:], start=start):
            stripped = line.strip()

            if stripped == "Summary:":
                in_summary = True
                continue

            if in_summary:
                # End of summary section when we hit a non-indented line
                # or a known section header
                if stripped.startswith("Execution Profile"):
                    return idx
                if _RE_FRAGMENT.match(stripped):
                    return idx

                m = _RE_SUMMARY_KV.match(line)
                if m:
                    result.summary[m.group(1).strip()] = m.group(2).strip()

        return idx

    def _parse_fragments(
        self, lines: list[str], start: int, result: ParsedProfile,
    ) -> None:
        """Parse fragment and node sections from the profile."""
        current_fragment: ProfileNode | None = None
        node_stack: list[tuple[int, ProfileNode]] = []  # (indent, node)

        for line in lines[start:]:
            if not line.strip():
                continue

            indent = len(line) - len(line.lstrip())
            stripped = line.strip()

            # Fragment header
            frag_match = _RE_FRAGMENT.match(stripped)
            if frag_match:
                current_fragment = ProfileNode(
                    node_type="FRAGMENT",
                    label=stripped,
                    detail=frag_match.group(1),
                )
                result.fragments.append(current_fragment)
                node_stack = []
                continue

            # Instance header (skip — instances are handled via node tree)
            if _RE_INSTANCE.match(stripped):
                continue

            # Node label
            node_match = _RE_NODE.match(stripped)
            if node_match:
                node_id = int(node_match.group(1))
                node_type = node_match.group(2)
                detail_parts = []
                if node_match.group(3):
                    detail_parts.append(node_match.group(3))
                if node_match.group(4):
                    detail_parts.append(node_match.group(4))

                node = ProfileNode(
                    node_type=node_type,
                    node_id=node_id,
                    label=stripped,
                    detail=", ".join(detail_parts),
                )

                # Pop nodes from stack that are at same or deeper indent
                while node_stack and node_stack[-1][0] >= indent:
                    node_stack.pop()

                if node_stack:
                    node_stack[-1][1].children.append(node)
                elif current_fragment:
                    current_fragment.children.append(node)

                node_stack.append((indent, node))
                continue

            # Metric line
            metric_match = _RE_METRIC.match(stripped)
            if metric_match and node_stack:
                name = metric_match.group(1).strip()
                raw_value = metric_match.group(2).strip()
                metric = parse_metric_value(name, raw_value)
                node_stack[-1][1].metrics[name] = metric
                continue

            # Fragment-level metrics (when no node is on stack)
            if metric_match and current_fragment and not node_stack:
                metric_m = metric_match
                name = metric_m.group(1).strip()
                raw_value = metric_m.group(2).strip()
                metric = parse_metric_value(name, raw_value)
                current_fragment.metrics[name] = metric

    def _flatten_nodes(self, fragments: list[ProfileNode]) -> list[ProfileNode]:
        """Recursively collect all execution nodes from all fragments."""
        nodes: list[ProfileNode] = []

        def _walk(node: ProfileNode) -> None:
            if node.node_type != "FRAGMENT":
                nodes.append(node)
            for child in node.children:
                _walk(child)
            for inst in node.instances:
                _walk(inst)

        for frag in fragments:
            for child in frag.children:
                _walk(child)

        return nodes
