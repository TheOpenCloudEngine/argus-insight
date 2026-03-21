"""Lineage persistence — saves parsed lineage results to the database."""

from __future__ import annotations

import logging

from sync.core.database import get_session
from sync.platforms.hive.lineage_parser import HiveLineageParser, QueryLineageResult
from sync.platforms.hive.models import ColumnLineage, DatasetLineage, QueryLineage

logger = logging.getLogger(__name__)

_parser = HiveLineageParser()


def process_query_lineage(
    query_hist_id: int,
    query_id: str,
    sql: str,
    hook_inputs: list[str] | None = None,
    hook_outputs: list[str] | None = None,
) -> list[QueryLineage]:
    """Parse SQL and save lineage records.

    Uses hook-provided inputs/outputs as the authoritative table-level source,
    falling back to SQLGlot parsing. Column-level lineage always comes from
    SQLGlot parsing.

    Args:
        query_hist_id: FK to argus_collector_hive_query_history.id.
        query_id: Hive query ID (for aggregated lineage tracking).
        sql: The raw Hive SQL text.
        hook_inputs: Table names from HookContext.getInputs() (e.g. ["db.table"]).
        hook_outputs: Table names from HookContext.getOutputs() (e.g. ["db.table"]).

    Returns:
        List of persisted QueryLineage records.
    """
    # Parse with SQLGlot for column-level details
    parsed = _parser.parse(sql)

    # Determine source/target tables — prefer hook data over parsed
    if hook_inputs and hook_outputs:
        source_tables = hook_inputs
        target_tables = hook_outputs
    elif parsed:
        source_tables = parsed.source_tables
        target_tables = parsed.target_tables
    else:
        logger.debug("No lineage info available for query %s", query_id)
        return []

    if not source_tables or not target_tables:
        logger.debug("No source→target mapping for query %s", query_id)
        return []

    session = get_session()
    try:
        records = _save_query_lineage(
            session, query_hist_id, source_tables, target_tables,
        )

        # Save column-level lineage from parsed result
        if parsed and records:
            _save_column_lineage(session, records, parsed)

        # Update aggregated dataset lineage
        _update_dataset_lineage(session, source_tables, target_tables, query_id)

        session.commit()

        for r in records:
            session.refresh(r)

        logger.info(
            "Saved lineage for query %s: %d source(s) → %d target(s), %d record(s)",
            query_id, len(source_tables), len(target_tables), len(records),
        )
        return records
    except Exception:
        session.rollback()
        logger.exception("Failed to save lineage for query %s", query_id)
        raise
    finally:
        session.close()


def _save_query_lineage(
    session,
    query_hist_id: int,
    source_tables: list[str],
    target_tables: list[str],
) -> list[QueryLineage]:
    """Create QueryLineage records for each source→target pair."""
    records: list[QueryLineage] = []
    for target in target_tables:
        for source in source_tables:
            record = QueryLineage(
                query_hist_id=query_hist_id,
                source_table=source,
                target_table=target,
            )
            session.add(record)
            records.append(record)
    session.flush()
    return records


def _save_column_lineage(
    session,
    query_lineage_records: list[QueryLineage],
    parsed: QueryLineageResult,
) -> None:
    """Save column-level lineage entries linked to QueryLineage records."""
    if not parsed.column_lineages:
        return

    # Map target_table → QueryLineage.id (use the first record per target)
    target_to_ql: dict[str, int] = {}
    for rec in query_lineage_records:
        if rec.target_table not in target_to_ql:
            target_to_ql[rec.target_table] = rec.id

    for entry in parsed.column_lineages:
        ql_id = target_to_ql.get(entry.target.table)
        if ql_id is None:
            # Fall back to the first query lineage record
            ql_id = query_lineage_records[0].id

        source_str = f"{entry.source.table}.{entry.source.column}" if entry.source.table else entry.source.column
        target_str = entry.target.column

        col_record = ColumnLineage(
            query_lineage_id=ql_id,
            source_column=source_str,
            target_column=target_str,
            transform_type=entry.transform_type,
        )
        session.add(col_record)


def _update_dataset_lineage(
    session,
    source_tables: list[str],
    target_tables: list[str],
    query_id: str,
) -> None:
    """Update aggregated dataset lineage (upsert query_count)."""
    from sqlalchemy import func as sa_func

    for target in target_tables:
        for source in source_tables:
            existing = (
                session.query(DatasetLineage)
                .filter_by(
                    source_dataset_id=0,  # placeholder until dataset mapping is implemented
                    target_dataset_id=0,
                )
                .first()
            )
            # For now, skip aggregated lineage if dataset IDs are not resolved.
            # This will be activated once dataset name → ID mapping is implemented.
            # The per-query lineage (argus_query_lineage) is still saved with
            # raw table names, which can be resolved later.
            _ = existing, target, source, query_id
