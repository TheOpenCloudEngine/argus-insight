"""Code generators for Transform nodes (with defensive guards)."""


def gen_fillnull(var: str, parent: str, cfg: dict) -> list[str]:
    strategy = cfg.get("strategy", "median")
    lines = [f"# Transform: Fill Null ({strategy})", f"{var} = {parent}.copy()"]
    if strategy == "drop":
        lines.append(f"{var} = {var}.dropna()")
        lines.append(f'{var} = _check_not_empty({var}, "Fill Null (drop)")')
    elif strategy == "constant":
        val = repr(cfg.get("constant_value", "0"))
        lines.append(f"{var} = {var}.fillna({val})")
    elif strategy == "mean":
        lines.append(f"{var} = {var}.fillna({var}.mean(numeric_only=True))")
        lines.append(f'for _c in {var}.select_dtypes(include=["object","category"]).columns:')
        lines.append(f"    {var}[_c] = {var}[_c].fillna({var}[_c].mode().iloc[0] if not {var}[_c].mode().empty else '')")
        # Handle all-null columns where mean is NaN
        lines.append(f"_still_null = {var}.columns[{var}.isnull().all()].tolist()")
        lines.append(f"if _still_null:")
        lines.append(f'    print(f"  ⚠ All-null columns after fill: {{_still_null}}, filling with 0")')
        lines.append(f"    {var}[_still_null] = 0")
    elif strategy == "median":
        lines.append(f"{var} = {var}.fillna({var}.median(numeric_only=True))")
        lines.append(f'for _c in {var}.select_dtypes(include=["object","category"]).columns:')
        lines.append(f"    {var}[_c] = {var}[_c].fillna({var}[_c].mode().iloc[0] if not {var}[_c].mode().empty else '')")
        # Handle all-null columns where median is NaN
        lines.append(f"_still_null = {var}.columns[{var}.isnull().all()].tolist()")
        lines.append(f"if _still_null:")
        lines.append(f'    print(f"  ⚠ All-null columns after fill: {{_still_null}}, filling with 0")')
        lines.append(f"    {var}[_still_null] = 0")
    elif strategy == "mode":
        lines.append(f"for _c in {var}.columns:")
        lines.append(f"    if not {var}[_c].mode().empty:")
        lines.append(f"        {var}[_c] = {var}[_c].fillna({var}[_c].mode().iloc[0])")
    lines.append(f'print(f"[Fill Null] {{{var}.shape[0]}} rows")')
    lines.append("")
    return lines


def gen_drop_cols(var: str, parent: str, cfg: dict) -> list[str]:
    cols_str = cfg.get("columns", "")
    cols = [c.strip() for c in cols_str.split(",") if c.strip()] if isinstance(cols_str, str) else cols_str
    lines = ["# Transform: Drop Columns", f"{var} = {parent}.copy()"]
    if cols:
        lines.append(f'{var} = {var}.drop(columns={cols}, errors="ignore")')
    lines.append(f'print(f"[Drop Columns] {{{var}.shape[1]}} columns remain")')
    lines.append("")
    return lines


def gen_drop_dup(var: str, parent: str, cfg: dict) -> list[str]:
    subset_str = cfg.get("subset", "")
    subset = [c.strip() for c in subset_str.split(",") if c.strip()] if isinstance(subset_str, str) else []
    keep = cfg.get("keep", "first")
    lines = ["# Transform: Drop Duplicates", f"{var} = {parent}.copy()"]
    sub_arg = f"subset={subset}, " if subset else ""
    lines.append(f'{var} = {var}.drop_duplicates({sub_arg}keep="{keep}")')
    lines.append(f'print(f"[Drop Dup] {{{var}.shape[0]}} rows")')
    lines.append("")
    return lines


def gen_typecast(var: str, parent: str, cfg: dict) -> list[str]:
    casts = cfg.get("casts", [])
    type_map = {"int": "int64", "float": "float64", "str": "str",
                "category": "category", "bool": "bool", "datetime": "datetime64[ns]"}
    lines = ["# Transform: Type Cast", f"{var} = {parent}.copy()"]
    for c in casts:
        col, to = c.get("column", ""), c.get("to_type", "str")
        if not col:
            continue
        if to == "datetime":
            lines.append(f'{var}["{col}"] = pd.to_datetime({var}["{col}"], errors="coerce")')
        elif to in ("int", "float"):
            # Use safe cast with coerce fallback for numeric types
            target_dtype = type_map.get(to, to)
            lines.append(f'{var}["{col}"] = _safe_astype({var}["{col}"], "{target_dtype}")')
        else:
            lines.append(f'{var}["{col}"] = {var}["{col}"].astype("{type_map.get(to, to)}")')
    lines.append(f'print(f"[Type Cast] {len(casts)} column(s) cast")')
    lines.append("")
    return lines


def gen_outlier(var: str, parent: str, cfg: dict) -> list[str]:
    method = cfg.get("method", "iqr")
    threshold = cfg.get("threshold", 1.5 if method == "iqr" else 3.0)
    cols_str = cfg.get("columns", "")
    cols = [c.strip() for c in cols_str.split(",") if c.strip()] if isinstance(cols_str, str) else []
    lines = [f"# Transform: Outlier Remove ({method.upper()})", f"{var} = {parent}.copy()"]
    col_expr = repr(cols) if cols else f'{var}.select_dtypes(include="number").columns.tolist()'
    lines.append(f"_ocols = {col_expr}")
    if method == "zscore":
        # Use safe z-score mask that handles constant columns
        lines.append(f"_mask = _safe_zscore_mask({var}[_ocols], threshold={threshold})")
        lines.append(f"{var} = {var}[_mask]")
    else:
        # Use safe IQR mask per column that handles IQR=0 (constant columns)
        lines.append(f"_mask = pd.Series(True, index={var}.index)")
        lines.append("for _c in _ocols:")
        lines.append(f"    _mask &= _safe_iqr_mask({var}[_c], threshold={threshold})")
        lines.append(f"{var} = {var}[_mask]")
    lines.append(f'{var} = _check_not_empty({var}, "Outlier")')
    lines.append(f'print(f"[Outlier] {{{var}.shape[0]}} rows after removal")')
    lines.append("")
    return lines


def gen_datetime(var: str, parent: str, cfg: dict) -> list[str]:
    col = cfg.get("column", "")
    parts = cfg.get("extract", ["year", "month", "day", "dayofweek"])
    lines = ["# Transform: Datetime Extract", f"{var} = {parent}.copy()"]
    if col:
        lines.append(f'{var}["{col}"] = pd.to_datetime({var}["{col}"], errors="coerce")')
        # Warn if all values are NaT
        lines.append(f'if {var}["{col}"].isna().all():')
        lines.append(f'    print("  ⚠ All values in \'{col}\' are invalid dates (NaT)")')
        for p in parts:
            if p == "weekofyear":
                lines.append(f'{var}["{col}_{p}"] = {var}["{col}"].dt.isocalendar().week.astype(int)')
            else:
                lines.append(f'{var}["{col}_{p}"] = {var}["{col}"].dt.{p}')
        lines.append(f'{var} = {var}.drop(columns=["{col}"])')
        # Fill NaN from NaT datetime parts with 0
        part_cols = [f"{col}_{p}" for p in parts]
        lines.append(f"for _p in {part_cols}:")
        lines.append(f"    if _p in {var}.columns and {var}[_p].isna().any():")
        lines.append(f"        {var}[_p] = {var}[_p].fillna(0).astype(int)")
    lines.append(f'print(f"[Datetime] {len(parts)} parts extracted")')
    lines.append("")
    return lines


def gen_binning(var: str, parent: str, cfg: dict) -> list[str]:
    col = cfg.get("column", "")
    bins = cfg.get("bins", 5)
    strategy = cfg.get("strategy", "uniform")
    labels_str = cfg.get("labels", "")
    labels = [l.strip() for l in labels_str.split(",") if l.strip()] if labels_str else []
    lines = [f"# Transform: Binning ({strategy})", f"{var} = {parent}.copy()"]
    if col:
        lbl_arg = f", labels={labels}" if len(labels) == bins else ""
        # Wrap in try/except for constant columns or edge cases
        lines.append("try:")
        if strategy == "quantile":
            lines.append(f'    {var}["{col}_bin"] = pd.qcut({var}["{col}"], q={bins}{lbl_arg}, duplicates="drop")')
        else:
            lines.append(f'    {var}["{col}_bin"] = pd.cut({var}["{col}"], bins={bins}{lbl_arg})')
        lines.append("except ValueError as _e:")
        lines.append(f'    print(f"  ⚠ Binning failed for \'{col}\': {{_e}}, using single bin")')
        lines.append(f'    {var}["{col}_bin"] = "all"')
    lines.append(f'print(f"[Binning] {col} → {bins} bins")')
    lines.append("")
    return lines


def gen_sample(var: str, parent: str, cfg: dict) -> list[str]:
    n = cfg.get("n_rows", 10000)
    seed = cfg.get("random_seed", 42)
    lines = ["# Transform: Sample", f"{var} = {parent}.copy()"]
    lines.append(f"if len({var}) > 0:")
    lines.append(f"    {var} = {var}.sample(n=min({n}, len({var})), random_state={seed})")
    lines.append(f'print(f"[Sample] {{{var}.shape[0]}} rows")')
    lines.append("")
    return lines


def gen_sort(var: str, parent: str, cfg: dict) -> list[str]:
    col = cfg.get("column", "")
    asc = cfg.get("ascending", True)
    lines = ["# Transform: Sort", f"{var} = {parent}.copy()"]
    if col:
        lines.append(f'{var} = {var}.sort_values("{col}", ascending={asc}).reset_index(drop=True)')
    lines.append(f'print(f"[Sort] by {col}")')
    lines.append("")
    return lines


def gen_encode(var: str, parent: str, cfg: dict) -> list[str]:
    method = cfg.get("method", "label")
    lines = [f"# Transform: Encode ({method})", f"{var} = {parent}.copy()"]
    if method == "onehot":
        drop = ", drop_first=True" if cfg.get("drop_first") else ""
        lines.append(f'_cat_cols = {var}.select_dtypes(include=["object","category"]).columns.tolist()')
        lines.append(f"{var} = pd.get_dummies({var}, columns=_cat_cols{drop})")
    elif method == "label":
        lines.append("from sklearn.preprocessing import LabelEncoder as _LE")
        lines.append(f'for _c in {var}.select_dtypes(include=["object","category"]).columns:')
        lines.append(f"    _nulls = {var}[_c].isna().sum()")
        lines.append(f"    if _nulls > 0:")
        lines.append(f'        print(f"  ⚠ Column \'{{_c}}\' has {{_nulls}} nulls, encoded as string \'nan\'")')
        lines.append(f"    {var}[_c] = _LE().fit_transform({var}[_c].astype(str))")
    elif method == "ordinal":
        order_str = cfg.get("ordinal_order", "")
        order = [o.strip() for o in order_str.split(",") if o.strip()]
        if order:
            lines.append(f"from sklearn.preprocessing import OrdinalEncoder")
            lines.append(f"# Ordinal order: {order}")
    lines.append(f'print(f"[Encode] {method} applied")')
    lines.append("")
    return lines


def gen_scale(var: str, parent: str, cfg: dict) -> list[str]:
    method = cfg.get("method", "standard")
    cls_map = {"standard": "StandardScaler", "minmax": "MinMaxScaler", "robust": "RobustScaler"}
    cls = cls_map.get(method, "StandardScaler")
    lines = [f"# Transform: Scale ({method})", f"{var} = {parent}.copy()"]
    lines.append(f"from sklearn.preprocessing import {cls}")
    if method == "minmax":
        lo, hi = cfg.get("range_min", 0), cfg.get("range_max", 1)
        lines.append(f"_scaler = {cls}(feature_range=({lo}, {hi}))")
    else:
        lines.append(f"_scaler = {cls}()")
    lines.append(f'_num = {var}.select_dtypes(include="number").columns.tolist()')
    # Use safe scale that skips constant columns
    lines.append(f"{var} = _safe_scale({var}, _num, _scaler)")
    lines.append(f'print(f"[Scale] {{len(_num)}} numeric columns scaled")')
    lines.append("")
    return lines


def gen_filter(var: str, parent: str, cfg: dict) -> list[str]:
    conditions = cfg.get("conditions", [])
    logic = cfg.get("logic", "AND")
    lines = ["# Transform: Filter Rows", f"{var} = {parent}.copy()"]
    parts = []
    for cond in conditions:
        col = cond.get("column", "")
        if not col:
            continue
        op = cond.get("operator", ">")
        val = cond.get("value", "")
        if op == "not_null":
            parts.append(f'({var}["{col}"].notna())')
        elif op == "contains":
            parts.append(f'({var}["{col}"].astype(str).str.contains({repr(val)}, na=False))')
        else:
            # Try numeric
            try:
                num_val = float(val)
                parts.append(f'({var}["{col}"] {op} {num_val})')
            except (ValueError, TypeError):
                parts.append(f'({var}["{col}"] {op} {repr(val)})')
    if parts:
        joiner = " & " if logic == "AND" else " | "
        lines.append(f"{var} = {var}[{joiner.join(parts)}]")
    lines.append(f'{var} = _check_not_empty({var}, "Filter")')
    lines.append(f'print(f"[Filter] {{{var}.shape[0]}} rows remain")')
    lines.append("")
    return lines


def gen_feature(var: str, parent: str, cfg: dict) -> list[str]:
    features = cfg.get("features", [])
    lines = ["# Transform: Feature Engineering", f"{var} = {parent}.copy()"]
    for f in features:
        name, expr = f.get("name", ""), f.get("expression", "")
        if name and expr:
            # Wrap each expression in try/except + replace inf with NaN
            lines.append("try:")
            lines.append(f'    {var}["{name}"] = {expr}')
            lines.append(f'    {var}["{name}"] = {var}["{name}"].replace([np.inf, -np.inf], np.nan)')
            lines.append("except Exception as _e:")
            lines.append(f'    print(f"  ⚠ Feature \'{name}\' failed: {{_e}}")')
            lines.append(f'    {var}["{name}"] = np.nan')
    lines.append(f'print(f"[Feature Eng] {len(features)} new feature(s)")')
    lines.append("")
    return lines


def gen_split(var: str, parent: str, cfg: dict) -> list[str]:
    target = cfg.get("target_column", "")
    test_size = cfg.get("test_size", 0.2)
    seed = cfg.get("random_seed", 42)
    stratify = cfg.get("stratify", True)
    lines = ["# Transform: Train/Test Split", f"{var} = {parent}.copy()"]
    lines.append(f'{var} = _check_not_empty({var}, "Split input")')
    if target:
        # Runtime check that target column exists
        lines.append(f'if "{target}" not in {var}.columns:')
        lines.append(f'    raise RuntimeError(f"Target column \'{target}\' not found. '
                     f'Available: {{{var}.columns.tolist()}}")')
        strat_arg = ", stratify=y" if stratify else ""
        lines.append(f'X, y = _prepare_for_model({var}, "{target}")')
        lines.append(f"X_train, X_test, y_train, y_test = train_test_split("
                     f"X, y, test_size={test_size}, random_state={seed}{strat_arg})")
        lines.append(f'print(f"[Split] Train: {{X_train.shape}}, Test: {{X_test.shape}}")')
    lines.append("")
    return lines


TRANSFORM_GENERATORS: dict[str, callable] = {
    "transform_fillnull": gen_fillnull,
    "transform_drop_cols": gen_drop_cols,
    "transform_drop_dup": gen_drop_dup,
    "transform_typecast": gen_typecast,
    "transform_outlier": gen_outlier,
    "transform_datetime": gen_datetime,
    "transform_binning": gen_binning,
    "transform_sample": gen_sample,
    "transform_sort": gen_sort,
    "transform_encode": gen_encode,
    "transform_scale": gen_scale,
    "transform_filter": gen_filter,
    "transform_feature": gen_feature,
    "transform_split": gen_split,
}
