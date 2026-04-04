"""Data-aware pipeline validator with schema propagation.

Loads actual data from Source nodes and walks the DAG to validate
that each node's config is compatible with the data it receives.
Schema changes (dropped columns, type casts, new derived columns)
are propagated through the DAG so downstream nodes are validated
against the *actual* schema they will see at runtime.
"""

import io
import logging
import re
from dataclasses import dataclass, field

import pandas as pd

from app.ml_studio.codegen.schema_tracker import (
    SchemaMeta,
    apply_schema_effect,
    extract_column_refs,
)

logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────────

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


# ── DAG helpers ──────────────────────────────────────────────

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


def _find_ancestors(node_id: str, edges: list[dict], node_map: dict) -> set[str]:
    """Return set of ancestor node types (for checking upstream model, etc.)."""
    visited = set()
    queue = [node_id]
    types = set()
    while queue:
        cur = queue.pop(0)
        parent = _find_parent(cur, edges)
        if parent and parent not in visited:
            visited.add(parent)
            if parent in node_map:
                types.add(node_map[parent].get("type", ""))
            queue.append(parent)
    return types


# ── Source data loader ───────────────────────────────────────

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


# ── Main validator ───────────────────────────────────────────

def validate_pipeline(
    nodes: list[dict],
    edges: list[dict],
    minio_client=None,
) -> ValidationResult:
    """Validate a pipeline DAG with data-aware schema propagation.

    Walks the DAG in topological order, propagating schema changes
    (column adds/drops, type casts, etc.) through each transform.
    Validates downstream nodes against the *actual* schema they will
    receive at runtime, not just the original source schema.

    Args:
        nodes: [{id, type, label, config}, ...]
        edges: [{from, to}, ...]
        minio_client: Optional Minio client for loading source data.

    Returns:
        ValidationResult with errors and warnings.
    """
    logger.info("validate_pipeline: %d nodes, %d edges, minio=%s",
                len(nodes), len(edges), "yes" if minio_client else "no")
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

    # ── Load source data & build initial schemas ─────────────
    df_cache: dict[str, pd.DataFrame | None] = {}
    schema_map: dict[str, SchemaMeta | None] = {}

    for src in sources:
        df = _load_source_df(src, minio_client)
        sid = src["id"]
        df_cache[sid] = df

        if df is not None:
            label = src.get("label", src.get("type", ""))

            # Apply column exclusions
            cols = src.get("config", {}).get("columns", [])
            excludes = [c["name"] for c in cols if isinstance(c, dict) and c.get("action") == "exclude"]
            if excludes:
                df = df.drop(columns=[c for c in excludes if c in df.columns], errors="ignore")
                df_cache[sid] = df

            schema_map[sid] = SchemaMeta.from_dataframe(df)

            # Source-level warnings
            if len(df) == 0:
                result.add_warning(sid, label, "Source data has 0 rows")
            all_null_cols = schema_map[sid].get_all_null_columns()
            if all_null_cols:
                result.add_warning(sid, label,
                                   f"All-null column(s): {', '.join(all_null_cols)}")
            const_cols = [c for c in schema_map[sid].get_constant_columns()
                          if c not in all_null_cols]
            if const_cols:
                result.add_warning(sid, label,
                                   f"Constant column(s) (single unique value): {', '.join(const_cols)}")
        else:
            # No MinIO client or load failed — build schema from config columns if available
            cfg_cols = src.get("config", {}).get("columns", [])
            if cfg_cols:
                from app.ml_studio.codegen.schema_tracker import ColumnMeta
                col_dict = {}
                for c in cfg_cols:
                    if isinstance(c, dict) and c.get("action") != "exclude":
                        name = c.get("name", "")
                        dtype = c.get("dtype", "object")
                        if name:
                            col_dict[name] = ColumnMeta(
                                name=name, dtype=dtype,
                                null_count=0, unique_count=10,
                                is_constant=False, all_null=False,
                                sample_size=100,
                            )
                if col_dict:
                    schema_map[sid] = SchemaMeta(columns=col_dict, row_count=100)
                else:
                    schema_map[sid] = None
            else:
                schema_map[sid] = None

    # ── Walk nodes in topological order ──────────────────────
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
        if parent_id and parent_id in schema_map and ntype not in ("source_csv", "source_parquet", "source_database"):
            schema_map[nid] = schema_map[parent_id].copy() if schema_map[parent_id] else None
            if parent_id in df_cache:
                df_cache[nid] = df_cache[parent_id]

        sm = schema_map.get(nid)  # SchemaMeta or None
        columns = sm.column_names() if sm else []
        numeric_cols = sm.get_numeric_columns() if sm else []

        # ── Source validation ────────────────────────────────
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

        # ── Transform: Fill Null ─────────────────────────────
        elif ntype == "transform_fillnull":
            strategy = cfg.get("strategy", "median")
            if sm and strategy in ("mean", "median"):
                all_null_num = [c for c in sm.get_all_null_columns()
                                if c in sm.get_numeric_columns()]
                if all_null_num:
                    result.add_warning(
                        nid, label,
                        f"All-null numeric column(s) {all_null_num}: "
                        f"{strategy} is NaN — fill has no effect, will fallback to 0")
            if strategy == "drop":
                result.add_warning(nid, label,
                                   "strategy=drop may remove all rows if every row has at least one null")

        # ── Transform: Type Cast ─────────────────────────────
        elif ntype == "transform_typecast":
            df = df_cache.get(nid)
            for cast in cfg.get("casts", []):
                col = cast.get("column", "")
                to_type = cast.get("to_type", "str")
                if col and columns and col not in columns:
                    result.add_error(nid, label, f"Column '{col}' does not exist in data")
                elif col and sm and col in sm.columns:
                    src_dtype = sm.columns[col].dtype
                    # object → int: check if convertible
                    if to_type in ("int", "float") and src_dtype in ("object", "category"):
                        if df is not None and col in df.columns:
                            converted = pd.to_numeric(df[col], errors="coerce")
                            n_failed = int(converted.isna().sum() - df[col].isna().sum())
                            if n_failed > 0:
                                result.add_error(
                                    nid, label,
                                    f"Column '{col}': {n_failed} value(s) cannot be converted to {to_type} "
                                    f"(non-numeric strings detected in sample)")
                    # int cast with nulls
                    if to_type == "int" and sm.columns[col].null_count > 0:
                        result.add_warning(
                            nid, label,
                            f"Column '{col}' has nulls — int64 cannot hold NaN, "
                            f"will use float64 with coerce fallback")

        # ── Transform: Drop Columns ──────────────────────────
        elif ntype == "transform_drop_cols":
            cols_str = cfg.get("columns", "")
            drop_list = [c.strip() for c in cols_str.split(",") if c.strip()] if isinstance(cols_str, str) else []
            for c in drop_list:
                if columns and c not in columns:
                    result.add_warning(nid, label, f"Column '{c}' not found — will be ignored")

        # ── Transform: Drop Duplicates ───────────────────────
        elif ntype == "transform_drop_dup":
            subset_str = cfg.get("subset", "")
            if subset_str:
                subset = [c.strip() for c in subset_str.split(",") if c.strip()] if isinstance(subset_str, str) else []
                for c in subset:
                    if columns and c not in columns:
                        result.add_error(nid, label, f"Subset column '{c}' does not exist")

        # ── Transform: Outlier ───────────────────────────────
        elif ntype == "transform_outlier":
            cols_str = cfg.get("columns", "")
            ocols = [c.strip() for c in cols_str.split(",") if c.strip()] if isinstance(cols_str, str) else []
            target_cols = ocols if ocols else numeric_cols
            for c in ocols:
                if columns and c in columns and c not in numeric_cols:
                    result.add_error(nid, label,
                                     f"Column '{c}' is not numeric — cannot detect outliers")
            # Constant column check
            if sm:
                const_targets = [c for c in target_cols
                                 if c in sm.columns and sm.columns[c].is_constant]
                if const_targets:
                    result.add_error(
                        nid, label,
                        f"Constant column(s) {const_targets}: IQR=0 would remove all rows. "
                        f"Exclude these columns or remove outlier node")
            result.add_warning(nid, label,
                               "Outlier removal may produce an empty DataFrame — "
                               "downstream nodes will abort if no rows remain")

        # ── Transform: Datetime ──────────────────────────────
        elif ntype == "transform_datetime":
            col = cfg.get("column", "")
            if not col:
                result.add_error(nid, label, "Datetime column is required")
            elif columns and col not in columns:
                result.add_error(nid, label, f"Column '{col}' does not exist")
            elif sm and col in sm.columns and sm.columns[col].all_null:
                result.add_warning(nid, label,
                                   f"Column '{col}' is all null — all extracted date parts will be 0")
            elif df_cache.get(nid) is not None and col in df_cache[nid].columns:
                try:
                    pd.to_datetime(df_cache[nid][col].head(5), errors="raise")
                except Exception:
                    result.add_warning(nid, label, f"Column '{col}' may not be a valid datetime")

        # ── Transform: Binning ───────────────────────────────
        elif ntype == "transform_binning":
            col = cfg.get("column", "")
            bins = cfg.get("bins", 5)
            if not col:
                result.add_error(nid, label, "Column is required for binning")
            elif columns and col not in columns:
                result.add_error(nid, label, f"Column '{col}' does not exist")
            elif columns and col in columns and col not in numeric_cols:
                result.add_error(nid, label, f"Column '{col}' is not numeric — cannot bin")
            elif sm and col in sm.columns:
                if sm.columns[col].is_constant:
                    result.add_error(nid, label,
                                     f"Column '{col}' is constant — pd.qcut/pd.cut will fail. "
                                     f"Remove binning or choose a different column")
                elif sm.columns[col].unique_count < bins:
                    result.add_warning(
                        nid, label,
                        f"Column '{col}' has only {sm.columns[col].unique_count} "
                        f"unique values but {bins} bins requested")

        # ── Transform: Sort ──────────────────────────────────
        elif ntype == "transform_sort":
            col = cfg.get("column", "")
            if not col:
                result.add_error(nid, label, "Sort column is required")
            elif columns and col not in columns:
                result.add_error(nid, label, f"Column '{col}' does not exist")

        # ── Transform: Filter ────────────────────────────────
        elif ntype == "transform_filter":
            df = df_cache.get(nid)
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

            # Try applying filter on sample to check if result is empty
            if df is not None and cfg.get("conditions"):
                try:
                    filtered = _apply_sample_filter(df, cfg)
                    if len(filtered) == 0:
                        result.add_warning(
                            nid, label,
                            "Filter removes ALL rows in sample data — "
                            "downstream nodes will receive an empty DataFrame")
                except Exception:
                    pass  # filter check is best-effort

        # ── Transform: Encode ────────────────────────────────
        elif ntype == "transform_encode":
            method = cfg.get("method", "label")
            if sm and method == "label":
                cat_with_null = [c for c in sm.get_categorical_columns()
                                 if c in sm.columns and sm.columns[c].null_count > 0]
                if cat_with_null:
                    result.add_warning(
                        nid, label,
                        f"Column(s) {cat_with_null} have nulls — "
                        f"LabelEncoder will encode NaN as string 'nan'")
            if sm and method == "onehot":
                high_card = [c for c in sm.get_categorical_columns()
                             if c in sm.columns and sm.columns[c].unique_count > 50]
                if high_card:
                    result.add_warning(
                        nid, label,
                        f"High-cardinality column(s) {high_card} — "
                        f"one-hot encoding may create many columns")

        # ── Transform: Scale ─────────────────────────────────
        elif ntype == "transform_scale":
            if sm:
                const_num = [c for c in sm.get_numeric_columns()
                             if c in sm.columns and sm.columns[c].is_constant]
                if const_num:
                    result.add_warning(
                        nid, label,
                        f"Constant numeric column(s) {const_num}: "
                        f"StandardScaler produces NaN (std=0) — these will be skipped")

        # ── Transform: Feature Engineering ───────────────────
        elif ntype == "transform_feature":
            for i, feat in enumerate(cfg.get("features", [])):
                name = feat.get("name", "")
                expr = feat.get("expression", "")
                if not name:
                    result.add_error(nid, label, f"Feature {i+1}: name is required")
                if not expr:
                    result.add_error(nid, label, f"Feature {i+1}: expression is required")
                elif sm:
                    # Check column references in expression
                    refs = extract_column_refs(expr)
                    for ref in refs:
                        if not sm.has_column(ref) and not sm.onehot_expanded:
                            result.add_error(
                                nid, label,
                                f"Feature '{name}': references column '{ref}' "
                                f"which does not exist at this point in the pipeline")
                    # Warn about division
                    if "/" in expr:
                        result.add_warning(
                            nid, label,
                            f"Feature '{name}': division may produce inf/NaN if divisor is 0")

        # ── Transform: Split ─────────────────────────────────
        elif ntype == "transform_split":
            target = cfg.get("target_column", "")
            if not target:
                result.add_error(nid, label, "Target column is required")
            elif columns and target not in columns:
                result.add_error(
                    nid, label,
                    f"Target column '{target}' does not exist at this point in the pipeline "
                    f"(available: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''})")
            elif sm and target in sm.columns:
                col_meta = sm.columns[target]
                if col_meta.all_null:
                    result.add_error(nid, label,
                                     f"Target '{target}' is all null — cannot train a model")
                elif col_meta.unique_count < 2:
                    result.add_error(
                        nid, label,
                        f"Target '{target}' has only {col_meta.unique_count} "
                        f"unique value(s) — need at least 2")
                # Stratify on continuous target
                stratify = cfg.get("stratify", True)
                if stratify and col_meta.dtype in ("float64", "float32", "float"):
                    result.add_warning(
                        nid, label,
                        f"Target '{target}' appears to be continuous (float) "
                        f"but stratify=True — stratification only works with discrete values")

                test_size = cfg.get("test_size", 0.2)
                n_test = int(sm.row_count * test_size)
                if n_test < 1:
                    result.add_warning(nid, label,
                                       "Test set would be empty with current split ratio")

            if sm and sm.may_be_empty:
                result.add_error(
                    nid, label,
                    "Upstream may produce an empty DataFrame (filter/outlier) — "
                    "split will fail")

        # ── Model validation ─────────────────────────────────
        elif ntype.startswith("model_"):
            if not parent_id:
                result.add_error(nid, label, "Model must be connected to a data source")
            parent_type = node_map[parent_id]["type"] if parent_id and parent_id in node_map else None
            if parent_type != "transform_split":
                result.add_warning(
                    nid, label,
                    "No Split node upstream — auto-split will use the last column as target. "
                    "Add a Split node to explicitly choose the target column")
            if sm and sm.may_be_empty:
                result.add_error(
                    nid, label,
                    "Upstream may produce an empty DataFrame — model training will fail")

        # ── Output validation ────────────────────────────────
        elif ntype == "output_csv":
            if not cfg.get("bucket"):
                result.add_error(nid, label, "Bucket is required")
            if not cfg.get("filename"):
                result.add_error(nid, label, "Filename is required")
            fname = cfg.get("filename", "")
            if fname and not fname.lower().endswith(".csv"):
                result.add_warning(nid, label, "Filename should end with .csv")

        elif ntype in ("output_evaluate", "output_mlflow", "output_kserve"):
            ancestor_types = _find_ancestors(nid, edges, node_map)
            has_model_upstream = any(t.startswith("model_") for t in ancestor_types)
            if not has_model_upstream:
                result.add_error(
                    nid, label,
                    "No Model node upstream — this output requires a trained model")

        # ── Apply schema effect for this node ────────────────
        if sm and ntype.startswith("transform_"):
            schema_map[nid] = apply_schema_effect(ntype, cfg, sm)

    return result


# ── Helper: apply filter on sample data ──────────────────────

def _apply_sample_filter(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Apply filter conditions to sample DataFrame for validation."""
    conditions = cfg.get("conditions", [])
    logic = cfg.get("logic", "AND")
    masks = []
    for cond in conditions:
        col = cond.get("column", "")
        if not col or col not in df.columns:
            continue
        op = cond.get("operator", ">")
        val = cond.get("value", "")
        if op == "not_null":
            masks.append(df[col].notna())
        elif op == "contains":
            masks.append(df[col].astype(str).str.contains(str(val), na=False))
        else:
            try:
                num_val = float(val)
                if op == ">":
                    masks.append(df[col] > num_val)
                elif op == ">=":
                    masks.append(df[col] >= num_val)
                elif op == "<":
                    masks.append(df[col] < num_val)
                elif op == "<=":
                    masks.append(df[col] <= num_val)
                elif op == "==":
                    masks.append(df[col] == num_val)
                elif op == "!=":
                    masks.append(df[col] != num_val)
            except (ValueError, TypeError):
                if op == "==":
                    masks.append(df[col] == val)
                elif op == "!=":
                    masks.append(df[col] != val)

    if not masks:
        return df

    if logic == "AND":
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m
    else:
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m

    return df[combined]
