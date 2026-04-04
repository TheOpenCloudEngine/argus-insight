"""Code generators for Output nodes."""


def gen_evaluate(var: str, cfg: dict) -> list[str]:
    lines = [
        "# Output: Evaluate",
        "import json as _json",
        "from sklearn.metrics import (classification_report, accuracy_score, f1_score,",
        "                             mean_squared_error, r2_score, mean_absolute_error)",
        "",
        '_eval_result = {"status": "completed", "message": "Pipeline executed successfully"}',
        "",
        "# Detect task type: classification vs regression",
        "_is_classification = len(np.unique(y_test)) <= 20",
        "",
        "# Evaluate all registered models",
        "_leaderboard = []",
        "_best_score = -1",
        "_best_entry = None",
        "",
        "for _mi, _m in enumerate(_models if _models else [{'name': type(model).__name__, 'model': model, 'y_pred': y_pred, 'train_time': 0}]):",
        "    _cur_model = _m['model']",
        "    _cur_pred = _m['y_pred']",
        "    _cur_name = _m['name']",
        "    _cur_time = _m.get('train_time', 0)",
        "    try:",
        "        if _is_classification:",
        "            _acc = float(accuracy_score(y_test, _cur_pred))",
        "            _f1 = float(f1_score(y_test, _cur_pred, average='weighted', zero_division=0))",
        "            _metrics = {'accuracy': round(_acc, 4), 'f1_weighted': round(_f1, 4)}",
        "            _score = _f1",
        "        else:",
        "            _rmse = float(np.sqrt(mean_squared_error(y_test, _cur_pred)))",
        "            _r2 = float(r2_score(y_test, _cur_pred))",
        "            _mae = float(mean_absolute_error(y_test, _cur_pred))",
        "            _metrics = {'rmse': round(_rmse, 4), 'r2': round(_r2, 4), 'mae': round(_mae, 4)}",
        "            _score = _r2",
        "        _leaderboard.append({",
        "            'rank': 0,",
        "            'model_name': _cur_name,",
        "            'metrics': _metrics,",
        "            'training_time_seconds': round(_cur_time, 2),",
        "        })",
        "        if _score > _best_score:",
        "            _best_score = _score",
        "            _best_entry = {'model_name': _cur_name, 'metrics': _metrics, 'model_obj': _cur_model, 'y_pred': _cur_pred}",
        "    except Exception as _e:",
        "        print(f'  ⚠ Evaluation failed for {_cur_name}: {_e}')",
        "",
        "# Sort leaderboard and assign ranks",
        "if _is_classification:",
        "    _leaderboard.sort(key=lambda x: x['metrics'].get('f1_weighted', 0), reverse=True)",
        "else:",
        "    _leaderboard.sort(key=lambda x: x['metrics'].get('r2', 0), reverse=True)",
        "for _ri, _entry in enumerate(_leaderboard):",
        "    _entry['rank'] = _ri + 1",
        "",
        "# Print results",
        "if _best_entry:",
        "    model = _best_entry['model_obj']",
        "    y_pred = _best_entry['y_pred']",
        "    if _is_classification:",
        '        print("\\n=== Classification Results ===")',
        "        print(classification_report(y_test, y_pred, zero_division=0))",
        "    else:",
        '        print("\\n=== Regression Results ===")',
        "        for _k, _v in _best_entry['metrics'].items():",
        '            print(f"  {_k}: {_v}")',
        "",
        "if len(_leaderboard) > 1:",
        '    print(f"\\n=== Leaderboard ({len(_leaderboard)} models) ===")',
        "    for _entry in _leaderboard:",
        "        _mk = ', '.join(f'{k}={v}' for k, v in _entry['metrics'].items())",
        '        print(f"  #{_entry[\'rank\']} {_entry[\'model_name\']}: {_mk} ({_entry[\'training_time_seconds\']}s)")',
        "",
        "# Build RESULT_JSON",
        "if _best_entry:",
        "    _eval_result['best_model'] = {'model_name': _best_entry['model_name'], 'metrics': _best_entry['metrics']}",
        "if len(_leaderboard) > 0:",
        "    _eval_result['leaderboard'] = _leaderboard",
        "",
        "# Classification report for best model",
        "if _is_classification and _best_entry:",
        "    _report = classification_report(y_test, _best_entry['y_pred'], zero_division=0, output_dict=True)",
        "    _class_metrics = []",
        "    for _cls, _vals in _report.items():",
        "        if isinstance(_vals, dict) and 'precision' in _vals:",
        "            _class_metrics.append({",
        '                "class": str(_cls),',
        '                "precision": round(_vals["precision"], 4),',
        '                "recall": round(_vals["recall"], 4),',
        '                "f1_score": round(_vals["f1-score"], 4),',
        '                "support": int(_vals["support"]),',
        "            })",
        "    _eval_result['classification_report'] = _class_metrics",
        "",
        "# Feature importance for best model",
        "if _best_entry:",
        "    _bm = _best_entry['model_obj']",
        '    if hasattr(_bm, "feature_importances_"):',
        "        _imp = pd.Series(_bm.feature_importances_, index=X_train.columns).sort_values(ascending=False)",
        '        print("\\nFeature Importance (top 10):")',
        "        print(_imp.head(10))",
        "        _eval_result['feature_importance'] = {k: round(float(v), 4) for k, v in _imp.head(15).items()}",
        "    elif hasattr(_bm, 'coef_'):",
        "        _coef = pd.Series(np.abs(_bm.coef_[0]) if _bm.coef_.ndim > 1 else np.abs(_bm.coef_), index=X_train.columns).sort_values(ascending=False)",
        "        _eval_result['feature_importance'] = {k: round(float(v), 4) for k, v in _coef.head(15).items()}",
        "",
        "# Emit structured result JSON",
        'print(f"RESULT_JSON:{_json.dumps(_eval_result)}", flush=True)',
        "",
    ]
    return lines


def gen_mlflow(var: str, cfg: dict) -> list[str]:
    exp = cfg.get("experiment_name", "default")
    lines = [
        "# Output: MLflow Log",
        "import mlflow",
        f'mlflow.set_experiment("{exp}")',
        "with mlflow.start_run():",
        "    mlflow.log_params(model.get_params())",
        '    mlflow.sklearn.log_model(model, "model")',
        '    print("[MLflow] Model and params logged")',
        "",
    ]
    return lines


def gen_kserve(var: str, cfg: dict) -> list[str]:
    cpu = cfg.get("cpu", "1")
    mem = cfg.get("memory", "2Gi")
    lines = [
        f"# Output: KServe Deploy ({cpu} CPU, {mem} memory)",
        "import joblib",
        'joblib.dump(model, "model.joblib")',
        'print("[KServe] Model saved, ready for deployment")',
        "",
    ]
    return lines


def gen_csv_export(var: str, cfg: dict) -> list[str]:
    bucket = cfg.get("bucket", "")
    path = cfg.get("path", "")
    filename = cfg.get("filename", "")
    key = "/".join(p for p in [path, filename] if p).replace("//", "/")
    lines = [
        "# Output: CSV Export",
        "_result_df = X_test.copy()",
        '_result_df["prediction"] = y_pred',
        f'_minio_upload("{bucket}", "{key}", _result_df)',
        f'print(f"[Export] {{len(_result_df)}} rows → s3://{bucket}/{key}")',
        "",
    ]
    return lines


OUTPUT_GENERATORS = {
    "output_evaluate": gen_evaluate,
    "output_mlflow": gen_mlflow,
    "output_kserve": gen_kserve,
    "output_csv": gen_csv_export,
}
