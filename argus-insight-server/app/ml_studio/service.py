"""ML Studio service — training job management."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml_studio.models import ArgusMLJob
from app.ml_studio.schemas import (
    TrainJobResponse,
    TrainRequest,
)

logger = logging.getLogger(__name__)


def _job_to_response(job: ArgusMLJob) -> TrainJobResponse:
    return TrainJobResponse(
        id=job.id,
        workspace_id=job.workspace_id,
        name=job.name,
        status=job.status,
        task_type=job.task_type,
        target_column=job.target_column,
        metric=job.metric,
        algorithm=job.algorithm,
        progress=job.progress,
        data_source=job.data_source or {},
        config=job.config,
        results=job.results,
        error_message=job.error_message,
        author_username=job.author_username,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


async def create_job(
    session: AsyncSession,
    req: TrainRequest,
    author_user_id: int,
    author_username: str | None,
) -> TrainJobResponse:
    """Create a new ML training job record."""
    # Auto-select metric based on task type
    metric = req.metric
    if metric == "auto":
        metric = {
            "classification": "f1",
            "regression": "rmse",
            "timeseries": "rmse",
        }.get(req.task_type.value, "f1")

    job = ArgusMLJob(
        workspace_id=req.workspace_id,
        name=req.name,
        status="pending",
        task_type=req.task_type.value,
        target_column=req.target_column,
        metric=metric,
        algorithm=req.algorithm.value,
        data_source=req.data_source,
        config={
            "feature_columns": req.feature_columns,
            "exclude_columns": req.exclude_columns,
            "time_limit_seconds": req.time_limit_seconds,
            "test_split": req.test_split,
        },
        progress=0,
        author_user_id=author_user_id,
        author_username=author_username,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    logger.info("ML job created: id=%d name=%s task=%s", job.id, job.name, job.task_type)
    return _job_to_response(job)


async def get_job(session: AsyncSession, job_id: int) -> TrainJobResponse | None:
    result = await session.execute(
        select(ArgusMLJob).where(ArgusMLJob.id == job_id)
    )
    job = result.scalars().first()
    return _job_to_response(job) if job else None


async def update_job_status(
    session: AsyncSession,
    job_id: int,
    status: str,
    progress: int = 0,
    results: dict | None = None,
    error_message: str | None = None,
) -> None:
    result = await session.execute(
        select(ArgusMLJob).where(ArgusMLJob.id == job_id)
    )
    job = result.scalars().first()
    if not job:
        return
    job.status = status
    job.progress = progress
    if results:
        job.results = results
    if error_message:
        job.error_message = error_message
    if status in ("completed", "failed"):
        job.completed_at = datetime.now(timezone.utc)
    await session.commit()


async def list_jobs(
    session: AsyncSession,
    workspace_id: int,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[TrainJobResponse], int]:
    """Returns (jobs, total_count)."""
    from sqlalchemy import func

    count_q = select(func.count(ArgusMLJob.id)).where(ArgusMLJob.workspace_id == workspace_id)
    total = (await session.execute(count_q)).scalar() or 0

    result = await session.execute(
        select(ArgusMLJob)
        .where(ArgusMLJob.workspace_id == workspace_id)
        .order_by(ArgusMLJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = [_job_to_response(j) for j in result.scalars().all()]
    return jobs, total
