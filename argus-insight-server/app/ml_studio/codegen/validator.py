"""Data-aware pipeline validator.

Loads actual data from Source nodes and walks the DAG to validate
that each node's config is compatible with the data it receives.
"""

import io
import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    node_id: str
    node_label: str
    level: str  # "error" | "warning"
    message: str


@dataclass
class ValidationResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, node_id: str, label: str, msg: str):
        self.errors.append(Issue(node_id, label, "error", msg))

    def add_warning(self, node_id: str, label: str, msg: str):
        self.warnings.append(Issue(node_id, label, "warning", msg))

    def to_dict(self) -> dict:
        return {
            "valid": self.ok,
            "errors": [{"nodeId": e.node_id, "label": e.node_label,
                         "level": e.level, "message": e.message} for e in self.errors],
            "warnings": [{"nodeId": w.node_id, "label": w.node_label,
                           "level": w.level, "message": w.message} for w in self.warnings],
        }


def _load_source_df(node: dict, minio_client) -> pd.DataFrame | None:
    """Attempt to load source data for schema validation (first 100 rows)."""
    cfg = node.get("config", {})
    ntype = node.get("type", "")
    bucket = cfg.get("bucket", "")
    path = cfg.get("path", "")

    if not bucket or not path or not minio_client:
        return None

    try:
        response = minio_client.get_object(bucket, path)
        raw = response.read()
        response.close()
        response.release_conn()
        buf = io.BytesIO(raw)

        if ntype == "source_parquet":
            return pd.read_parquet(buf).head(100)
        elif ntype == "source_csv":
            delim = cfg.get("delimiter", "auto")
            sep = None if delim == "auto" else delim
            enc = cfg.get("encoding", "utf-8")
            return pd.read_csv(buf, sep=sep, encoding=enc, nrows=100)
        return pd.read_csv(buf, nrows=100)
    except Exception as e:
        logger.debug("Failed to load source for validation: %s", e)
        return None


def _topo_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Return node IDs in topological order."""
    in_deg = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        src, tgt = e.get("from", e.get("source", "")), e.get("to", e.get("target", ""))
        adj.setdefault(src, []).append(tgt)
        in_deg[tgt] = in_deg.get(tgt, 0) + 1

    queue = [nid for nid, d in in_deg.items() if d == 0]
    result = []
    while queue:
        cur = queue.pop(0)
        result.append(cur)
        for nxt in adj.get(cur, []):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                queue.append(nxt)
    return result


def _find_parent(node_id: str, edges: list[dict]) -> str | None:
    for e in edges:
        tgt = e.get("to", e.get("target", ""))
        src = e.get("from", e.get("source", ""))
        if tgt == node_id:
            return src
    return None


def validate_pipeline(
    nodes: list[dict],
    edges: list[dict],
    minio_client=None,
) -> ValidationResult:
    """Validate a pipeline DAG with data-aware checks.

    Args:
        nodes: [{id, type, label, config}, ...]
        edges: [{from, to}, ...]
        minio_client: Optional Minio client for loading source data.

    Returns:
        ValidationResult with errors and warnings.
    """
    result = ValidationResult()
    node_map = {n["id"]: n for n in nodes}

    if not nodes:
        result.add_error("", "Pipeline", "Pipeline has no nodes")
        return result

    # Check for source nodes
    sources = [n for n in nodes if n.get("type", "").startswith("source_")]
    if not sources:
        result.add_error("", "Pipeline", "Pipeline must have at least one Source node")
        return result

    # Check for model nodes
    models = [n for n in nodes if n.get("type", "").startswith("model_")]
    if not models:
        result.add_warning("", "Pipeline", "No Model node — pipeline will only transform data")

    # Load source data for schema tracking
    schema: dict[str, pd.DataFrame | None] = {}
    for src in sources:
        df = _load_source_df(src, minio_client)
        schema[src["id"]] = df
        if df is not None:
            # Apply column exclusions
            cols = src.get("config", {}).get("columns", [])
            excludes = [c["name"] for c in cols if isinstance(c, dict) and c.get("action") == "exclude"]
            if excludes:
                df = df.drop(columns=[c for c in excludes if c in df.columns], errors="ignore")
                schema[src["id"]] = df

    # Walk nodes in topological order
    order = _topo_sort(nodes, edges)

    for nid in order:
        node = node_map.get(nid)
        if not node:
            continue

        ntype = node.get("type", "")
        cfg = node.get("config", {})
        label = node.get("label", ntype)
        parent_id = _find_parent(nid, edges)

        # Propagate schema from parent
        if parent_id and parent_id in schema:
            schema[nid] = schema[parent_id]

        df = schema.get(nid)  # May be None if source load failed
        columns = list(df.columns) if df is not None else []
        numeric_cols = list(df.select_dtypes(include="number").columns) if df is not None else []
        dt_cols = list(df.select_dtypes(include="datetime").columns) if df is not None else []

        # ── Source validation ─────────────────────────────
        if ntype.startswith("source_"):
            if ntype in ("source_csv", "source_parquet"):
                if not cfg.get("bucket"):
                    result.add_error(nid, label, "Bucket is required")
                if not cfg.get("path"):
                    result.add_error(nid, label, "File path is required")
            elif ntype == "source_database":
                if cfg.get("mode") == "sql" and not cfg.get("query"):
                    result.add_error(nid, label, "SQL query is required")
                if cfg.get("mode") == "table" and not cfg.get("table"):
                    result.add_error(nid, label, "Table name is required")

        # ── Transform validation ──────────────────────────
        elif ntype == "transform_typecast":
            for cast in cfg.get("casts", []):
                col = cast.get("column", "")
                if col and columns and col not in columns:
                    result.add_error(nid, label, f"Column '{col}' does not exist in data")

        elif ntype == "transform_drop_cols":
            cols_str = cfg.get("columns", "")
            drop_list = [c.strip() for c in cols_str.split(",") if c.strip()] if isinstance(cols_str, str) else []
            for c in drop_list:
                if columns and c not in columns:
                    result.add_warning(nid, label, f"Column '{c}' not found — will be ignored")

        elif ntype == "transform_outlier":
            cols_str = cfg.get("columns", "")
            ocols = [c.strip() for c in cols_str.split(",") if c.strip()] if isinstance(cols_str, str) else []
            for c in ocols:
                if columns and c in columns and c not in numeric_cols:
                    result.add_error(nid, label, f"Column '{c}' is not numeric — cannot detect outliers")

        elif ntype == "transform_datetime":
            col = cfg.get("column", "")
            if not col:
                result.add_error(nid, label, "Datetime column is required")
            elif df is not None and col in columns:
                # Try parsing — check if it's convertible
                try:
                    pd.to_datetime(df[col].head(5), errors="raise")
                except Exception:
                    result.add_warning(nid, label, f"Column '{col}' may not be a valid datetime")

        elif ntype == "transform_binning":
            col = cfg.get("column", "")
            if not col:
                result.add_error(nid, label, "Column is required for binning")
            elif columns and col in columns and col not in numeric_cols:
                result.add_error(nid, label, f"Column '{col}' is not numeric — cannot bin")
            elif df is not None and col in columns:
                n_unique = df[col].nunique()
                bins = cfg.get("bins", 5)
                if n_unique < bins:
                    result.add_warning(nid, label,
                                       f"Column '{col}' has only {n_unique} unique values but {bins} bins requested")

        elif ntype == "transform_sort":
            col = cfg.get("column", "")
            if not col:
                result.add_error(nid, label, "Sort column is required")
            elif columns and col not in columns:
                result.add_error(nid, label, f"Column '{col}' does not exist")

        elif ntype == "transform_filter":
            for i, cond in enumerate(cfg.get("conditions", [])):
                col = cond.get("column", "")
                if not col:
                    result.add_error(nid, label, f"Condition {i+1}: column is required")
                elif columns and col not in columns:
                    result.add_error(nid, label, f"Condition {i+1}: column '{col}' does not exist")
                op = cond.get("operator", "")
                val = cond.get("value", "")
                if op not in ("not_null", "contains") and not val:
                    result.add_warning(nid, label, f"Condition {i+1}: value is empty")

        elif ntype == "transform_split":
            target = cfg.get("target_column", "")
            if not target:
                result.add_error(nid, label, "Target column is required")
            elif columns and target not in columns:
                result.add_error(nid, label, f"Target column '{target}' does not exist in data")
            elif df is not None and target in columns:
                n_unique = df[target].nunique()
                if n_unique < 2:
                    result.add_error(nid, label,
                                     f"Target '{target}' has only {n_unique} unique value(s) — need at least 2")
                test_size = cfg.get("test_size", 0.2)
                n_test = int(len(df) * test_size)
                if n_test < 1:
                    result.add_warning(nid, label, "Test set would be empty with current split ratio")

        # ── Model validation ──────────────────────────────
        elif ntype.startswith("model_"):
            if not parent_id:
                result.add_error(nid, label, "Model must be connected to a data source")

        # ── Output validation ─────────────────────────────
        elif ntype == "output_csv":
            if not cfg.get("bucket"):
                result.add_error(nid, label, "Bucket is required")
            if not cfg.get("filename"):
                result.add_error(nid, label, "Filename is required")
            fname = cfg.get("filename", "")
            if fname and not fname.lower().endswith(".csv"):
                result.add_warning(nid, label, "Filename should end with .csv")

    return result
