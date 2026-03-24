"""RAG Server - FastAPI application entry point."""

import argparse
import logging
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.collection.router import router as collection_router
from app.core.config import settings
from app.core.database import Base, close_database, engine, init_database
from app.core.logging import setup_logging
from app.core.security import SecurityHeadersMiddleware
from app.search.router import router as search_router
from app.settings.router import router as settings_router
from app.source.router import router as sync_router

logger = logging.getLogger(__name__)
_start_time: float = 0.0

BANNER = r"""
_______                                  ______ _______ _______
___    |_____________ ____  _________    ___  / ___    /___  __/
__  /| |_  ___/_  __ `/  / / /_  ___/    __  /  __  __ \__  /_
_  ___ |  /   _  /_/ // /_/ /_(__  )     _  /___  /_/ /_  __/
/_/  |_/_/    _\__, / \__,_/ /____/      /_____/\____/ /_/
              /____/
              RAG Server — Embedding & Semantic Search
"""


def _print_banner() -> None:
    logger.info(BANNER)
    logger.info("Version           : %s", settings.app_version)
    logger.info("Config YAML       : %s", settings.config_yaml_path)
    logger.info(
        "Embedding         : %s (%s)", settings.embedding_provider, settings.embedding_model
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.monotonic()
    setup_logging()
    _print_banner()
    logger.info("RAG Server %s starting", __version__)

    await init_database()

    import app.models.collection  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    # Initialize embedding provider
    from app.embedding.registry import initialize_from_settings

    try:
        provider = await initialize_from_settings()
        logger.info(
            "Embedding provider ready: %s (dim=%d)",
            provider.model_name(),
            provider.dimension(),
        )
    except Exception as e:
        logger.warning("Embedding provider init failed: %s", e)
        logger.warning("Configure via PUT /api/v1/settings/embedding")

    yield

    from app.embedding.registry import shutdown_provider

    await shutdown_provider()
    await close_database()
    logger.info("RAG Server shutting down")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)


class DynamicCORSMiddleware:
    def __init__(self, app):
        self.app = app
        self._inner = None
        self._snapshot = None

    def _get_inner(self):
        current = tuple(settings.cors_origins)
        if current != self._snapshot:
            self._inner = CORSMiddleware(
                app=self.app,
                allow_origins=list(current),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            self._snapshot = current
        return self._inner

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        await self._get_inner()(scope, receive, send)


app.add_middleware(DynamicCORSMiddleware)

app.include_router(collection_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")


@app.get("/health")
async def health():
    uptime = int(time.monotonic() - _start_time)
    from app.embedding.registry import get_provider

    provider = await get_provider()
    return {
        "status": "ok",
        "service": "argus-rag-server",
        "uptime": uptime,
        "version": __version__,
        "embedding": {
            "provider": provider.provider_name() if provider else None,
            "model": provider.model_name() if provider else None,
            "ready": provider is not None,
        },
    }


@app.get("/api/v1/stats")
async def dashboard_stats():
    """Dashboard statistics across all collections."""
    from sqlalchemy import func, select

    from app.core.database import async_session
    from app.models.collection import Collection, Document, DocumentChunk, SyncJob

    async with async_session() as session:
        total_collections = (
            await session.execute(
                select(func.count()).select_from(Collection).where(Collection.status != "deleted")
            )
        ).scalar() or 0

        total_documents = (
            await session.execute(select(func.count()).select_from(Document))
        ).scalar() or 0

        total_chunks = (
            await session.execute(select(func.count()).select_from(DocumentChunk))
        ).scalar() or 0

        embedded_chunks = (
            await session.execute(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.embedding.isnot(None))
            )
        ).scalar() or 0

        recent_jobs = (
            (await session.execute(select(SyncJob).order_by(SyncJob.started_at.desc()).limit(5)))
            .scalars()
            .all()
        )

        provider = (
            await (
                await __import__("app.embedding.registry", fromlist=["get_provider"])
            ).get_provider()
            if False
            else None
        )
        from app.embedding.registry import get_provider

        provider = await get_provider()

        return {
            "total_collections": total_collections,
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "coverage_pct": (
                round(embedded_chunks / total_chunks * 100, 1) if total_chunks > 0 else 0
            ),
            "embedding_provider": provider.provider_name() if provider else None,
            "embedding_model": provider.model_name() if provider else None,
            "recent_jobs": [
                {
                    "id": j.id,
                    "collection_id": j.collection_id,
                    "job_type": j.job_type,
                    "status": j.status,
                    "total_items": j.total_items,
                    "processed_items": j.processed_items,
                    "started_at": j.started_at.isoformat() if j.started_at else None,
                }
                for j in recent_jobs
            ],
        }


def run() -> None:
    parser = argparse.ArgumentParser(
        prog="argus-rag-server",
        description="Argus RAG Server — Embedding, indexing, and semantic search.",
    )
    parser.add_argument("--config-yaml", metavar="PATH")
    parser.add_argument("--config-properties", metavar="PATH")
    args = parser.parse_args()

    if args.config_yaml or args.config_properties:
        from app.core.config import init_settings

        init_settings(yaml_path=args.config_yaml, properties_path=args.config_properties)
    else:
        if (
            not settings.config_yaml_path.is_file()
            and not settings.config_properties_path.is_file()
        ):
            parser.print_help()
            print(f"\nError: No config at {settings.config_yaml_path}")
            sys.exit(1)

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    run()
