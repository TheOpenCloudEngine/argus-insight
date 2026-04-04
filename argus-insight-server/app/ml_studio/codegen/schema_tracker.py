"""Schema propagation engine for pipeline validation.

Tracks column names, dtypes, null counts, and uniqueness through
the DAG so that downstream nodes can be validated against the
*actual* schema they will receive at runtime — not just the
original source schema.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

import pandas as pd


# ── Column & Schema metadata ────────────────────────────────────

@dataclass
class ColumnMeta:
    name: str
    dtype: str  # int64, float64, object, category, datetime64[ns], bool
    null_count: int = 0
    unique_count: int = 0
    is_constant: bool = False  # unique_count <= 1
    all_null: bool = False  # null_count == sample_size
    sample_size: int = 0


@dataclass
class SchemaMeta:
    columns: dict[str, ColumnMeta] = field(default_factory=dict)
    row_count: int = 0
    may_be_empty: bool = False
    onehot_expanded: bool = False  # exact column names unknown after one-hot

    # ── Constructors ─────────────────────────────────────────

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> SchemaMeta:
        cols: dict[str, ColumnMeta] = {}
        n = len(df)
        for c in df.columns:
            s = df[c]
            nc = int(s.isna().sum())
            uc = int(s.nunique(dropna=True))
            cols[c] = ColumnMeta(
                name=c,
                dtype=str(s.dtype),
                null_count=nc,
                unique_count=uc,
                is_constant=uc <= 1,
                all_null=nc >= n,
                sample_size=n,
            )
        return cls(columns=cols, row_count=n)

    def copy(self) -> SchemaMeta:
        return copy.deepcopy(self)

    # ── Query helpers ────────────────────────────────────────

    def has_column(self, name: str) -> bool:
        return name in self.columns

    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    def get_numeric_columns(self) -> list[str]:
        numeric = {"int64", "int32", "float64", "float32", "int", "float"}
        return [c.name for c in self.columns.values() if c.dtype in numeric]

    def get_categorical_columns(self) -> list[str]:
        cats = {"object", "category"}
        return [c.name for c in self.columns.values() if c.dtype in cats]

    def get_constant_columns(self) -> list[str]:
        return [c.name for c in self.columns.values() if c.is_constant]

    def get_all_null_columns(self) -> list[str]:
        return [c.name for c in self.columns.values() if c.all_null]

    # ── Mutation helpers (return new SchemaMeta) ─────────────

    def drop_columns(self, names: list[str]) -> SchemaMeta:
        s = self.copy()
        for n in names:
            s.columns.pop(n, None)
        return s

    def add_column(self, name: str, dtype: str = "float64") -> SchemaMeta:
        s = self.copy()
        s.columns[name] = ColumnMeta(
            name=name, dtype=dtype,
            null_count=0, unique_count=s.row_count,
            is_constant=False, all_null=False,
            sample_size=s.row_count,
        )
        return s

    def update_dtype(self, col: str, new_dtype: str) -> SchemaMeta:
        s = self.copy()
        if col in s.columns:
            s.columns[col].dtype = new_dtype
        return s

    def clear_nulls(self, cols: list[str] | None = None) -> SchemaMeta:
        """Mark columns as having no nulls (after fillna)."""
        s = self.copy()
        targets = cols if cols else list(s.columns.keys())
        for c in targets:
            if c in s.columns:
                s.columns[c].null_count = 0
                s.columns[c].all_null = False
        return s

    def mark_may_be_empty(self) -> SchemaMeta:
        s = self.copy()
        s.may_be_empty = True
        return s


# ── Per-transform schema effect functions ────────────────────

def _effect_fillnull(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    strategy = cfg.get("strategy", "median")
    if strategy == "drop":
        return schema.mark_may_be_empty().clear_nulls()
    return schema.clear_nulls()


def _effect_drop_cols(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    cols_str = cfg.get("columns", "")
    cols = [c.strip() for c in cols_str.split(",") if c.strip()] if isinstance(cols_str, str) else cols_str
    return schema.drop_columns(cols)


def _effect_drop_dup(schema: SchemaMeta, _cfg: dict) -> SchemaMeta:
    return schema.copy()


def _effect_typecast(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    type_map = {"int": "int64", "float": "float64", "str": "object",
                "category": "category", "bool": "bool", "datetime": "datetime64[ns]"}
    s = schema.copy()
    for c in cfg.get("casts", []):
        col = c.get("column", "")
        to = c.get("to_type", "str")
        if col in s.columns:
            s.columns[col].dtype = type_map.get(to, to)
    return s


def _effect_outlier(schema: SchemaMeta, _cfg: dict) -> SchemaMeta:
    return schema.mark_may_be_empty()


def _effect_datetime(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    col = cfg.get("column", "")
    parts = cfg.get("extract", ["year", "month", "day", "dayofweek"])
    if not col or col not in schema.columns:
        return schema.copy()
    s = schema.drop_columns([col])
    for p in parts:
        s = s.add_column(f"{col}_{p}", "int64")
    return s


def _effect_binning(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    col = cfg.get("column", "")
    if col:
        return schema.add_column(f"{col}_bin", "category")
    return schema.copy()


def _effect_sample(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    s = schema.copy()
    n = cfg.get("n_rows", 10000)
    s.row_count = min(n, s.row_count)
    return s


def _effect_sort(schema: SchemaMeta, _cfg: dict) -> SchemaMeta:
    return schema.copy()


def _effect_encode(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    method = cfg.get("method", "label")
    s = schema.copy()
    if method == "label":
        for c in list(s.columns.values()):
            if c.dtype in ("object", "category"):
                s.columns[c.name].dtype = "int64"
    elif method == "onehot":
        s.onehot_expanded = True
        # Remove original categorical columns
        cats = [c.name for c in s.columns.values() if c.dtype in ("object", "category")]
        s = s.drop_columns(cats)
        # Exact new column names depend on data — mark as expanded
        s.onehot_expanded = True
    return s


def _effect_scale(schema: SchemaMeta, _cfg: dict) -> SchemaMeta:
    return schema.copy()


def _effect_filter(schema: SchemaMeta, _cfg: dict) -> SchemaMeta:
    return schema.mark_may_be_empty()


def _effect_feature(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    s = schema.copy()
    for f in cfg.get("features", []):
        name = f.get("name", "")
        if name:
            s = s.add_column(name, "float64")
    return s


def _effect_split(schema: SchemaMeta, cfg: dict) -> SchemaMeta:
    target = cfg.get("target_column", "")
    s = schema.copy()
    if target and target in s.columns:
        s = s.drop_columns([target])
    return s


SCHEMA_EFFECTS: dict[str, callable] = {
    "transform_fillnull": _effect_fillnull,
    "transform_drop_cols": _effect_drop_cols,
    "transform_drop_dup": _effect_drop_dup,
    "transform_typecast": _effect_typecast,
    "transform_outlier": _effect_outlier,
    "transform_datetime": _effect_datetime,
    "transform_binning": _effect_binning,
    "transform_sample": _effect_sample,
    "transform_sort": _effect_sort,
    "transform_encode": _effect_encode,
    "transform_scale": _effect_scale,
    "transform_filter": _effect_filter,
    "transform_feature": _effect_feature,
    "transform_split": _effect_split,
}


def apply_schema_effect(node_type: str, cfg: dict, schema: SchemaMeta) -> SchemaMeta:
    """Apply a node's schema effect and return the new schema."""
    fn = SCHEMA_EFFECTS.get(node_type)
    if fn:
        return fn(schema, cfg)
    return schema.copy()


# ── Expression column reference extraction ───────────────────

_COL_REF_RE = re.compile(r'(?:df|{var})\["([^"]+)"\]|(?:df|{var})\[\'([^\']+)\'\]')


def extract_column_refs(expression: str) -> list[str]:
    """Extract column name references from a feature expression.

    Recognises patterns like: df["col"], df['col'], {var}["col"]
    """
    refs = []
    for m in _COL_REF_RE.finditer(expression):
        refs.append(m.group(1) or m.group(2))
    return refs
