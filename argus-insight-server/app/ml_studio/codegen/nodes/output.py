"""Code generators for Output nodes."""


def gen_evaluate(var: str, cfg: dict) -> list[str]:
    lines = [
        "# Output: Evaluate",
        "from sklearn.metrics import classification_report, mean_squared_error, r2_score",
        'print("\\n=== Evaluation Results ===")',
        "try:",
        "    print(classification_report(y_test, y_pred, zero_division=0))",
        "except Exception:",
        '    print(f"  RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")',
        '    print(f"  R²:   {r2_score(y_test, y_pred):.4f}")',
        "",
        'if hasattr(model, "feature_importances_"):',
        "    _imp = pd.Series(model.feature_importances_, index=X_train.columns).sort_values(ascending=False)",
        '    print("\\nFeature Importance (top 10):")',
        "    print(_imp.head(10))",
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
