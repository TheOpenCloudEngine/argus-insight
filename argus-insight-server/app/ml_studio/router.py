"""ML Studio API endpoints."""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.database import get_session, async_session
from app.ml_studio import service
from app.ml_studio.schemas import (
    CodegenRequest,
    CodegenResponse,
    DataPreviewRequest,
    DataPreviewResponse,
    ColumnInfo,
    PipelineExecuteRequest,
    PipelineListResponse,
    PipelineResponse,
    PipelineSaveRequest,
    PipelineUpdateRequest,
    TrainJobListResponse,
    TrainJobResponse,
    TrainRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml-studio", tags=["ml-studio"])


# ---------------------------------------------------------------------------
# Data preview
# ---------------------------------------------------------------------------

@router.post("/preview", response_model=DataPreviewResponse)
async def preview_data(
    req: DataPreviewRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Preview a dataset: schema, statistics, sample rows.

    Supports CSV, TSV, Parquet, and Excel (.xlsx/.xls).
    Uses pandas for parsing and type inference.
    """
    columns: list[ColumnInfo] = []
    sample_rows: list[dict] = []
    row_count = 0

    if req.source_type == "minio" and req.path:
        try:
            from app.settings.service import get_config_by_category
            cfg = await get_config_by_category(session, "argus")
            s3_endpoint = cfg.get("object_storage_endpoint", "")
            s3_access = cfg.get("object_storage_access_key", "")
            s3_secret = cfg.get("object_storage_secret_key", "")

            if s3_endpoint and s3_access:
                import io
                import pandas as pd
                from minio import Minio
                from urllib.parse import urlparse

                parsed = urlparse(s3_endpoint)
                client = Minio(
                    parsed.netloc,
                    access_key=s3_access,
                    secret_key=s3_secret,
                    secure=parsed.scheme == "https",
                )

                bucket = req.bucket or ""
                obj_path = req.path
                response = client.get_object(bucket, obj_path)
                raw = response.read()
                response.close()
                response.release_conn()

                # Parse based on file extension
                ext = obj_path.rsplit(".", 1)[-1].lower() if "." in obj_path else ""
                buf = io.BytesIO(raw)

                if ext == "parquet":
                    df = pd.read_parquet(buf)
                elif ext in ("xlsx", "xls"):
                    df = pd.read_excel(buf, sheet_name=0)
                elif ext == "tsv":
                    df = pd.read_csv(buf, sep="\t")
                else:
                    df = pd.read_csv(buf)

                row_count = len(df)

                for col_name in df.columns:
                    series = df[col_name]
                    dtype = _infer_column_type(series)
                    missing = int(series.isna().sum())
                    unique = int(series.nunique())
                    samples = [str(v) for v in series.dropna().head(3).tolist()]

                    min_val = None
                    max_val = None
                    cat_vals = None

                    if dtype in ("integer", "float"):
                        numeric = pd.to_numeric(series, errors="coerce")
                        min_val = str(numeric.min()) if not numeric.isna().all() else None
                        max_val = str(numeric.max()) if not numeric.isna().all() else None
                    elif dtype == "datetime":
                        try:
                            dt = pd.to_datetime(series, errors="coerce", format="mixed")
                            min_val = str(dt.min()) if not dt.isna().all() else None
                            max_val = str(dt.max()) if not dt.isna().all() else None
                        except Exception:
                            pass
                    elif dtype == "category":
                        cat_vals = sorted(series.dropna().unique().astype(str).tolist())

                    columns.append(ColumnInfo(
                        name=str(col_name),
                        dtype=dtype,
                        missing=missing,
                        unique=unique,
                        sample_values=samples,
                        min_value=min_val,
                        max_value=max_val,
                        category_values=cat_vals,
                    ))

                sample_rows = df.head(5).fillna("").astype(str).to_dict(orient="records")

        except Exception as e:
            logger.warning("Failed to preview data: %s", e)

    return DataPreviewResponse(
        columns=columns,
        row_count=row_count,
        sample_rows=sample_rows,
    )


def _infer_column_type(series: "pd.Series") -> str:
    """Infer column type: boolean > integer > float > datetime > category > string."""
    import pandas as pd

    non_null = series.dropna()
    if len(non_null) == 0:
        return "string"

    # Boolean: {true, false}, {yes, no}, {0, 1}, {t, f}
    unique_lower = set(non_null.astype(str).str.strip().str.lower().unique())
    bool_sets = [{"true", "false"}, {"yes", "no"}, {"0", "1"}, {"t", "f"}, {"y", "n"}]
    if len(unique_lower) <= 2 and any(unique_lower <= bs for bs in bool_sets):
        return "boolean"

    # Integer / Float
    try:
        numeric = pd.to_numeric(non_null, errors="raise")
        if (numeric == numeric.astype(int)).all():
            return "integer"
        return "float"
    except (ValueError, TypeError):
        pass

    # Datetime
    try:
        pd.to_datetime(non_null, errors="raise", format="mixed")
        return "datetime"
    except (ValueError, TypeError):
        pass

    # Category: string with low cardinality (unique <= 5% of rows or <= 20)
    n_unique = non_null.nunique()
    threshold = max(min(len(non_null) * 0.05, 20), 2)
    if n_unique <= threshold:
        return "category"

    return "string"


# ---------------------------------------------------------------------------
# Training jobs
# ---------------------------------------------------------------------------

@router.post("/train", response_model=TrainJobResponse)
async def start_training(
    req: TrainRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Start an ML training job."""
    # Pre-check: workspace namespace must exist
    await _check_workspace_namespace(session, req.workspace_id)

    job = await service.create_job(
        session, req,
        author_user_id=int(user.sub),
        author_username=user.username,
    )

    # Launch training in background
    background_tasks.add_task(_run_training, job.id, req)

    return job


async def _run_training(job_id: int, req: TrainRequest) -> None:
    """Background task: launch training as a K8s Job in the workspace namespace.

    The server does NOT run training itself. It:
    1. Creates a K8s Job in the workspace namespace
    2. Polls the Job status until completion
    3. Reads results from the Job's output (stored in MinIO/DB)

    If K8s is not available, falls back to mock results for demo.
    """
    async with async_session() as session:
        try:
            await service.update_job_status(session, job_id, "running", progress=5)

            # Try to launch as K8s Job
            launched = await _launch_k8s_training_job(session, job_id, req)
            if launched:
                # Poll K8s Job status
                await _poll_k8s_job(session, job_id, req)
            else:
                # No K8s or H2O available — use mock for demo
                await _train_mock(session, job_id, req)

        except Exception as e:
            logger.error("Training job %d failed: %s", job_id, e)
            async with async_session() as err_session:
                await service.update_job_status(
                    err_session, job_id, "failed", error_message=str(e),
                )


async def _launch_k8s_training_job(
    session: AsyncSession, job_id: int, req: TrainRequest,
) -> bool:
    """Create a K8s Job with real scikit-learn training.

    Returns True if Job was created, False if K8s is not available.
    """
    import json as json_mod
    from workspace_provisioner.models import ArgusWorkspace
    from sqlalchemy import select

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == req.workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        return False

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"

    # Get S3 settings for data access
    from app.settings.service import get_config_by_category
    s3_cfg = await get_config_by_category(session, "argus")
    s3_endpoint = s3_cfg.get("object_storage_endpoint", "")
    s3_access = s3_cfg.get("object_storage_access_key", "")
    s3_secret = s3_cfg.get("object_storage_secret_key", "")

    config_json = json_mod.dumps({
        "job_id": job_id,
        "task_type": req.task_type.value,
        "target_column": req.target_column,
        "metric": req.metric,
        "algorithm": req.algorithm.value,
        "data_source": req.data_source,
        "feature_columns": req.feature_columns,
        "exclude_columns": req.exclude_columns,
        "time_limit": req.time_limit_seconds,
        "test_split": req.test_split,
        "s3_endpoint": s3_endpoint,
        "s3_access_key": s3_access,
        "s3_secret_key": s3_secret,
    })

    # The training script that runs inside the K8s Job container
    train_script = r'''
import json, sys, time, os, warnings
warnings.filterwarnings("ignore")

print("[trainer] Installing dependencies...", flush=True)
os.system("pip install -q scikit-learn xgboost lightgbm pandas minio pyarrow openpyxl 2>/dev/null")
print("[trainer] Dependencies installed", flush=True)

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             precision_score, recall_score,
                             mean_squared_error, mean_absolute_error, r2_score)
from minio import Minio
from urllib.parse import urlparse
from io import BytesIO

config = json.loads(os.environ["TRAIN_CONFIG"])
task = config["task_type"]
target = config["target_column"]
metric_key = config["metric"]
algo = config["algorithm"]
ds = config["data_source"]
features = config.get("feature_columns")
exclude = config.get("exclude_columns") or []
test_split = config.get("test_split", 0.2)

# Load data from MinIO
print(f"[trainer] Loading data from {ds.get('bucket')}/{ds.get('path')}", flush=True)
parsed = urlparse(config["s3_endpoint"])
client = Minio(parsed.netloc, access_key=config["s3_access_key"],
               secret_key=config["s3_secret_key"], secure=parsed.scheme == "https")
response = client.get_object(ds["bucket"], ds["path"])
raw = response.read()
response.close(); response.release_conn()

fpath = ds["path"].lower()
if fpath.endswith(".parquet"):
    df = pd.read_parquet(BytesIO(raw))
elif fpath.endswith((".xlsx", ".xls")):
    df = pd.read_excel(BytesIO(raw), sheet_name=0)
elif fpath.endswith(".tsv"):
    df = pd.read_csv(BytesIO(raw), sep="\\t")
else:
    df = pd.read_csv(BytesIO(raw))
print(f"[trainer] Loaded {len(df)} rows, {len(df.columns)} columns", flush=True)

# Prepare features
drop_cols = [target] + exclude
if features:
    use_cols = [c for c in features if c != target and c not in exclude]
else:
    use_cols = [c for c in df.columns if c not in drop_cols]

X = df[use_cols].copy()
y = df[target].copy()

# Auto-encode categoricals
for col in X.select_dtypes(include=["object", "category"]).columns:
    X[col] = X[col].astype("category").cat.codes

# Fill missing
X = X.fillna(X.median(numeric_only=True))

is_cls = task == "classification"

# Encode target for classification
if is_cls:
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    y = pd.Series(le.fit_transform(y.astype(str)))

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_split, random_state=42)
print(f"[trainer] Train: {len(X_train)}, Test: {len(X_test)}", flush=True)

# Models to try
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
try:
    from xgboost import XGBClassifier, XGBRegressor
    has_xgb = True
except: has_xgb = False
try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    has_lgbm = True
except: has_lgbm = False

model_list = []
if is_cls:
    if algo in ("auto", "random_forest"):
        model_list.append(("RandomForest", RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)))
    if algo in ("auto", "xgboost") and has_xgb:
        model_list.append(("XGBoost", XGBClassifier(n_estimators=100, random_state=42, verbosity=0, n_jobs=-1)))
    if algo in ("auto", "lightgbm") and has_lgbm:
        model_list.append(("LightGBM", LGBMClassifier(n_estimators=100, random_state=42, verbose=-1, n_jobs=-1)))
    if algo in ("auto", "linear"):
        model_list.append(("LogisticRegression", LogisticRegression(max_iter=500, random_state=42)))
else:
    if algo in ("auto", "random_forest"):
        model_list.append(("RandomForest", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)))
    if algo in ("auto", "xgboost") and has_xgb:
        model_list.append(("XGBoost", XGBRegressor(n_estimators=100, random_state=42, verbosity=0, n_jobs=-1)))
    if algo in ("auto", "lightgbm") and has_lgbm:
        model_list.append(("LightGBM", LGBMRegressor(n_estimators=100, random_state=42, verbose=-1, n_jobs=-1)))
    if algo in ("auto", "linear"):
        model_list.append(("LinearRegression", LinearRegression()))

leaderboard = []
best_importance = {}
for name, model in model_list:
    try:
        print(f"[trainer] Training {name}...", flush=True)
        t0 = time.time()
        model.fit(X_train, y_train)
        train_time = round(time.time() - t0, 1)
        y_pred = model.predict(X_test)

        if is_cls:
            metrics = {
                "f1": round(f1_score(y_test, y_pred, average="weighted", zero_division=0), 4),
                "accuracy": round(accuracy_score(y_test, y_pred), 4),
                "precision": round(precision_score(y_test, y_pred, average="weighted", zero_division=0), 4),
                "recall": round(recall_score(y_test, y_pred, average="weighted", zero_division=0), 4),
            }
            try:
                if hasattr(model, "predict_proba"):
                    y_prob = model.predict_proba(X_test)
                    if y_prob.shape[1] == 2:
                        metrics["auc"] = round(roc_auc_score(y_test, y_prob[:, 1]), 4)
                    else:
                        metrics["auc"] = round(roc_auc_score(y_test, y_prob, multi_class="ovr", average="weighted"), 4)
            except: pass
        else:
            metrics = {
                "rmse": round(np.sqrt(mean_squared_error(y_test, y_pred)), 4),
                "mae": round(mean_absolute_error(y_test, y_pred), 4),
                "r2": round(r2_score(y_test, y_pred), 4),
            }

        leaderboard.append({"model_name": name, "metrics": metrics, "training_time_seconds": train_time})
        print(f"[trainer] {name}: {metrics}, time={train_time}s", flush=True)

        # Feature importance from best model
        if hasattr(model, "feature_importances_"):
            imp = dict(zip(use_cols, [round(float(v), 4) for v in model.feature_importances_]))
            if not best_importance or len(imp) > len(best_importance):
                best_importance = imp
    except Exception as ex:
        print(f"[trainer] {name} FAILED: {ex}", flush=True)

# Sort leaderboard
if metric_key == "auto":
    metric_key = "f1" if is_cls else "rmse"
reverse = metric_key not in ("rmse", "mae", "mse")
leaderboard.sort(key=lambda x: x["metrics"].get(metric_key, 0), reverse=reverse)
for i, e in enumerate(leaderboard):
    e["rank"] = i + 1

# Normalize importance
if best_importance:
    total = sum(best_importance.values()) or 1
    best_importance = {k: round(v / total, 4) for k, v in best_importance.items()}

result = {
    "status": "completed",
    "leaderboard": leaderboard,
    "feature_importance": best_importance,
    "metric_key": metric_key,
}
print(f"RESULT_JSON:{json.dumps(result)}", flush=True)
print("[trainer] Done!", flush=True)
'''

    job_manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": f"ml-train-{job_id}",
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/part-of": "argus-insight",
                "argus-insight/ml-job-id": str(job_id),
            },
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "trainer",
                        "image": "python:3.11-slim",
                        "command": ["python", "-c", train_script],
                        "env": [{
                            "name": "TRAIN_CONFIG",
                            "value": config_json,
                        }],
                        "resources": {
                            "requests": {"cpu": "1", "memory": "2Gi"},
                            "limits": {"cpu": "2", "memory": "4Gi"},
                        },
                    }],
                },
            },
        },
    }

    try:
        from app.k8s.service import _make_client
        k8s = await _make_client(session)
        try:
            await k8s.create_resource("jobs", job_manifest, namespace)
            logger.info("K8s training Job created: ml-train-%d in %s", job_id, namespace)
            return True
        finally:
            await k8s.close()
    except Exception as e:
        logger.warning("Failed to create K8s Job: %s. Falling back to mock.", e)
        return False


async def _poll_k8s_job(
    session: AsyncSession, job_id: int, req: TrainRequest,
) -> None:
    """Poll K8s Job status and update DB when completed."""
    from workspace_provisioner.models import ArgusWorkspace
    from sqlalchemy import select
    import json

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == req.workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        return

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"
    job_name = f"ml-train-{job_id}"

    from app.k8s.service import _make_client

    for attempt in range(900):  # Max 30 minutes (2s * 900)
        await asyncio.sleep(2)

        try:
            # Check if job was cancelled
            job_record = await service.get_job(session, job_id)
            if job_record and job_record.status == "cancelled":
                return

            k8s = await _make_client(session)
            try:
                job_data = await k8s.get_resource("jobs", job_name, namespace)
            finally:
                await k8s.close()

            status = job_data.get("status", {})
            succeeded = status.get("succeeded", 0)
            failed = status.get("failed", 0)
            active = status.get("active", 0)

            progress = min(5 + attempt, 90) if active > 0 else (100 if succeeded > 0 else 0)
            await service.update_job_status(session, job_id, "running", progress=progress)

            if succeeded > 0:
                # Read results from pod logs — look for RESULT_JSON: prefix
                try:
                    k8s2 = await _make_client(session)
                    try:
                        pods = await k8s2.list_resources(
                            "pods", namespace=namespace,
                            label_selector=f"job-name={job_name}",
                        )
                        pod_items = pods.get("items", [])
                        if pod_items:
                            pod_name = pod_items[0]["metadata"]["name"]
                            logs = []
                            async for line in k8s2.get_pod_logs(pod_name, namespace, tail_lines=100):
                                logs.append(line)
                            # Find RESULT_JSON: line
                            for line in logs:
                                stripped = line.strip()
                                # Remove timestamp prefix if present
                                if "RESULT_JSON:" in stripped:
                                    json_str = stripped.split("RESULT_JSON:", 1)[1]
                                    results = json.loads(json_str)
                                    leaderboard = results.get("leaderboard", [])
                                    feature_importance = results.get("feature_importance", {})
                                    metric_key = results.get("metric_key", req.metric)
                                    await service.update_job_status(
                                        session, job_id, "completed", progress=100,
                                        results={
                                            "leaderboard": leaderboard,
                                            "best_model": leaderboard[0] if leaderboard else None,
                                            "feature_importance": feature_importance,
                                            "metric_key": metric_key,
                                        },
                                    )
                                    return
                    finally:
                        await k8s2.close()
                except Exception as e:
                    logger.warning("Failed to read K8s Job logs: %s", e)

                await service.update_job_status(session, job_id, "completed", progress=100)
                return

            if failed > 0:
                # Read pod logs to get the actual error message
                error_detail = "K8s training Job failed"
                try:
                    k8s3 = await _make_client(session)
                    try:
                        pods = await k8s3.list_resources(
                            "pods", namespace=namespace,
                            label_selector=f"job-name={job_name}",
                        )
                        pod_items = pods.get("items", [])
                        if pod_items:
                            pod_name = pod_items[0]["metadata"]["name"]
                            logs: list[str] = []
                            async for line in k8s3.get_pod_logs(pod_name, namespace, tail_lines=30):
                                logs.append(line)
                            # Find error lines (Traceback, Error, Exception)
                            error_lines = []
                            capture = False
                            for line in logs:
                                stripped = line.strip()
                                if "Traceback" in stripped or "Error" in stripped or "Exception" in stripped:
                                    capture = True
                                if capture:
                                    error_lines.append(stripped)
                            if error_lines:
                                error_detail = "\n".join(error_lines[-10:])  # last 10 error lines
                            elif logs:
                                error_detail = "\n".join(logs[-5:])  # last 5 lines as fallback
                    finally:
                        await k8s3.close()
                except Exception as log_err:
                    logger.warning("Failed to read error logs: %s", log_err)

                await service.update_job_status(
                    session, job_id, "failed", error_message=error_detail,
                )
                return

        except Exception as e:
            logger.debug("Poll K8s Job attempt %d: %s", attempt, e)

    await service.update_job_status(
        session, job_id, "failed", error_message="Training job timed out",
    )


async def _train_mock(session: AsyncSession, job_id: int, req: TrainRequest) -> None:
    """Mock training for demo/testing when no AutoML service is available."""
    import random

    is_cls = req.task_type.value == "classification"
    models = ["XGBoost", "LightGBM", "RandomForest", "LogisticRegression" if is_cls else "LinearRegression"]
    leaderboard = []

    for i, model_name in enumerate(models):
        # Simulate training time
        await asyncio.sleep(2)
        progress = int((i + 1) / len(models) * 80) + 10
        await service.update_job_status(session, job_id, "running", progress=progress)

        if is_cls:
            metrics = {
                "f1": round(random.uniform(0.75, 0.95), 4),
                "accuracy": round(random.uniform(0.80, 0.95), 4),
                "auc": round(random.uniform(0.80, 0.98), 4),
                "precision": round(random.uniform(0.75, 0.95), 4),
                "recall": round(random.uniform(0.75, 0.95), 4),
            }
        else:
            metrics = {
                "rmse": round(random.uniform(0.5, 5.0), 4),
                "mae": round(random.uniform(0.3, 3.0), 4),
                "r2": round(random.uniform(0.70, 0.98), 4),
            }

        leaderboard.append({
            "rank": i + 1,
            "model_name": model_name,
            "metrics": metrics,
            "training_time_seconds": round(random.uniform(1, 30), 1),
        })

    # Sort leaderboard by primary metric
    metric_key = req.metric if req.metric != "auto" else ("f1" if is_cls else "rmse")
    reverse = metric_key not in ("rmse", "mae", "mse")
    leaderboard.sort(key=lambda x: x["metrics"].get(metric_key, 0), reverse=reverse)
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    # Feature importance (mock)
    features = req.feature_columns or ["feature_1", "feature_2", "feature_3", "feature_4", "feature_5"]
    total = sum(range(1, len(features) + 1))
    importance = {f: round((len(features) - i) / total, 4) for i, f in enumerate(features)}

    results = {
        "leaderboard": leaderboard,
        "best_model": leaderboard[0] if leaderboard else None,
        "feature_importance": importance,
        "metric_key": metric_key,
    }

    await service.update_job_status(session, job_id, "completed", progress=100, results=results)
    logger.info("ML job %d completed (mock): best=%s", job_id, leaderboard[0]["model_name"] if leaderboard else "none")


async def _train_with_h2o(
    session: AsyncSession, job_id: int, req: TrainRequest, h2o_endpoint: str,
) -> None:
    """Train using H2O AutoML REST API."""
    # H2O integration would go here
    # For now, fall back to mock
    await _train_mock(session, job_id, req)


@router.get("/jobs", response_model=TrainJobListResponse)
async def list_jobs(
    user: CurrentUser,
    workspace_id: int = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """List training jobs for a workspace with pagination."""
    jobs, total = await service.list_jobs(session, workspace_id, page, page_size)
    return TrainJobListResponse(jobs=jobs, total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=TrainJobResponse)
async def get_job(
    job_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Get training job details."""
    job = await service.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Pipelines (save/load)
# ---------------------------------------------------------------------------

@router.post("/pipelines", response_model=PipelineResponse)
async def save_pipeline(
    req: PipelineSaveRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Save a pipeline DAG."""
    return await service.save_pipeline(
        session,
        workspace_id=req.workspace_id,
        name=req.name,
        description=req.description,
        pipeline_json=req.pipeline_json,
        author_user_id=int(user.sub),
        author_username=user.username,
    )


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int,
    req: PipelineUpdateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing pipeline."""
    p = await service.update_pipeline(
        session, pipeline_id,
        name=req.name,
        description=req.description,
        pipeline_json=req.pipeline_json,
    )
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return p


@router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines(
    user: CurrentUser,
    workspace_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """List saved pipelines for a workspace."""
    items, total = await service.list_pipelines(session, workspace_id)
    return PipelineListResponse(pipelines=items, total=total)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Get a pipeline by ID."""
    p = await service.get_pipeline(session, pipeline_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return p


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete a pipeline."""
    deleted = await service.delete_pipeline(session, pipeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"ok": True}


async def _check_workspace_namespace(session: AsyncSession, workspace_id: int) -> str:
    """Validate workspace exists and K8s namespace is available.

    Called before pipeline/training execution to ensure the target
    namespace exists. Returns namespace name or raises HTTPException.
    """
    from workspace_provisioner.models import ArgusWorkspace
    from sqlalchemy import select

    logger.debug("Checking workspace namespace: workspace_id=%d", workspace_id)
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        logger.warning("Workspace id=%d not found", workspace_id)
        raise HTTPException(status_code=404, detail={
            "message": f"Workspace (id={workspace_id}) not found",
        })

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"

    try:
        from app.k8s.service import _make_client
        k8s = await _make_client(session)
        try:
            await k8s.get_resource("namespaces", namespace)
        finally:
            await k8s.close()
        logger.info("Workspace namespace verified: %s", namespace)
    except Exception:
        logger.warning("K8s namespace '%s' not found for workspace '%s'", namespace, workspace.name)
        raise HTTPException(status_code=422, detail={
            "message": f"Kubernetes namespace '{namespace}' does not exist. "
                       f"Please provision the workspace '{workspace.name}' first.",
        })

    return namespace


async def _get_s3_config(session: AsyncSession) -> tuple[str, str, str, "Minio | None"]:
    """Return (endpoint, access_key, secret_key, minio_client) from settings."""
    from app.settings.service import get_config_by_category
    cfg = await get_config_by_category(session, "argus")
    ep = cfg.get("object_storage_endpoint", "")
    ak = cfg.get("object_storage_access_key", "")
    sk = cfg.get("object_storage_secret_key", "")

    client = None
    if ep and ak:
        try:
            from urllib.parse import urlparse
            from minio import Minio
            parsed = urlparse(ep)
            client = Minio(parsed.netloc, access_key=ak, secret_key=sk,
                           secure=parsed.scheme == "https")
        except Exception:
            pass
    return ep, ak, sk, client


@router.post("/pipelines/codegen", response_model=CodegenResponse)
async def codegen_pipeline(
    req: CodegenRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Validate pipeline and generate Python code (server-side)."""
    from app.ml_studio.codegen import validate_pipeline, generate_pipeline_code

    pj = req.pipeline_json
    nodes = pj.get("nodes", [])
    edges = pj.get("edges", [])

    ep, ak, sk, minio_client = await _get_s3_config(session)

    # 1. Validate with real data
    vr = validate_pipeline(nodes, edges, minio_client=minio_client)

    # 2. Generate code (even if warnings — only block on errors)
    code = ""
    if vr.ok:
        code = generate_pipeline_code(nodes, edges,
                                      s3_endpoint=ep, s3_access_key=ak, s3_secret_key=sk)

    vd = vr.to_dict()
    return CodegenResponse(code=code, valid=vd["valid"],
                           errors=vd["errors"], warnings=vd["warnings"])


@router.post("/pipelines/execute", response_model=TrainJobResponse)
async def execute_pipeline(
    req: PipelineExecuteRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Validate, generate code, and execute pipeline as a K8s Job."""
    from app.ml_studio.codegen import validate_pipeline, generate_pipeline_code

    # Pre-check: workspace namespace must exist
    await _check_workspace_namespace(session, req.workspace_id)

    pj = req.pipeline_json
    nodes = pj.get("nodes", [])
    edges = pj.get("edges", [])

    ep, ak, sk, minio_client = await _get_s3_config(session)

    # Validate
    vr = validate_pipeline(nodes, edges, minio_client=minio_client)
    if not vr.ok:
        raise HTTPException(status_code=422, detail={
            "message": "Pipeline validation failed",
            "errors": [{"nodeId": e.node_id, "message": e.message} for e in vr.errors],
        })

    # Generate code
    code = generate_pipeline_code(nodes, edges,
                                  s3_endpoint=ep, s3_access_key=ak, s3_secret_key=sk)
    req.generated_code = code

    job = await service.create_pipeline_job(
        session,
        workspace_id=req.workspace_id,
        name=req.name,
        pipeline_id=req.pipeline_id,
        generated_code=code,
        author_user_id=int(user.sub),
        author_username=user.username,
    )
    background_tasks.add_task(_run_pipeline_job, job.id, req)
    return job


async def _run_pipeline_job(job_id: int, req: PipelineExecuteRequest) -> None:
    """Background task: launch pipeline code as a K8s Job."""
    async with async_session() as session:
        try:
            await service.update_job_status(session, job_id, "running", progress=5)
            launched = await _launch_pipeline_k8s_job(session, job_id, req)
            if launched:
                await _poll_pipeline_k8s_job(session, job_id, req)
            else:
                # Fallback: mock complete
                await asyncio.sleep(3)
                await service.update_job_status(
                    session, job_id, "completed", progress=100,
                    results={"status": "completed", "message": "Pipeline executed (mock)"},
                )
        except Exception as e:
            logger.error("Pipeline job %d failed: %s", job_id, e)
            async with async_session() as err_session:
                await service.update_job_status(
                    err_session, job_id, "failed", error_message=str(e),
                )


async def _launch_pipeline_k8s_job(
    session: AsyncSession, job_id: int, req: PipelineExecuteRequest,
) -> bool:
    """Create a K8s Job that runs the generated Python code."""
    import json as json_mod
    from workspace_provisioner.models import ArgusWorkspace
    from sqlalchemy import select

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == req.workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        return False

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"

    # Wrap user code with result reporting (skip if Evaluate node already emits RESULT_JSON)
    has_evaluate = any(
        n.get("type") == "output_evaluate"
        for n in req.pipeline_json.get("nodes", [])
    )
    if has_evaluate:
        wrapped_code = req.generated_code
    else:
        wrapped_code = req.generated_code + r'''

# Signal completion
import json as _json
print(f"RESULT_JSON:{_json.dumps({'status': 'completed', 'message': 'Pipeline executed successfully'})}", flush=True)
'''

    job_manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": f"ml-pipeline-{job_id}",
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/part-of": "argus-insight",
                "argus-insight/ml-job-id": str(job_id),
                "argus-insight/ml-source": "modeler",
            },
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "pipeline",
                        "image": "python:3.11-slim",
                        "command": ["bash", "-c",
                            "apt-get update -qq && apt-get install -y -qq libgomp1 >/dev/null 2>&1; "
                            "pip install -q pandas numpy scikit-learn xgboost lightgbm minio pyarrow openpyxl 2>/dev/null && "
                            "python -c \"$PIPELINE_CODE\""
                        ],
                        "env": [{
                            "name": "PIPELINE_CODE",
                            "value": wrapped_code,
                        }],
                        "resources": {
                            "requests": {"cpu": "1", "memory": "2Gi"},
                            "limits": {"cpu": "2", "memory": "4Gi"},
                        },
                    }],
                },
            },
        },
    }

    try:
        from app.k8s.service import _make_client
        k8s = await _make_client(session)
        try:
            await k8s.create_resource("jobs", job_manifest, namespace)
            logger.info("K8s pipeline Job created: ml-pipeline-%d in %s", job_id, namespace)
            return True
        finally:
            await k8s.close()
    except Exception as e:
        logger.warning("Failed to create K8s pipeline Job: %s", e)
        return False


async def _poll_pipeline_k8s_job(
    session: AsyncSession, job_id: int, req: PipelineExecuteRequest,
) -> None:
    """Poll K8s pipeline Job status."""
    from workspace_provisioner.models import ArgusWorkspace
    from sqlalchemy import select
    import json

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == req.workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        return

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"
    job_name = f"ml-pipeline-{job_id}"

    from app.k8s.service import _make_client

    for attempt in range(900):
        await asyncio.sleep(2)
        try:
            job_record = await service.get_job(session, job_id)
            if job_record and job_record.status == "cancelled":
                return

            k8s = await _make_client(session)
            try:
                job_data = await k8s.get_resource("jobs", job_name, namespace)
            finally:
                await k8s.close()

            status = job_data.get("status", {})
            succeeded = status.get("succeeded", 0)
            failed = status.get("failed", 0)
            active = status.get("active", 0)

            progress = min(5 + attempt, 90) if active > 0 else (100 if succeeded > 0 else 0)
            await service.update_job_status(session, job_id, "running", progress=progress)

            if succeeded > 0:
                # Read RESULT_JSON from pod logs
                results = {"status": "completed"}
                try:
                    k8s2 = await _make_client(session)
                    try:
                        pods = await k8s2.list_resources(
                            "pods", namespace=namespace,
                            label_selector=f"job-name={job_name}",
                        )
                        pod_items = pods.get("items", [])
                        if pod_items:
                            pod_name = pod_items[0]["metadata"]["name"]
                            async for line in k8s2.get_pod_logs(pod_name, namespace, tail_lines=50):
                                if "RESULT_JSON:" in line:
                                    json_str = line.strip().split("RESULT_JSON:", 1)[1]
                                    results = json.loads(json_str)
                                    break
                    finally:
                        await k8s2.close()
                except Exception as e:
                    logger.warning("Failed to read pipeline Job logs: %s", e)

                await service.update_job_status(
                    session, job_id, "completed", progress=100, results=results,
                )
                return

            if failed > 0:
                error_detail = "Pipeline execution failed"
                try:
                    k8s3 = await _make_client(session)
                    try:
                        pods = await k8s3.list_resources(
                            "pods", namespace=namespace,
                            label_selector=f"job-name={job_name}",
                        )
                        pod_items = pods.get("items", [])
                        if pod_items:
                            pod_name = pod_items[0]["metadata"]["name"]
                            logs: list[str] = []
                            async for line in k8s3.get_pod_logs(pod_name, namespace, tail_lines=30):
                                logs.append(line)
                            error_lines = [l.strip() for l in logs if "Error" in l or "Traceback" in l or "Exception" in l]
                            error_detail = "\n".join(error_lines[-10:]) if error_lines else "\n".join(logs[-5:])
                    finally:
                        await k8s3.close()
                except Exception:
                    pass

                await service.update_job_status(
                    session, job_id, "failed", error_message=error_detail,
                )
                return

        except Exception as e:
            logger.debug("Poll pipeline Job attempt %d: %s", attempt, e)

    await service.update_job_status(
        session, job_id, "failed", error_message="Pipeline job timed out",
    )


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Cancel a running training job — deletes K8s Job and updates DB."""
    from workspace_provisioner.models import ArgusWorkspace
    from sqlalchemy import select as sa_select

    job = await service.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("running", "pending"):
        raise HTTPException(status_code=400, detail="Job is not running")

    # Delete K8s Job
    ws_result = await session.execute(
        sa_select(ArgusWorkspace).where(ArgusWorkspace.id == job.workspace_id)
    )
    workspace = ws_result.scalars().first()
    if workspace:
        namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"
        job_name = f"ml-train-{job_id}"
        try:
            from app.k8s.service import _make_client
            k8s = await _make_client(session)
            try:
                await k8s.delete_resource("jobs", job_name, namespace)
                # Also delete pods
                pods = await k8s.list_resources(
                    "pods", namespace=namespace,
                    label_selector=f"job-name={job_name}",
                )
                for pod in pods.get("items", []):
                    try:
                        await k8s.delete_resource("pods", pod["metadata"]["name"], namespace)
                    except Exception:
                        pass
            finally:
                await k8s.close()
        except Exception as e:
            logger.warning("Failed to delete K8s Job %s: %s", job_name, e)

    await service.update_job_status(session, job_id, "cancelled", error_message="Cancelled by user")
    return {"ok": True}


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: int,
    workspace_id: int = Query(...),
    user: CurrentUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Fetch K8s pod logs for a job."""
    from workspace_provisioner.models import ArgusWorkspace
    from sqlalchemy import select as sa_select

    job = await service.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    ws_result = await session.execute(
        sa_select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        return {"logs": "Workspace not found"}

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"
    # Determine job name based on source
    source = job.source or "wizard"
    job_name = f"ml-pipeline-{job_id}" if source == "modeler" else f"ml-train-{job_id}"

    try:
        from app.k8s.service import _make_client
        k8s = await _make_client(session)
        try:
            pods = await k8s.list_resources(
                "pods", namespace=namespace,
                label_selector=f"job-name={job_name}",
            )
            pod_items = pods.get("items", [])
            if not pod_items:
                return {"logs": "No pods found for this job"}

            pod = pod_items[0]
            pod_name = pod["metadata"]["name"]
            phase = pod.get("status", {}).get("phase", "Unknown")

            # Check container status
            container_statuses = pod.get("status", {}).get("containerStatuses", [])
            if container_statuses:
                state = container_statuses[0].get("state", {})
                if "waiting" in state:
                    reason = state["waiting"].get("reason", "Waiting")
                    msg = state["waiting"].get("message", "")
                    return {"logs": f"⏳ Pod is {reason}...\n{msg}".strip()}
                if "terminated" in state:
                    exit_code = state["terminated"].get("exitCode", -1)
                    reason = state["terminated"].get("reason", "")
                    if exit_code != 0:
                        # Still try to get logs for failed containers
                        pass

            if phase == "Pending":
                return {"logs": "⏳ Pod is pending — waiting for resources..."}

            lines: list[str] = []
            async for line in k8s.get_pod_logs(pod_name, namespace, tail_lines=500):
                lines.append(line)
            return {"logs": "\n".join(lines) if lines else "No output yet"}
        finally:
            await k8s.close()
    except Exception as e:
        return {"logs": f"Failed to fetch logs: {e}"}
