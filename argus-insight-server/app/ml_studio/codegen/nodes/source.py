"""Code generators for Source nodes."""


def gen_source_csv(var: str, cfg: dict) -> list[str]:
    bucket = cfg.get("bucket", "")
    path = cfg.get("path", "")
    delim = cfg.get("delimiter", "auto")
    enc = cfg.get("encoding", "utf-8")

    fname = path.rsplit("/", 1)[-1] if "/" in path else path
    lines = [f'# Source: CSV — {fname}']
    lines.append(f'{var} = _load_csv("{bucket}", "{path}", '
                 f'delimiter={"None" if delim == "auto" else repr(delim)}, '
                 f'encoding="{enc}")')

    # Apply column exclusions
    cols = cfg.get("columns", [])
    excludes = [c["name"] for c in cols if isinstance(c, dict) and c.get("action") == "exclude"]
    if excludes:
        lines.append(f'{var} = {var}.drop(columns={excludes}, errors="ignore")')

    lines.append(f'print(f"[Source] {{{var}.shape[0]}} rows, {{{var}.shape[1]}} columns")')
    lines.append("")
    return lines


def gen_source_parquet(var: str, cfg: dict) -> list[str]:
    bucket = cfg.get("bucket", "")
    path = cfg.get("path", "")
    fname = path.rsplit("/", 1)[-1] if "/" in path else path
    lines = [f'# Source: Parquet — {fname}']
    lines.append(f'{var} = _load_parquet("{bucket}", "{path}")')

    cols = cfg.get("columns", [])
    excludes = [c["name"] for c in cols if isinstance(c, dict) and c.get("action") == "exclude"]
    if excludes:
        lines.append(f'{var} = {var}.drop(columns={excludes}, errors="ignore")')

    lines.append(f'print(f"[Source] {{{var}.shape[0]}} rows, {{{var}.shape[1]}} columns")')
    lines.append("")
    return lines


def gen_source_database(var: str, cfg: dict) -> list[str]:
    mode = cfg.get("mode", "sql")
    lines = [f'# Source: Database ({cfg.get("db_type", "postgresql")})']

    if mode == "sql" and cfg.get("query"):
        query = cfg["query"].replace('"""', '\\"\\"\\"')
        lines.append(f'{var} = pd.read_sql("""{query}""", _db_engine)')
    else:
        table = cfg.get("table", "")
        schema = cfg.get("schema", "public")
        lines.append(f'{var} = pd.read_sql_table("{table}", _db_engine, schema="{schema}")')

    lines.append(f'print(f"[Source] {{{var}.shape[0]}} rows, {{{var}.shape[1]}} columns")')
    lines.append("")
    return lines


SOURCE_GENERATORS = {
    "source_csv": gen_source_csv,
    "source_parquet": gen_source_parquet,
    "source_database": gen_source_database,
}
