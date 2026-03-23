"""Merge AST and regex analysis results with deduplication."""

from __future__ import annotations

from java_source_analyzer.models import FileAnalysisResult, RawMapping


class ResultMerger:
    """Merges AST and regex analysis results, deduplicating and resolving conflicts."""

    def merge(
        self,
        ast_result: FileAnalysisResult | None,
        regex_result: FileAnalysisResult,
    ) -> FileAnalysisResult:
        """Merge two results, preferring AST data when available.

        Rules:
        1. AST result is the base (more accurate structural info).
        2. Regex results add NEW table mappings not found by AST.
        3. Deduplication key: (class_or_method, table_name).
        4. Access type: union merge (R + W = RW).
        """
        if ast_result is None:
            return regex_result

        # Start with AST as base
        merged = FileAnalysisResult(
            source_file=ast_result.source_file,
            package_name=ast_result.package_name or regex_result.package_name,
            imports=ast_result.imports or regex_result.imports,
            mappings=list(ast_result.mappings),
        )

        # Build index of existing mappings
        existing: dict[tuple[str, str], RawMapping] = {}
        for m in merged.mappings:
            key = (m.class_or_method, m.table_name)
            if key in existing:
                # Merge access types
                existing[key] = self._merge_access(existing[key], m)
            else:
                existing[key] = m

        # Add regex results that are new
        for m in regex_result.mappings:
            key = (m.class_or_method, m.table_name)
            if key in existing:
                # Merge access type if different
                existing[key] = self._merge_access(existing[key], m)
            else:
                existing[key] = m
                merged.mappings.append(m)

        # Update mappings with merged access types
        merged.mappings = list(existing.values())

        return merged

    def _merge_access(self, a: RawMapping, b: RawMapping) -> RawMapping:
        """Merge access types: R + W = RW, same stays same."""
        access_a = a.access_type
        access_b = b.access_type

        if access_a == access_b:
            return a

        if {access_a, access_b} == {"R", "W"}:
            merged_access = "RW"
        elif "RW" in (access_a, access_b):
            merged_access = "RW"
        else:
            merged_access = "RW"

        return RawMapping(
            table_name=a.table_name,
            class_or_method=a.class_or_method,
            access_type=merged_access,
            framework=a.framework or b.framework,
            annotation=a.annotation or b.annotation,
        )
