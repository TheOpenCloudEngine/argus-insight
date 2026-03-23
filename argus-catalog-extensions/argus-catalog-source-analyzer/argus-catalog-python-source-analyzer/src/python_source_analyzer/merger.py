"""Generic result merger shared by all Python framework analyzers."""

from __future__ import annotations

from python_source_analyzer.models import FileAnalysisResult, RawMapping


class ResultMerger:
    """Merges AST and regex analysis results with deduplication."""

    def merge(
        self,
        ast_result: FileAnalysisResult | None,
        regex_result: FileAnalysisResult,
    ) -> FileAnalysisResult:
        if ast_result is None:
            return regex_result

        merged = FileAnalysisResult(
            source_file=ast_result.source_file,
            module_path=ast_result.module_path or regex_result.module_path,
            imports=ast_result.imports or regex_result.imports,
            mappings=list(ast_result.mappings),
        )

        existing: dict[tuple[str, str], RawMapping] = {}
        for m in merged.mappings:
            key = (m.class_or_function, m.table_name)
            existing[key] = m

        for m in regex_result.mappings:
            key = (m.class_or_function, m.table_name)
            if key in existing:
                existing[key] = self._merge_access(existing[key], m)
            else:
                existing[key] = m
                merged.mappings.append(m)

        merged.mappings = list(existing.values())
        return merged

    def _merge_access(self, a: RawMapping, b: RawMapping) -> RawMapping:
        if a.access_type == b.access_type:
            return a
        return RawMapping(
            table_name=a.table_name,
            class_or_function=a.class_or_function,
            access_type="RW",
            framework=a.framework or b.framework,
            pattern=a.pattern or b.pattern,
        )
