"""Impala lineage service — parses collected queries and saves lineage records."""

from __future__ import annotations

import logging
import sys

from sync.core.database import get_session
from sync.platforms.hive.models import ColumnLineage, QueryLineage
from sync.platforms.impala.models import ImpalaQueryHistory

logger = logging.getLogger(__name__)

# Import ImpalaLineageParser — the argus-catalog-sqlglot-impala package must be
# installed or its src/ directory must be on sys.path.
try:
    from sqlglot_impala.lineage_parser import ImpalaLineageParser
    _parser = ImpalaLineageParser()
except ImportError:
    logger.warning(
        "sqlglot_impala package not found. Impala lineage parsing will be disabled. "
        "Install argus-catalog-sqlglot-impala or add its src/ to PYTHONPATH."
    )
    _parser = None


def process_impala_query_lineage(record: ImpalaQueryHistory) -> int:
    """Parse an Impala query and save lineage records.

    Args:
        record: Persisted ImpalaQueryHistory record with id and statement.

    Returns:
        Number of QueryLineage records created.
    """
    if _parser is None:
        return 0

    if not record.statement:
        return 0

    # Only parse completed queries (FINISHED)
    if record.query_state != "FINISHED":
        return 0

    # Only parse DML/QUERY types (skip DDL-only)
    if record.query_type not in ("DML", "QUERY"):
        return 0

    parsed = _parser.parse(record.statement)
    if parsed is None:
        return 0

    if not parsed.source_tables or not parsed.target_tables:
        return 0

    session = get_session()
    try:
        lineage_records: list[QueryLineage] = []

        for target in parsed.target_tables:
            for source in parsed.source_tables:
                ql = QueryLineage(
                    query_hist_id=record.id,
                    source_table=source,
                    target_table=target,
                )
                session.add(ql)
                lineage_records.append(ql)

        session.flush()

        # Save column-level lineage
        if parsed.column_lineages and lineage_records:
            target_to_ql: dict[str, int] = {}
            for rec in lineage_records:
                if rec.target_table not in target_to_ql:
                    target_to_ql[rec.target_table] = rec.id

            for entry in parsed.column_lineages:
                ql_id = target_to_ql.get(entry.target.table, lineage_records[0].id)
                source_str = (
                    f"{entry.source.table}.{entry.source.column}"
                    if entry.source.table else entry.source.column
                )
                col_record = ColumnLineage(
                    query_lineage_id=ql_id,
                    source_column=source_str,
                    target_column=entry.target.column,
                    transform_type=entry.transform_type,
                )
                session.add(col_record)

        session.commit()
        count = len(lineage_records)
        logger.debug(
            "Saved %d lineage record(s) for Impala query %s",
            count, record.query_id,
        )
        return count
    except Exception:
        session.rollback()
        logger.exception("Failed to save lineage for Impala query %s", record.query_id)
        return 0
    finally:
        session.close()
