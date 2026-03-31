"""Impala query profile bottleneck detector.

Applies heuristic rules to a parsed Impala runtime profile to identify
execution nodes that are likely performance bottlenecks. Each rule produces
a list of ``Bottleneck`` findings with severity, category, evidence metrics,
and actionable recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sync.platforms.impala.profile_parser import ParsedProfile, ProfileNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Bottleneck:
    """A single bottleneck finding."""

    severity: str  # "critical", "warning", "info"
    category: str  # detection rule category
    node_id: int | None
    node_type: str
    fragment: str
    description: str
    metrics: dict[str, object] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "fragment": self.fragment,
            "description": self.description,
            "metrics": self.metrics,
            "recommendation": self.recommendation,
        }


@dataclass
class NodeTimeSummary:
    """Time contribution summary for a single node."""

    node_id: int | None
    node_type: str
    fragment: str
    exec_time_ms: float
    pct_of_total: float

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "fragment": self.fragment,
            "exec_time_ms": round(self.exec_time_ms, 3),
            "pct_of_total": round(self.pct_of_total, 2),
        }


@dataclass
class BottleneckReport:
    """Complete bottleneck analysis report."""

    query_id: str
    total_time_ms: float | None
    bottlenecks: list[Bottleneck] = field(default_factory=list)
    node_summary: list[NodeTimeSummary] = field(default_factory=list)
    analyzed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "total_time_ms": round(self.total_time_ms, 3) if self.total_time_ms else None,
            "bottleneck_count": len(self.bottlenecks),
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "node_summary": [n.to_dict() for n in self.node_summary],
            "analyzed_at": self.analyzed_at,
        }


# ---------------------------------------------------------------------------
# Detection thresholds
# ---------------------------------------------------------------------------

@dataclass
class DetectionThresholds:
    """Configurable thresholds for bottleneck detection rules."""

    # Node ExecTime as fraction of total query time to flag as "time dominant"
    time_dominant_pct: float = 0.30
    # Max/avg instance time ratio to flag as "data skew"
    skew_ratio: float = 3.0
    # Rows returned / rows read ratio below which scan is "low selectivity"
    selectivity_threshold: float = 0.01
    # Minimum bytes read to consider a scan for selectivity check
    scan_bytes_min: int = 100 * 1024 * 1024  # 100 MB
    # Exchange DequeueTime as fraction of total node time for "network wait"
    network_wait_pct: float = 0.30
    # Join output/input ratio above which is "row explosion"
    row_explosion_factor: float = 10.0
    # Actual/estimated rows ratio beyond which is "cardinality error"
    cardinality_error_factor: float = 10.0
    # PeakMemory / MemoryLimit ratio for "memory pressure"
    memory_pressure_pct: float = 0.80


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

# Time metric name candidates across Impala versions
_TIME_METRIC_NAMES = ["TotalTime", "ExecTime", "LocalTime", "TotalWallClockTime"]

# Row count metric name candidates
_ROWS_RETURNED_NAMES = ["RowsReturned", "RowsProduced"]
_ROWS_READ_NAMES = ["RowsRead", "NumRowsFetched"]
_ROWS_ESTIMATED_NAMES = ["EstimatedRows", "Cardinality"]


def _get_node_time_ns(node: ProfileNode) -> int | None:
    """Get the best available time metric from a node, in nanoseconds."""
    for name in _TIME_METRIC_NAMES:
        val = node.metric_ns(name)
        if val is not None and val > 0:
            return val
    return None


def _get_count(node: ProfileNode, candidates: list[str]) -> int | None:
    """Get the first available count metric from candidates."""
    for name in candidates:
        val = node.metric_count(name)
        if val is not None:
            return val
    return None


def _find_fragment_label(profile: ParsedProfile, node: ProfileNode) -> str:
    """Find which fragment a node belongs to."""
    for frag in profile.fragments:
        if _node_in_tree(frag, node):
            return frag.detail or frag.label
    return "unknown"


def _node_in_tree(root: ProfileNode, target: ProfileNode) -> bool:
    """Check if target node is in root's subtree."""
    for child in root.children:
        if child is target:
            return True
        if _node_in_tree(child, target):
            return True
    return False


class BottleneckDetector:
    """Analyzes parsed Impala profiles to detect performance bottlenecks."""

    def __init__(self, thresholds: DetectionThresholds | None = None) -> None:
        self.t = thresholds or DetectionThresholds()

    def analyze(self, profile: ParsedProfile) -> BottleneckReport:
        """Run all detection rules and produce a report."""
        total_time_ns = profile.total_time_ns
        total_time_ms = total_time_ns / 1_000_000 if total_time_ns else None

        report = BottleneckReport(
            query_id=profile.query_id,
            total_time_ms=total_time_ms,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

        # Build node time summary
        for node in profile.all_nodes:
            node_time_ns = _get_node_time_ns(node)
            if node_time_ns is None:
                continue
            node_time_ms = node_time_ns / 1_000_000
            pct = (node_time_ns / total_time_ns * 100) if total_time_ns else 0

            frag_label = _find_fragment_label(profile, node)
            report.node_summary.append(NodeTimeSummary(
                node_id=node.node_id,
                node_type=node.node_type,
                fragment=frag_label,
                exec_time_ms=node_time_ms,
                pct_of_total=pct,
            ))

        # Sort by time descending
        report.node_summary.sort(key=lambda n: n.exec_time_ms, reverse=True)

        # Run all detection rules
        for node in profile.all_nodes:
            frag_label = _find_fragment_label(profile, node)
            report.bottlenecks.extend(self._check_time_dominant(node, total_time_ns, frag_label))
            report.bottlenecks.extend(self._check_data_skew(node, frag_label))
            report.bottlenecks.extend(self._check_spill(node, frag_label))
            report.bottlenecks.extend(self._check_low_selectivity(node, frag_label))
            report.bottlenecks.extend(self._check_network_wait(node, frag_label))
            report.bottlenecks.extend(self._check_row_explosion(node, frag_label))
            report.bottlenecks.extend(self._check_cardinality_error(node, frag_label))
            report.bottlenecks.extend(self._check_memory_pressure(node, frag_label))

        # Sort bottlenecks: critical first, then warning, then info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        report.bottlenecks.sort(key=lambda b: severity_order.get(b.severity, 9))

        return report

    # ----- Detection rules -----

    def _check_time_dominant(
        self, node: ProfileNode, total_time_ns: int | None, fragment: str,
    ) -> list[Bottleneck]:
        """Flag nodes consuming a disproportionate share of total query time."""
        if not total_time_ns or total_time_ns == 0:
            return []
        node_time_ns = _get_node_time_ns(node)
        if node_time_ns is None:
            return []

        ratio = node_time_ns / total_time_ns
        if ratio < self.t.time_dominant_pct:
            return []

        pct = round(ratio * 100, 1)
        node_ms = round(node_time_ns / 1_000_000, 1)
        total_ms = round(total_time_ns / 1_000_000, 1)

        severity = "critical" if ratio >= 0.50 else "warning"

        return [Bottleneck(
            severity=severity,
            category="time_dominant",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=(
                f"Node {node.node_id}:{node.node_type} consumed {pct}% of total "
                f"query time ({node_ms}ms / {total_ms}ms)"
            ),
            metrics={"exec_time_ms": node_ms, "total_time_ms": total_ms, "pct": pct},
            recommendation=_time_dominant_recommendation(node),
        )]

    def _check_data_skew(
        self, node: ProfileNode, fragment: str,
    ) -> list[Bottleneck]:
        """Detect uneven data distribution across instances."""
        if len(node.instances) < 2:
            return []

        times = []
        for inst in node.instances:
            t = _get_node_time_ns(inst)
            if t is not None:
                times.append(t)

        if len(times) < 2:
            return []

        avg_time = sum(times) / len(times)
        max_time = max(times)

        if avg_time == 0:
            return []

        ratio = max_time / avg_time
        if ratio < self.t.skew_ratio:
            return []

        return [Bottleneck(
            severity="critical",
            category="data_skew",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=(
                f"Node {node.node_id}:{node.node_type} has data skew — "
                f"slowest instance is {ratio:.1f}x the average "
                f"(max={max_time / 1_000_000:.1f}ms, avg={avg_time / 1_000_000:.1f}ms)"
            ),
            metrics={
                "max_instance_ms": round(max_time / 1_000_000, 1),
                "avg_instance_ms": round(avg_time / 1_000_000, 1),
                "skew_ratio": round(ratio, 2),
                "instance_count": len(times),
            },
            recommendation=(
                "Data is unevenly distributed. Consider: "
                "(1) Check for skewed join keys or partition keys, "
                "(2) Use COMPUTE STATS to update table statistics, "
                "(3) Consider repartitioning the data."
            ),
        )]

    def _check_spill(
        self, node: ProfileNode, fragment: str,
    ) -> list[Bottleneck]:
        """Detect when operators spill data to disk due to memory pressure."""
        spill_count = _get_count(node, ["SpilledPartitions", "SpillCount", "NumSpilledPartitions"])
        if spill_count is None or spill_count == 0:
            return []

        spill_bytes = node.metric_bytes("SpilledBytes") or node.metric_bytes("SpillBytes")
        spill_mb = round(spill_bytes / 1_024 / 1_024, 1) if spill_bytes else None

        desc_parts = [
            f"Node {node.node_id}:{node.node_type} spilled {spill_count} partitions to disk"
        ]
        if spill_mb:
            desc_parts.append(f"({spill_mb} MB)")

        return [Bottleneck(
            severity="warning",
            category="spill",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=" ".join(desc_parts),
            metrics={"spill_count": spill_count, "spill_mb": spill_mb},
            recommendation=(
                "Operator ran out of memory and spilled to disk. Consider: "
                "(1) Increase MEM_LIMIT for this query, "
                "(2) Check if COMPUTE STATS is up to date, "
                "(3) Reduce query concurrency, "
                "(4) Use a more selective predicate to reduce data volume."
            ),
        )]

    def _check_low_selectivity(
        self, node: ProfileNode, fragment: str,
    ) -> list[Bottleneck]:
        """Detect scan nodes reading far more data than they return."""
        if "SCAN" not in node.node_type:
            return []

        bytes_read = node.metric_bytes("BytesRead") or node.metric_bytes("TotalBytesRead")
        if bytes_read is None or bytes_read < self.t.scan_bytes_min:
            return []

        rows_returned = _get_count(node, _ROWS_RETURNED_NAMES)
        rows_read = _get_count(node, _ROWS_READ_NAMES)

        if rows_read is None or rows_read == 0 or rows_returned is None:
            return []

        selectivity = rows_returned / rows_read
        if selectivity >= self.t.selectivity_threshold:
            return []

        pct = round(selectivity * 100, 4)
        read_mb = round(bytes_read / 1_024 / 1_024, 1)

        return [Bottleneck(
            severity="warning",
            category="low_selectivity",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=(
                f"Node {node.node_id}:{node.node_type} read {read_mb}MB "
                f"but returned only {pct}% of rows "
                f"({rows_returned:,} / {rows_read:,})"
            ),
            metrics={
                "bytes_read_mb": read_mb,
                "rows_returned": rows_returned,
                "rows_read": rows_read,
                "selectivity_pct": pct,
            },
            recommendation=(
                "Scan reads much more data than needed. Consider: "
                "(1) Add partition pruning predicates (WHERE partition_col = ...), "
                "(2) Push predicates closer to the scan, "
                "(3) Use Parquet/ORC columnar format for better predicate pushdown, "
                "(4) Ensure table statistics are up to date."
            ),
        )]

    def _check_network_wait(
        self, node: ProfileNode, fragment: str,
    ) -> list[Bottleneck]:
        """Detect exchange nodes spending excessive time waiting for data."""
        if "EXCHANGE" not in node.node_type:
            return []

        node_time_ns = _get_node_time_ns(node)
        dequeue_ns = node.metric_ns("DequeueTime") or node.metric_ns("DataArrivalWaitTime")
        if not node_time_ns or not dequeue_ns or node_time_ns == 0:
            return []

        ratio = dequeue_ns / node_time_ns
        if ratio < self.t.network_wait_pct:
            return []

        pct = round(ratio * 100, 1)
        wait_ms = round(dequeue_ns / 1_000_000, 1)

        return [Bottleneck(
            severity="warning",
            category="network_wait",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=(
                f"Node {node.node_id}:{node.node_type} spent {pct}% of its time "
                f"waiting for data ({wait_ms}ms)"
            ),
            metrics={"dequeue_time_ms": wait_ms, "wait_pct": pct},
            recommendation=(
                "Exchange node is blocked waiting for upstream data. "
                "The bottleneck is likely in the sending fragment — "
                "check the upstream nodes for slow operations."
            ),
        )]

    def _check_row_explosion(
        self, node: ProfileNode, fragment: str,
    ) -> list[Bottleneck]:
        """Detect joins that produce far more rows than their inputs."""
        if "JOIN" not in node.node_type:
            return []

        rows_returned = _get_count(node, _ROWS_RETURNED_NAMES)
        if rows_returned is None:
            return []

        # Get probe and build side row counts
        probe_rows = _get_count(node, ["ProbeRows", "LeftChildRows"])
        build_rows = _get_count(node, ["BuildRows", "RightChildRows"])

        if probe_rows is None and build_rows is None:
            # Try to infer from children
            if len(node.children) >= 2:
                probe_rows = _get_count(node.children[0], _ROWS_RETURNED_NAMES)
                build_rows = _get_count(node.children[1], _ROWS_RETURNED_NAMES)

        max_input = max(filter(None, [probe_rows, build_rows]), default=None)
        if max_input is None or max_input == 0:
            return []

        ratio = rows_returned / max_input
        if ratio < self.t.row_explosion_factor:
            return []

        return [Bottleneck(
            severity="warning",
            category="row_explosion",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=(
                f"Node {node.node_id}:{node.node_type} produced {ratio:.1f}x more rows "
                f"than its largest input ({rows_returned:,} output vs {max_input:,} input)"
            ),
            metrics={
                "rows_returned": rows_returned,
                "max_input_rows": max_input,
                "explosion_ratio": round(ratio, 2),
            },
            recommendation=(
                "Join is producing a cartesian-like explosion. Consider: "
                "(1) Add or refine join predicates, "
                "(2) Check for many-to-many relationships, "
                "(3) Filter one side before joining to reduce combinations."
            ),
        )]

    def _check_cardinality_error(
        self, node: ProfileNode, fragment: str,
    ) -> list[Bottleneck]:
        """Detect large discrepancies between estimated and actual row counts."""
        actual = _get_count(node, _ROWS_RETURNED_NAMES)
        estimated = _get_count(node, _ROWS_ESTIMATED_NAMES)

        if actual is None or estimated is None or estimated == 0:
            return []

        ratio = actual / estimated
        if (1 / self.t.cardinality_error_factor) <= ratio <= self.t.cardinality_error_factor:
            return []

        if ratio > 1:
            direction = "underestimated"
            factor = round(ratio, 1)
        else:
            direction = "overestimated"
            factor = round(1 / ratio, 1)

        return [Bottleneck(
            severity="info",
            category="cardinality_error",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=(
                f"Node {node.node_id}:{node.node_type} — optimizer {direction} "
                f"row count by {factor}x (actual={actual:,}, estimated={estimated:,})"
            ),
            metrics={
                "actual_rows": actual,
                "estimated_rows": estimated,
                "error_ratio": round(ratio, 2),
            },
            recommendation=(
                "Cardinality estimation is significantly off. "
                "Run COMPUTE STATS or COMPUTE INCREMENTAL STATS on the relevant tables "
                "to give the optimizer more accurate statistics."
            ),
        )]

    def _check_memory_pressure(
        self, node: ProfileNode, fragment: str,
    ) -> list[Bottleneck]:
        """Detect nodes approaching the memory limit."""
        peak_mem = node.metric_bytes("PeakMemoryUsage") or node.metric_bytes("PeakMemUsage")
        mem_limit = node.metric_bytes("MemoryLimit") or node.metric_bytes("MemLimit")

        if peak_mem is None or mem_limit is None or mem_limit == 0:
            return []

        ratio = peak_mem / mem_limit
        if ratio < self.t.memory_pressure_pct:
            return []

        peak_mb = round(peak_mem / 1_024 / 1_024, 1)
        limit_mb = round(mem_limit / 1_024 / 1_024, 1)
        pct = round(ratio * 100, 1)

        return [Bottleneck(
            severity="warning",
            category="memory_pressure",
            node_id=node.node_id,
            node_type=node.node_type,
            fragment=fragment,
            description=(
                f"Node {node.node_id}:{node.node_type} used {pct}% of memory limit "
                f"({peak_mb}MB / {limit_mb}MB)"
            ),
            metrics={"peak_memory_mb": peak_mb, "memory_limit_mb": limit_mb, "usage_pct": pct},
            recommendation=(
                "Node is close to the memory limit and may spill or fail. Consider: "
                "(1) Increase MEM_LIMIT, "
                "(2) Check if table stats are current, "
                "(3) Break the query into smaller parts, "
                "(4) Add more selective predicates."
            ),
        )]


# ---------------------------------------------------------------------------
# Recommendation helpers
# ---------------------------------------------------------------------------

def _time_dominant_recommendation(node: ProfileNode) -> str:
    """Generate a node-type-specific recommendation for time-dominant nodes."""
    nt = node.node_type

    if "SCAN" in nt:
        return (
            "Scan node is the bottleneck. Consider: "
            "(1) Add partition pruning predicates, "
            "(2) Use columnar format (Parquet/ORC), "
            "(3) Ensure COMPUTE STATS is up to date, "
            "(4) Check for small files issue (too many small files)."
        )
    if "JOIN" in nt:
        return (
            "Join node is the bottleneck. Consider: "
            "(1) Verify join order (smaller table on build side), "
            "(2) Use COMPUTE STATS for accurate cardinality estimates, "
            "(3) Add a STRAIGHT_JOIN hint if optimizer chooses wrong order, "
            "(4) Check for data skew on join keys."
        )
    if "AGGREGATE" in nt or "GROUP" in nt:
        return (
            "Aggregation node is the bottleneck. Consider: "
            "(1) Reduce the number of GROUP BY columns, "
            "(2) Pre-filter data before aggregation, "
            "(3) Check for high-cardinality grouping columns."
        )
    if "SORT" in nt:
        return (
            "Sort node is the bottleneck. Consider: "
            "(1) Add a LIMIT clause if full sort is not needed, "
            "(2) Increase memory to avoid spilling, "
            "(3) Check if the ORDER BY is necessary."
        )
    if "EXCHANGE" in nt:
        return (
            "Exchange (data shuffle) is the bottleneck. Consider: "
            "(1) Check upstream nodes for slow operations, "
            "(2) Consider broadcast join hint for small tables, "
            "(3) Verify network bandwidth between nodes."
        )

    return (
        "This node dominates query execution time. "
        "Review the node's input data volume and consider optimizing upstream operations."
    )
