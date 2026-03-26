"""Prompt templates for AI metadata generation.

Each function builds a structured prompt from available catalog context
(table info, columns, DDL, sample data) for a specific generation task.

Enhanced context (optional):
- glossary: StandardWord abbreviation→name mappings (domain-specific terminology)
- lineage: upstream/downstream dataset relationships
- fewshot_examples: previously approved AI generations as reference
"""

SYSTEM_PROMPT = (
    "You are a data catalog assistant that generates metadata for database tables. "
    "Always respond with valid JSON only, no markdown fences or extra text."
)


# ---------------------------------------------------------------------------
# Shared context builders
# ---------------------------------------------------------------------------

def _build_glossary_section(glossary: list[dict] | None, columns: list[dict]) -> str:
    """Build a glossary section that maps abbreviations found in column names.

    Only includes glossary entries whose abbreviation appears in the actual column names,
    keeping the prompt focused and token-efficient.
    """
    if not glossary:
        return ""

    # Collect all tokens from column names (split by _ and lowercase)
    col_tokens = set()
    for c in columns:
        for token in c["field_path"].upper().replace("-", "_").split("_"):
            if token:
                col_tokens.add(token)

    # Filter glossary to entries matching column tokens
    relevant = [g for g in glossary if g["abbr"].upper() in col_tokens]

    if not relevant:
        return ""

    lines = []
    for g in relevant[:50]:  # Limit to 50 entries
        lines.append(f"  {g['abbr']}: {g['name']} ({g['english']})")

    return (
        "\n== Terminology glossary (abbreviation → meaning) ==\n"
        + "\n".join(lines)
        + "\n"
    )


def _build_lineage_section(lineage: dict[str, list[str]] | None) -> str:
    """Build a lineage context section showing data flow relationships."""
    if not lineage:
        return ""

    upstream = lineage.get("upstream", [])
    downstream = lineage.get("downstream", [])

    if not upstream and not downstream:
        return ""

    section = "\n== Data lineage ==\n"
    if upstream:
        section += f"  Upstream (source tables): {', '.join(upstream)}\n"
    if downstream:
        section += f"  Downstream (consuming tables): {', '.join(downstream)}\n"
    return section


def _build_fewshot_section(
    examples: list[dict] | None, generation_type: str,
) -> str:
    """Build a few-shot examples section from previously approved generations."""
    if not examples:
        return ""

    section = "\n== Reference examples (previously approved descriptions in this catalog) ==\n"
    for i, ex in enumerate(examples[:3], 1):
        name = ex.get("dataset_name", "")
        text = ex.get("generated_text", "")
        # Truncate long texts
        if len(text) > 200:
            text = text[:200] + "..."
        section += f"  {i}. {name}: {text}\n"

    section += "Use a similar style and level of detail.\n"
    return section


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_dataset_description_prompt(
    table_name: str,
    database: str,
    platform_type: str,
    columns: list[dict],
    ddl: str | None = None,
    sample_rows: list[dict] | None = None,
    row_count: int | None = None,
    language: str = "ko",
    glossary: list[dict] | None = None,
    lineage: dict[str, list[str]] | None = None,
    fewshot_examples: list[dict] | None = None,
) -> str:
    """Build prompt for generating a table description."""
    col_lines = []
    for c in columns[:50]:  # Limit to 50 columns
        parts = [c["field_path"], f"({c['field_type']})"]
        if c.get("is_primary_key") == "true":
            parts.append("PK")
        if c.get("nullable") == "false":
            parts.append("NOT NULL")
        if c.get("description"):
            parts.append(f"-- {c['description']}")
        col_lines.append("  " + " ".join(parts))

    prompt = f"""Generate a concise description for this database table.
{_build_glossary_section(glossary, columns)}{_build_fewshot_section(fewshot_examples, "description")}{_build_lineage_section(lineage)}
Table: {database}.{table_name}
Platform: {platform_type}
Columns:
{chr(10).join(col_lines)}
"""

    if ddl:
        prompt += f"\nDDL:\n{ddl[:2000]}\n"

    if sample_rows:
        rows_str = "\n".join(str(r) for r in sample_rows[:5])
        prompt += f"\nSample data (first rows):\n{rows_str}\n"

    if row_count is not None:
        prompt += f"\nEstimated row count: {row_count:,}\n"

    lang_name = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}.get(
        language, language
    )
    prompt += f"""
Respond in {lang_name}.
JSON format: {{"description": "...", "confidence": 0.0-1.0}}"""
    return prompt


def build_column_descriptions_prompt(
    table_name: str,
    database: str,
    table_description: str | None,
    columns: list[dict],
    sample_values: dict[str, list] | None = None,
    language: str = "ko",
    glossary: list[dict] | None = None,
    lineage: dict[str, list[str]] | None = None,
    fewshot_examples: list[dict] | None = None,
) -> str:
    """Build prompt for generating column descriptions in batch."""
    col_lines = []
    for i, c in enumerate(columns[:80], 1):  # Limit to 80 columns
        parts = [f"{i}. {c['field_path']} ({c['field_type']}"]
        if c.get("native_type"):
            parts[0] += f", {c['native_type']}"
        parts[0] += ")"
        attrs = []
        if c.get("is_primary_key") == "true":
            attrs.append("PK")
        if c.get("is_unique") == "true":
            attrs.append("UNIQUE")
        if c.get("is_indexed") == "true":
            attrs.append("INDEX")
        if c.get("nullable") == "false":
            attrs.append("NOT NULL")
        if attrs:
            parts.append(", ".join(attrs))
        col_lines.append(" ".join(parts))

    prompt = f"""Generate descriptions for all columns in this table.
{_build_glossary_section(glossary, columns)}{_build_lineage_section(lineage)}
Table: {database}.{table_name}
"""
    if table_description:
        prompt += f"Table purpose: {table_description}\n"

    prompt += f"""
Columns:
{chr(10).join(col_lines)}
"""

    if sample_values:
        prompt += "\nSample values per column:\n"
        for col_name, values in list(sample_values.items())[:30]:
            vals_str = ", ".join(str(v) for v in values[:5])
            prompt += f"  {col_name}: [{vals_str}]\n"

    lang_name = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}.get(
        language, language
    )
    prompt += f"""
Respond in {lang_name}.
JSON format: {{"columns": [{{"name": "col_name", "description": "...", "confidence": 0.0-1.0}}, ...]}}"""
    return prompt


def build_tag_suggestion_prompt(
    table_name: str,
    database: str,
    description: str | None,
    columns: list[dict],
    existing_tags: list[str],
    language: str = "ko",
    glossary: list[dict] | None = None,
    lineage: dict[str, list[str]] | None = None,
) -> str:
    """Build prompt for suggesting tags for a dataset."""
    col_names = [c["field_path"] for c in columns[:50]]

    prompt = f"""Suggest relevant classification tags for this database table.
{_build_glossary_section(glossary, columns)}{_build_lineage_section(lineage)}
Table: {database}.{table_name}
"""
    if description:
        prompt += f"Description: {description}\n"

    prompt += f"Columns: {', '.join(col_names)}\n"

    if existing_tags:
        prompt += f"\nExisting tags in catalog (prefer these): {', '.join(existing_tags)}\n"

    lang_name = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}.get(
        language, language
    )
    prompt += f"""
Suggest 2-5 tags. Prefer existing tags when appropriate.
Respond in {lang_name}.
JSON format: {{"tags": ["existing_tag1", ...], "new_tags": [{{"name": "...", "description": "..."}}, ...]}}"""
    return prompt


def build_pii_detection_prompt(
    table_name: str,
    database: str,
    columns: list[dict],
    sample_values: dict[str, list] | None = None,
    glossary: list[dict] | None = None,
) -> str:
    """Build prompt for detecting PII columns."""
    col_lines = []
    for c in columns[:80]:
        col_lines.append(f"  {c['field_path']} ({c['field_type']})")

    prompt = f"""Analyze columns for Personally Identifiable Information (PII).
{_build_glossary_section(glossary, columns)}
Table: {database}.{table_name}
Columns:
{chr(10).join(col_lines)}
"""

    if sample_values:
        prompt += "\nSample values:\n"
        for col_name, values in list(sample_values.items())[:30]:
            vals_str = ", ".join(str(v) for v in values[:5])
            prompt += f"  {col_name}: [{vals_str}]\n"

    prompt += """
PII types: EMAIL, PHONE, SSN, NAME, ADDRESS, CREDIT_CARD, IP_ADDRESS, DATE_OF_BIRTH, NATIONAL_ID, OTHER
Only flag columns with high confidence.
JSON format: {"pii_columns": [{"name": "col_name", "pii_type": "EMAIL", "confidence": 0.0-1.0, "reason": "..."}]}
If no PII detected, return: {"pii_columns": []}"""
    return prompt
