"""AI metadata generation service.

Orchestrates LLM-powered generation of dataset descriptions, column descriptions,
tag suggestions, and PII detection. Handles context assembly, LLM calls,
JSON parsing, logging, and optional application to catalog entities.
"""

import asyncio
import json
import logging
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AIGenerationLog
from app.ai.prompts import (
    SYSTEM_PROMPT,
    build_column_descriptions_prompt,
    build_dataset_description_prompt,
    build_pii_detection_prompt,
    build_tag_suggestion_prompt,
)
from app.ai.registry import get_provider
from app.catalog.models import Dataset, DatasetLineage, DatasetSchema, DatasetTag, Platform, Tag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enhanced context loaders (glossary, lineage, few-shot)
# ---------------------------------------------------------------------------

async def _load_glossary_context(session: AsyncSession) -> list[dict]:
    """Load StandardWord entries as abbreviation→name mappings for prompt context.

    Returns: [{"abbr": "EQP", "name": "장비", "english": "Equipment"}, ...]
    """
    from app.standard.models import StandardDictionary, StandardWord

    # Find active dictionaries
    dict_result = await session.execute(
        select(StandardDictionary.id)
        .where(StandardDictionary.status == "ACTIVE")
        .order_by(StandardDictionary.id)
    )
    dict_ids = [r[0] for r in dict_result.all()]
    if not dict_ids:
        return []

    result = await session.execute(
        select(
            StandardWord.word_abbr,
            StandardWord.word_name,
            StandardWord.word_english,
            StandardWord.word_type,
        )
        .where(
            StandardWord.dictionary_id.in_(dict_ids),
            StandardWord.status == "ACTIVE",
        )
        .order_by(StandardWord.word_abbr)
    )

    return [
        {
            "abbr": r.word_abbr,
            "name": r.word_name,
            "english": r.word_english,
            "type": r.word_type,
        }
        for r in result.all()
    ]


async def _load_lineage_context(
    session: AsyncSession, dataset_id: int,
) -> dict[str, list[str]]:
    """Load upstream and downstream dataset names for lineage context.

    Returns: {"upstream": ["db.table1", ...], "downstream": ["db.table2", ...]}
    """
    # Upstream: datasets that feed into this one
    upstream_result = await session.execute(
        select(Dataset.name)
        .join(DatasetLineage, DatasetLineage.source_dataset_id == Dataset.id)
        .where(DatasetLineage.target_dataset_id == dataset_id)
        .limit(10)
    )
    upstream = [r[0] for r in upstream_result.all()]

    # Downstream: datasets that consume from this one
    downstream_result = await session.execute(
        select(Dataset.name)
        .join(DatasetLineage, DatasetLineage.target_dataset_id == Dataset.id)
        .where(DatasetLineage.source_dataset_id == dataset_id)
        .limit(10)
    )
    downstream = [r[0] for r in downstream_result.all()]

    return {"upstream": upstream, "downstream": downstream}


async def _load_fewshot_examples(
    session: AsyncSession,
    platform_type: str,
    generation_type: str,
    exclude_dataset_id: int,
    limit: int = 3,
) -> list[dict]:
    """Load applied AI generation results as few-shot examples.

    Selects examples from same platform type where the result was applied (approved).
    Returns: [{"dataset_name": "...", "generated_text": "..."}, ...]
    """
    result = await session.execute(
        select(
            Dataset.name.label("dataset_name"),
            AIGenerationLog.generated_text,
        )
        .join(Dataset, AIGenerationLog.dataset_id == Dataset.id)
        .join(Platform, Dataset.platform_id == Platform.id)
        .where(
            AIGenerationLog.applied == True,  # noqa: E712
            AIGenerationLog.generation_type == generation_type,
            AIGenerationLog.entity_type == "dataset",
            Platform.type == platform_type,
            AIGenerationLog.dataset_id != exclude_dataset_id,
        )
        .order_by(AIGenerationLog.created_at.desc())
        .limit(limit)
    )

    examples = []
    for r in result.all():
        examples.append({
            "dataset_name": r.dataset_name,
            "generated_text": r.generated_text,
        })

    # If no applied AI results, fallback to manually described datasets
    if not examples and generation_type == "description":
        manual_result = await session.execute(
            select(Dataset.name, Dataset.description)
            .join(Platform, Dataset.platform_id == Platform.id)
            .where(
                Platform.type == platform_type,
                Dataset.description.isnot(None),
                Dataset.description != "",
                Dataset.status != "removed",
                Dataset.id != exclude_dataset_id,
            )
            .order_by(func.length(Dataset.description).desc())
            .limit(limit)
        )
        for r in manual_result.all():
            examples.append({
                "dataset_name": r.name,
                "generated_text": r.description,
            })

    return examples


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> dict | None:
    """Extract JSON from LLM response, tolerating markdown fences."""
    # Try direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def _call_llm(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> dict:
    """Call LLM and parse JSON response. Retries once on parse failure.

    Returns: {"data": parsed_dict, "prompt_tokens": int, "completion_tokens": int}
    Raises ValueError if provider unavailable or JSON parse fails after retry.
    """
    provider = await get_provider()
    if provider is None:
        raise ValueError("LLM provider not initialized. Enable LLM in settings.")

    result = await provider.generate(prompt, system_prompt, temperature, max_tokens)
    parsed = _parse_json_response(result["text"])

    if parsed is None:
        # Retry with correction prompt
        retry_prompt = (
            "Your previous response was not valid JSON. "
            "Please fix and respond with valid JSON only:\n\n" + result["text"]
        )
        result2 = await provider.generate(retry_prompt, system_prompt, temperature, max_tokens)
        parsed = _parse_json_response(result2["text"])
        if parsed is None:
            raise ValueError(f"LLM returned invalid JSON after retry: {result2['text'][:200]}")
        # Combine token counts
        result["prompt_tokens"] = (result.get("prompt_tokens") or 0) + (
            result2.get("prompt_tokens") or 0
        )
        result["completion_tokens"] = (result.get("completion_tokens") or 0) + (
            result2.get("completion_tokens") or 0
        )

    return {
        "data": parsed,
        "prompt_tokens": result.get("prompt_tokens"),
        "completion_tokens": result.get("completion_tokens"),
    }


async def _get_llm_config(session: AsyncSession) -> dict[str, str]:
    """Load LLM config from DB."""
    from app.settings.service import get_config_by_category
    return await get_config_by_category(session, "llm")


def _load_sample_data(
    platform_name: str, dataset_name: str, max_rows: int = 5,
) -> tuple[list[dict] | None, dict[str, list] | None]:
    """Load sample data from Parquet file on disk.

    Returns (sample_rows, sample_values) or (None, None) if not available.
    """
    from pathlib import Path

    from app.core.config import settings

    parquet_path = (
        Path(settings.data_dir) / "samples" / platform_name / dataset_name / "sample.parquet"
    )
    if not parquet_path.exists():
        return None, None

    try:
        import pyarrow.parquet as pq

        table = pq.read_table(str(parquet_path))
        df = table.to_pandas().head(max_rows)

        rows = []
        for _, row in df.iterrows():
            rows.append({col: str(val) for col, val in row.items()})

        values: dict[str, list] = {}
        for col in df.columns:
            values[col] = [str(v) for v in df[col].tolist()]

        return rows, values
    except Exception:
        return None, None


async def _get_dataset_context(session: AsyncSession, dataset_id: int) -> dict | None:
    """Load dataset + platform + schema + sample data for prompt building."""
    result = await session.execute(
        select(
            Dataset.id, Dataset.name, Dataset.description, Dataset.qualified_name,
            Dataset.platform_properties,
            Platform.type.label("platform_type"), Platform.name.label("platform_name"),
            Platform.platform_id.label("platform_id_str"),
        )
        .join(Platform, Dataset.platform_id == Platform.id)
        .where(Dataset.id == dataset_id)
    )
    row = result.first()
    if not row:
        return None

    # Parse name into database.table
    parts = row.name.split(".", 1) if row.name else ["", ""]
    database = parts[0] if len(parts) > 1 else ""
    table_name = parts[1] if len(parts) > 1 else row.name

    # Load schema fields
    schema_result = await session.execute(
        select(DatasetSchema)
        .where(DatasetSchema.dataset_id == dataset_id)
        .order_by(DatasetSchema.ordinal)
    )
    fields = schema_result.scalars().all()
    columns = [
        {
            "id": f.id,
            "field_path": f.field_path,
            "field_type": f.field_type,
            "native_type": f.native_type,
            "description": f.description,
            "nullable": f.nullable,
            "is_primary_key": f.is_primary_key,
            "is_unique": f.is_unique,
            "is_indexed": f.is_indexed,
            "ordinal": f.ordinal,
        }
        for f in fields
    ]

    # Parse platform_properties for DDL and row count
    props = {}
    if row.platform_properties:
        try:
            props = json.loads(row.platform_properties)
        except (json.JSONDecodeError, TypeError):
            pass

    # Load sample data from Parquet file
    sample_rows, sample_values = _load_sample_data(
        row.platform_id_str, row.name,
    )

    return {
        "dataset_id": row.id,
        "name": row.name,
        "table_name": table_name,
        "database": database,
        "description": row.description,
        "platform_type": row.platform_type,
        "platform_name": row.platform_name,
        "columns": columns,
        "ddl": props.get("ddl"),
        "row_count": props.get("estimated_rows"),
        "sample_rows": sample_rows,
        "sample_values": sample_values,
    }


def _log_entry(
    entity_type: str,
    entity_id: int,
    dataset_id: int,
    generation_type: str,
    generated_text: str,
    applied: bool,
    provider_name: str,
    model_name: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    field_name: str | None = None,
) -> AIGenerationLog:
    """Create an AIGenerationLog entry."""
    return AIGenerationLog(
        entity_type=entity_type,
        entity_id=entity_id,
        dataset_id=dataset_id,
        field_name=field_name,
        generation_type=generation_type,
        generated_text=generated_text,
        applied=applied,
        provider=provider_name,
        model=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------

async def generate_dataset_description(
    session: AsyncSession,
    dataset_id: int,
    apply: bool = False,
    force: bool = False,
    language: str | None = None,
) -> dict:
    """Generate a description for a dataset using LLM.

    Returns: {"dataset_id", "description", "confidence", "applied", "log_id"}
    """
    ctx = await _get_dataset_context(session, dataset_id)
    if not ctx:
        raise ValueError(f"Dataset {dataset_id} not found")

    # Skip if already has description (unless force)
    if ctx["description"] and not force:
        return {
            "dataset_id": dataset_id,
            "description": ctx["description"],
            "confidence": 1.0,
            "applied": False,
            "skipped": True,
            "reason": "Description already exists",
        }

    cfg = await _get_llm_config(session)
    lang = language or cfg.get("llm_language", "ko")

    # Load enhanced context
    glossary = await _load_glossary_context(session)
    lineage = await _load_lineage_context(session, dataset_id)
    fewshot = await _load_fewshot_examples(
        session, ctx["platform_type"], "description", dataset_id,
    )

    prompt = build_dataset_description_prompt(
        table_name=ctx["table_name"],
        database=ctx["database"],
        platform_type=ctx["platform_type"],
        columns=ctx["columns"],
        ddl=ctx["ddl"],
        sample_rows=ctx.get("sample_rows"),
        row_count=ctx["row_count"],
        language=lang,
        glossary=glossary,
        lineage=lineage,
        fewshot_examples=fewshot,
    )

    llm_result = await _call_llm(prompt, max_tokens=int(cfg.get("llm_max_tokens", "1024")))
    data = llm_result["data"]
    description = data.get("description", "")
    confidence = data.get("confidence", 0.5)

    provider = await get_provider()

    # Log the generation
    log = _log_entry(
        entity_type="dataset",
        entity_id=dataset_id,
        dataset_id=dataset_id,
        generation_type="description",
        generated_text=description,
        applied=apply,
        provider_name=provider.provider_name() if provider else "unknown",
        model_name=provider.model_name() if provider else "unknown",
        prompt_tokens=llm_result.get("prompt_tokens"),
        completion_tokens=llm_result.get("completion_tokens"),
    )
    session.add(log)

    # Apply if requested
    if apply and description:
        ds_result = await session.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        ds = ds_result.scalars().first()
        if ds:
            ds.description = description

    await session.commit()
    await session.refresh(log)

    # Trigger embedding refresh if description was applied
    if apply and description:
        try:
            from app.embedding.service import embed_dataset_background
            await embed_dataset_background(dataset_id)
        except Exception as e:
            logger.warning("Embedding refresh failed after AI description: %s", e)

    return {
        "dataset_id": dataset_id,
        "description": description,
        "confidence": confidence,
        "applied": apply,
        "log_id": log.id,
    }


async def generate_column_descriptions(
    session: AsyncSession,
    dataset_id: int,
    apply: bool = False,
    force: bool = False,
    language: str | None = None,
) -> dict:
    """Generate descriptions for all columns of a dataset.

    Returns: {"dataset_id", "columns": [...], "applied"}
    """
    ctx = await _get_dataset_context(session, dataset_id)
    if not ctx:
        raise ValueError(f"Dataset {dataset_id} not found")

    # Filter columns that need descriptions
    columns = ctx["columns"]
    if not force:
        target_columns = [c for c in columns if not c.get("description")]
        if not target_columns:
            return {
                "dataset_id": dataset_id,
                "columns": [],
                "applied": False,
                "skipped": True,
                "reason": "All columns already have descriptions",
            }
    else:
        target_columns = columns

    cfg = await _get_llm_config(session)
    lang = language or cfg.get("llm_language", "ko")

    # Load enhanced context
    glossary = await _load_glossary_context(session)
    lineage = await _load_lineage_context(session, dataset_id)

    prompt = build_column_descriptions_prompt(
        table_name=ctx["table_name"],
        database=ctx["database"],
        table_description=ctx["description"],
        columns=target_columns,
        sample_values=ctx.get("sample_values"),
        language=lang,
        glossary=glossary,
        lineage=lineage,
    )

    llm_result = await _call_llm(
        prompt, max_tokens=min(int(cfg.get("llm_max_tokens", "1024")), 4096)
    )
    data = llm_result["data"]
    col_results = data.get("columns", [])

    provider = await get_provider()
    results = []

    # Map results back to schema fields
    col_name_map = {c["field_path"].lower(): c for c in target_columns}

    for cr in col_results:
        name = cr.get("name", "")
        desc = cr.get("description", "")
        conf = cr.get("confidence", 0.5)

        col_info = col_name_map.get(name.lower())
        if not col_info or not desc:
            continue

        # Log
        log = _log_entry(
            entity_type="column",
            entity_id=col_info["id"],
            dataset_id=dataset_id,
            generation_type="description",
            generated_text=desc,
            applied=apply,
            provider_name=provider.provider_name() if provider else "unknown",
            model_name=provider.model_name() if provider else "unknown",
            prompt_tokens=llm_result.get("prompt_tokens") if not results else None,
            completion_tokens=llm_result.get("completion_tokens") if not results else None,
            field_name=name,
        )
        session.add(log)

        # Apply
        if apply:
            schema_result = await session.execute(
                select(DatasetSchema).where(DatasetSchema.id == col_info["id"])
            )
            schema = schema_result.scalars().first()
            if schema:
                schema.description = desc

        results.append({
            "field_path": name,
            "description": desc,
            "confidence": conf,
            "had_existing": bool(col_info.get("description")),
        })

    await session.commit()

    return {
        "dataset_id": dataset_id,
        "columns": results,
        "total_generated": len(results),
        "applied": apply,
    }


async def suggest_tags(
    session: AsyncSession,
    dataset_id: int,
    apply: bool = False,
    language: str | None = None,
) -> dict:
    """Suggest tags for a dataset.

    Returns: {"dataset_id", "tags": [...], "new_tags": [...], "applied"}
    """
    ctx = await _get_dataset_context(session, dataset_id)
    if not ctx:
        raise ValueError(f"Dataset {dataset_id} not found")

    # Load existing catalog tags
    tag_result = await session.execute(select(Tag.name).order_by(Tag.name))
    existing_tags = [t[0] for t in tag_result.all()]

    cfg = await _get_llm_config(session)
    lang = language or cfg.get("llm_language", "ko")

    # Load enhanced context
    glossary = await _load_glossary_context(session)
    lineage = await _load_lineage_context(session, dataset_id)

    prompt = build_tag_suggestion_prompt(
        table_name=ctx["table_name"],
        database=ctx["database"],
        description=ctx["description"],
        columns=ctx["columns"],
        existing_tags=existing_tags,
        language=lang,
        glossary=glossary,
        lineage=lineage,
    )

    llm_result = await _call_llm(prompt, max_tokens=int(cfg.get("llm_max_tokens", "1024")))
    data = llm_result["data"]
    suggested_tags = data.get("tags", [])
    new_tags = data.get("new_tags", [])

    provider = await get_provider()

    # Log
    log = _log_entry(
        entity_type="dataset",
        entity_id=dataset_id,
        dataset_id=dataset_id,
        generation_type="tag_suggestion",
        generated_text=json.dumps({"tags": suggested_tags, "new_tags": new_tags},
                                  ensure_ascii=False),
        applied=apply,
        provider_name=provider.provider_name() if provider else "unknown",
        model_name=provider.model_name() if provider else "unknown",
        prompt_tokens=llm_result.get("prompt_tokens"),
        completion_tokens=llm_result.get("completion_tokens"),
    )
    session.add(log)

    applied_tags = []
    created_tags = []

    if apply:
        # Assign existing tags
        for tag_name in suggested_tags:
            tag_row = await session.execute(
                select(Tag).where(func.lower(Tag.name) == tag_name.lower())
            )
            tag = tag_row.scalars().first()
            if tag:
                # Check if already assigned
                existing = await session.execute(
                    select(DatasetTag).where(
                        DatasetTag.dataset_id == dataset_id,
                        DatasetTag.tag_id == tag.id,
                    )
                )
                if not existing.scalars().first():
                    session.add(DatasetTag(dataset_id=dataset_id, tag_id=tag.id))
                    applied_tags.append(tag_name)

        # Create and assign new tags
        for nt in new_tags:
            name = nt.get("name", "")
            desc = nt.get("description", "")
            if not name:
                continue
            # Check if tag already exists
            existing_tag = await session.execute(
                select(Tag).where(func.lower(Tag.name) == name.lower())
            )
            tag = existing_tag.scalars().first()
            if not tag:
                tag = Tag(name=name, description=desc)
                session.add(tag)
                await session.flush()
                created_tags.append(name)
            # Assign
            existing_dt = await session.execute(
                select(DatasetTag).where(
                    DatasetTag.dataset_id == dataset_id,
                    DatasetTag.tag_id == tag.id,
                )
            )
            if not existing_dt.scalars().first():
                session.add(DatasetTag(dataset_id=dataset_id, tag_id=tag.id))
                if name not in applied_tags:
                    applied_tags.append(name)

    await session.commit()
    await session.refresh(log)

    return {
        "dataset_id": dataset_id,
        "suggested_tags": suggested_tags,
        "new_tags": new_tags,
        "applied_tags": applied_tags,
        "created_tags": created_tags,
        "applied": apply,
        "log_id": log.id,
    }


async def detect_pii(
    session: AsyncSession,
    dataset_id: int,
    apply: bool = False,
) -> dict:
    """Detect PII columns in a dataset.

    Returns: {"dataset_id", "pii_columns": [...], "applied"}
    """
    ctx = await _get_dataset_context(session, dataset_id)
    if not ctx:
        raise ValueError(f"Dataset {dataset_id} not found")

    cfg = await _get_llm_config(session)

    # Load enhanced context
    glossary = await _load_glossary_context(session)

    prompt = build_pii_detection_prompt(
        table_name=ctx["table_name"],
        database=ctx["database"],
        columns=ctx["columns"],
        sample_values=ctx.get("sample_values"),
        glossary=glossary,
    )

    llm_result = await _call_llm(prompt, max_tokens=int(cfg.get("llm_max_tokens", "1024")))
    data = llm_result["data"]
    pii_columns = data.get("pii_columns", [])

    provider = await get_provider()

    # Log
    log = _log_entry(
        entity_type="dataset",
        entity_id=dataset_id,
        dataset_id=dataset_id,
        generation_type="pii_detection",
        generated_text=json.dumps(pii_columns, ensure_ascii=False),
        applied=apply,
        provider_name=provider.provider_name() if provider else "unknown",
        model_name=provider.model_name() if provider else "unknown",
        prompt_tokens=llm_result.get("prompt_tokens"),
        completion_tokens=llm_result.get("completion_tokens"),
    )
    session.add(log)

    if apply:
        col_name_map = {c["field_path"].lower(): c for c in ctx["columns"]}
        for pii in pii_columns:
            col_name = pii.get("name", "").lower()
            col_info = col_name_map.get(col_name)
            if col_info:
                schema_result = await session.execute(
                    select(DatasetSchema).where(DatasetSchema.id == col_info["id"])
                )
                schema = schema_result.scalars().first()
                if schema:
                    schema.pii_type = pii.get("pii_type")

    await session.commit()
    await session.refresh(log)

    return {
        "dataset_id": dataset_id,
        "pii_columns": pii_columns,
        "applied": apply,
        "log_id": log.id,
    }


async def generate_all_for_dataset(
    session: AsyncSession,
    dataset_id: int,
    apply: bool = False,
    force: bool = False,
    language: str | None = None,
) -> dict:
    """Run all generation tasks for a single dataset.

    Returns combined results from all tasks.
    """
    desc_result = await generate_dataset_description(
        session, dataset_id, apply=apply, force=force, language=language
    )
    col_result = await generate_column_descriptions(
        session, dataset_id, apply=apply, force=force, language=language
    )
    tag_result = await suggest_tags(
        session, dataset_id, apply=apply, language=language
    )
    pii_result = await detect_pii(
        session, dataset_id, apply=apply
    )

    return {
        "dataset_id": dataset_id,
        "description": desc_result,
        "columns": col_result,
        "tags": tag_result,
        "pii": pii_result,
    }


async def bulk_generate(
    session: AsyncSession,
    generation_types: list[str] | None = None,
    apply: bool = False,
    language: str | None = None,
    platform_id: int | None = None,
    empty_only: bool = True,
) -> dict:
    """Bulk generate metadata for multiple datasets.

    Args:
        generation_types: List of types to generate. Default: ["description"]
        apply: Whether to apply results directly.
        language: Target language override.
        platform_id: Filter by platform.
        empty_only: Only process datasets with empty descriptions (default True).

    Returns: {"total", "processed", "errors", "results": [...]}
    """
    types = generation_types or ["description"]

    query = select(Dataset.id).where(Dataset.status != "removed")
    if platform_id:
        query = query.where(Dataset.platform_id == platform_id)
    if empty_only:
        query = query.where((Dataset.description.is_(None)) | (Dataset.description == ""))
    query = query.order_by(Dataset.id)

    result = await session.execute(query)
    dataset_ids = [r[0] for r in result.all()]

    total = len(dataset_ids)
    processed = 0
    errors = 0
    results = []

    for ds_id in dataset_ids:
        try:
            ds_result = {}
            if "description" in types:
                ds_result["description"] = await generate_dataset_description(
                    session, ds_id, apply=apply, language=language
                )
            if "columns" in types:
                ds_result["columns"] = await generate_column_descriptions(
                    session, ds_id, apply=apply, language=language
                )
            if "tags" in types:
                ds_result["tags"] = await suggest_tags(
                    session, ds_id, apply=apply, language=language
                )
            if "pii" in types:
                ds_result["pii"] = await detect_pii(
                    session, ds_id, apply=apply
                )
            results.append({"dataset_id": ds_id, **ds_result})
            processed += 1
        except Exception as e:
            errors += 1
            logger.warning("Bulk generation failed for dataset %d: %s", ds_id, e)
            results.append({"dataset_id": ds_id, "error": str(e)})

    return {
        "total": total,
        "processed": processed,
        "errors": errors,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Suggestion management
# ---------------------------------------------------------------------------

async def get_suggestions(session: AsyncSession, dataset_id: int) -> list[dict]:
    """Get all unapplied AI suggestions for a dataset."""
    result = await session.execute(
        select(AIGenerationLog)
        .where(
            AIGenerationLog.dataset_id == dataset_id,
            AIGenerationLog.applied == False,  # noqa: E712
        )
        .order_by(AIGenerationLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "field_name": log.field_name,
            "generation_type": log.generation_type,
            "generated_text": log.generated_text,
            "provider": log.provider,
            "model": log.model,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


async def apply_suggestion(session: AsyncSession, suggestion_id: int) -> dict:
    """Apply a previously generated suggestion."""
    result = await session.execute(
        select(AIGenerationLog).where(AIGenerationLog.id == suggestion_id)
    )
    log = result.scalars().first()
    if not log:
        raise ValueError(f"Suggestion {suggestion_id} not found")

    if log.applied:
        return {"id": log.id, "already_applied": True}

    if log.entity_type == "dataset" and log.generation_type == "description":
        ds_result = await session.execute(
            select(Dataset).where(Dataset.id == log.entity_id)
        )
        ds = ds_result.scalars().first()
        if ds:
            ds.description = log.generated_text

    elif log.entity_type == "column" and log.generation_type == "description":
        schema_result = await session.execute(
            select(DatasetSchema).where(DatasetSchema.id == log.entity_id)
        )
        schema = schema_result.scalars().first()
        if schema:
            schema.description = log.generated_text

    elif log.generation_type == "pii_detection":
        pii_data = json.loads(log.generated_text)
        ctx = await _get_dataset_context(session, log.dataset_id)
        if ctx:
            col_name_map = {c["field_path"].lower(): c for c in ctx["columns"]}
            for pii in (pii_data if isinstance(pii_data, list) else []):
                col_info = col_name_map.get(pii.get("name", "").lower())
                if col_info:
                    schema_result = await session.execute(
                        select(DatasetSchema).where(DatasetSchema.id == col_info["id"])
                    )
                    schema = schema_result.scalars().first()
                    if schema:
                        schema.pii_type = pii.get("pii_type")

    log.applied = True
    await session.commit()

    # Trigger embedding refresh
    try:
        from app.embedding.service import embed_dataset_background
        await embed_dataset_background(log.dataset_id)
    except Exception as e:
        logger.warning("Embedding refresh failed: %s", e)

    return {"id": log.id, "applied": True}


async def reject_suggestion(session: AsyncSession, suggestion_id: int) -> dict:
    """Mark a suggestion as rejected (delete it)."""
    result = await session.execute(
        select(AIGenerationLog).where(AIGenerationLog.id == suggestion_id)
    )
    log = result.scalars().first()
    if not log:
        raise ValueError(f"Suggestion {suggestion_id} not found")

    await session.delete(log)
    await session.commit()
    return {"id": suggestion_id, "rejected": True}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

async def get_ai_stats(session: AsyncSession) -> dict:
    """Return AI generation statistics."""
    total_generations = (await session.execute(
        select(func.count()).select_from(AIGenerationLog)
    )).scalar() or 0

    applied_count = (await session.execute(
        select(func.count()).select_from(AIGenerationLog)
        .where(AIGenerationLog.applied == True)  # noqa: E712
    )).scalar() or 0

    total_prompt_tokens = (await session.execute(
        select(func.coalesce(func.sum(AIGenerationLog.prompt_tokens), 0))
    )).scalar() or 0

    total_completion_tokens = (await session.execute(
        select(func.coalesce(func.sum(AIGenerationLog.completion_tokens), 0))
    )).scalar() or 0

    # Description coverage
    total_datasets = (await session.execute(
        select(func.count()).select_from(Dataset).where(Dataset.status != "removed")
    )).scalar() or 0

    described_datasets = (await session.execute(
        select(func.count()).select_from(Dataset).where(
            Dataset.status != "removed",
            Dataset.description.isnot(None),
            Dataset.description != "",
        )
    )).scalar() or 0

    by_type = (await session.execute(
        select(AIGenerationLog.generation_type, func.count())
        .group_by(AIGenerationLog.generation_type)
    )).all()

    provider = await get_provider()

    return {
        "total_generations": total_generations,
        "applied_count": applied_count,
        "pending_count": total_generations - applied_count,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "description_coverage": {
            "total_datasets": total_datasets,
            "described_datasets": described_datasets,
            "coverage_pct": round(
                described_datasets / total_datasets * 100, 1
            ) if total_datasets > 0 else 0,
        },
        "by_type": {t: c for t, c in by_type},
        "provider": provider.provider_name() if provider else None,
        "model": provider.model_name() if provider else None,
    }


# ---------------------------------------------------------------------------
# Background helpers (for sync integration)
# ---------------------------------------------------------------------------

async def generate_descriptions_post_sync(dataset_ids: list[int]) -> None:
    """Background task: generate descriptions for datasets after sync.

    Uses its own DB session. Failures are logged but do not propagate.
    """
    if not dataset_ids:
        return

    from app.core.database import async_session

    async with async_session() as session:
        cfg = await _get_llm_config(session)
        enabled = cfg.get("llm_enabled", "false").lower() in ("true", "1", "yes")
        auto_sync = cfg.get("llm_auto_generate_on_sync", "false").lower() in ("true", "1", "yes")

        if not enabled or not auto_sync:
            return

        logger.info("Post-sync AI generation for %d dataset(s)", len(dataset_ids))
        for ds_id in dataset_ids:
            try:
                await generate_dataset_description(session, ds_id, apply=True)
            except Exception as e:
                logger.warning("Post-sync AI generation failed for dataset %d: %s", ds_id, e)
