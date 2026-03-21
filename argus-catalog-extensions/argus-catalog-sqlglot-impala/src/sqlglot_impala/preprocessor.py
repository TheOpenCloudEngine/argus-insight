"""Impala SQL pre-processor.

Transforms Impala-specific syntax into Hive-compatible SQL so that sqlglot's
Hive dialect can parse it correctly. Also identifies non-lineage statements
that should be skipped entirely.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Non-lineage statement patterns (no data flow, skip parsing)
# ---------------------------------------------------------------------------

_NON_LINEAGE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*COMPUTE\s+(INCREMENTAL\s+)?STATS\s+", re.IGNORECASE),
    re.compile(r"^\s*INVALIDATE\s+METADATA\b", re.IGNORECASE),
    re.compile(r"^\s*REFRESH\s+", re.IGNORECASE),
    re.compile(r"^\s*SHOW\s+", re.IGNORECASE),
    re.compile(r"^\s*DESCRIBE\s+", re.IGNORECASE),
    re.compile(r"^\s*DESC\s+", re.IGNORECASE),
    re.compile(r"^\s*EXPLAIN\s+", re.IGNORECASE),
    re.compile(r"^\s*USE\s+", re.IGNORECASE),
    re.compile(r"^\s*SET\s+", re.IGNORECASE),
    re.compile(r"^\s*ALTER\s+TABLE\s+\S+\s+RECOVER\s+PARTITIONS", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Impala hint patterns
# ---------------------------------------------------------------------------

# Block comment hints: /* +SHUFFLE */, /* +BROADCAST */, /* +NOCLUSTERED */
_BLOCK_HINT_RE = re.compile(r"/\*\s*\+\s*\w+\s*\*/")

# Bracket hints: [SHUFFLE], [NOSHUFFLE], [BROADCAST]
_BRACKET_HINT_RE = re.compile(r"\[\s*(?:NO)?(?:SHUFFLE|BROADCAST|CLUSTERED)\s*\]", re.IGNORECASE)

# STRAIGHT_JOIN after SELECT
_STRAIGHT_JOIN_RE = re.compile(r"\bSELECT\s+STRAIGHT_JOIN\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# UPSERT → INSERT rewrite
# ---------------------------------------------------------------------------

_UPSERT_RE = re.compile(r"\bUPSERT\s+INTO\b", re.IGNORECASE)


def is_lineage_relevant(sql: str) -> bool:
    """Check if the SQL statement produces data lineage.

    Returns False for metadata-only statements (COMPUTE STATS, INVALIDATE
    METADATA, REFRESH, SHOW, DESCRIBE, EXPLAIN, USE, SET).
    """
    stripped = sql.strip()
    for pattern in _NON_LINEAGE_PATTERNS:
        if pattern.match(stripped):
            return False
    return True


def preprocess(sql: str) -> str:
    """Transform Impala-specific SQL syntax into Hive-compatible SQL.

    Transformations:
    - Remove Impala query hints (/* +SHUFFLE */, [BROADCAST], etc.)
    - Rewrite UPSERT INTO → INSERT INTO (same lineage semantics)
    - Remove STRAIGHT_JOIN keyword
    """
    result = sql

    # Strip block comment hints
    result = _BLOCK_HINT_RE.sub("", result)

    # Strip bracket hints
    result = _BRACKET_HINT_RE.sub("", result)

    # Rewrite UPSERT INTO → INSERT INTO
    result = _UPSERT_RE.sub("INSERT INTO", result)

    # Remove STRAIGHT_JOIN after SELECT
    result = _STRAIGHT_JOIN_RE.sub("SELECT", result)

    return result
