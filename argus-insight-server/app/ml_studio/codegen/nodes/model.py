"""Code generators for Model nodes."""


def gen_model(var: str, node_type: str, cfg: dict, parent_type: str | None, parent_var: str | None) -> list[str]:
    """Generate model training code.

    If the parent is not a Split node, auto-split is injected.
    """
    lines = []
    has_split = parent_type == "transform_split"

    # Auto-split if no explicit Split upstream
    if not has_split and parent_var:
        lines.append("# Auto-split: no Train/Test Split node — using last column as target")
        lines.append(f"X, y = _prepare_for_model({parent_var}, {parent_var}.columns[-1])")
        lines.append("X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)")
        lines.append(f'print(f"[Auto-Split] Train: {{X_train.shape}}, Test: {{X_test.shape}}")')
        lines.append("")

    # Model instantiation
    if node_type == "model_xgboost":
        n = cfg.get("n_estimators", 100)
        d = cfg.get("max_depth", 6)
        lr = cfg.get("learning_rate", 0.1)
        lines.append("from xgboost import XGBClassifier, XGBRegressor")
        lines.append(f"model = XGBClassifier(n_estimators={n}, max_depth={d}, "
                     f"learning_rate={lr}, random_state=42, verbosity=0, eval_metric='logloss')")
    elif node_type == "model_lightgbm":
        n = cfg.get("n_estimators", 100)
        d = cfg.get("max_depth", -1)
        lr = cfg.get("learning_rate", 0.1)
        lines.append("from lightgbm import LGBMClassifier, LGBMRegressor")
        lines.append(f"model = LGBMClassifier(n_estimators={n}, max_depth={d}, "
                     f"learning_rate={lr}, random_state=42, verbose=-1)")
    elif node_type == "model_rf":
        n = cfg.get("n_estimators", 100)
        d = cfg.get("max_depth")
        d_arg = f", max_depth={d}" if d else ""
        lines.append("from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor")
        lines.append(f"model = RandomForestClassifier(n_estimators={n}{d_arg}, random_state=42, n_jobs=-1)")
    elif node_type == "model_linear":
        mi = cfg.get("max_iter", 500)
        lines.append("from sklearn.linear_model import LogisticRegression, LinearRegression")
        lines.append(f"model = LogisticRegression(max_iter={mi}, random_state=42)")
    elif node_type == "model_automl":
        lines.append("from sklearn.ensemble import RandomForestClassifier")
        lines.append("model = RandomForestClassifier(n_estimators=100, random_state=42)")

    lines.append("")
    lines.append("model.fit(X_train, y_train)")
    lines.append("y_pred = model.predict(X_test)")
    lines.append('print(f"[Model] {type(model).__name__} trained")')
    lines.append("")
    return lines
