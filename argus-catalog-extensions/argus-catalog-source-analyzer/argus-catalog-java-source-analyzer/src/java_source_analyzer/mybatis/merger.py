"""Merge MyBatis AST and regex analysis results with deduplication."""

from __future__ import annotations

from java_source_analyzer.models import FileAnalysisResult, RawMapping


class MyBatisResultMerger:
    """Merges AST and regex MyBatis results, deduplicating."""

    def merge(
        self,
        ast_result: FileAnalysisResult | None,
        regex_result: FileAnalysisResult,
    ) -> FileAnalysisResult:
        """Merge two results, preferring AST data when available."""
        if ast_result is None:
            return regex_result

        merged = FileAnalysisResult(
            source_file=ast_result.source_file,
            package_name=ast_result.package_name or regex_result.package_name,
            imports=ast_result.imports or regex_result.imports,
            mappings=list(ast_result.mappings),
        )

        existing: set[tuple[str, str]] = {
            (m.class_or_method, m.table_name) for m in merged.mappings
        }

        for m in regex_result.mappings:
            key = (m.class_or_method, m.table_name)
            if key not in existing:
                existing.add(key)
                merged.mappings.append(m)

        return merged
