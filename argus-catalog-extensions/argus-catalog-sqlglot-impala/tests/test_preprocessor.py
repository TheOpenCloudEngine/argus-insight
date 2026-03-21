"""Tests for Impala SQL preprocessor."""

from sqlglot_impala.preprocessor import is_lineage_relevant, preprocess


class TestIsLineageRelevant:

    def test_compute_stats(self):
        assert not is_lineage_relevant("COMPUTE STATS db.table")

    def test_compute_incremental_stats(self):
        assert not is_lineage_relevant("COMPUTE INCREMENTAL STATS db.table PARTITION (dt='2026-01-01')")

    def test_invalidate_metadata(self):
        assert not is_lineage_relevant("INVALIDATE METADATA db.table")

    def test_refresh(self):
        assert not is_lineage_relevant("REFRESH db.table")

    def test_show(self):
        assert not is_lineage_relevant("SHOW TABLES IN mydb")

    def test_describe(self):
        assert not is_lineage_relevant("DESCRIBE db.table")

    def test_explain(self):
        assert not is_lineage_relevant("EXPLAIN SELECT * FROM t")

    def test_use(self):
        assert not is_lineage_relevant("USE mydb")

    def test_set(self):
        assert not is_lineage_relevant("SET MEM_LIMIT=4g")

    def test_select(self):
        assert is_lineage_relevant("SELECT * FROM t")

    def test_insert(self):
        assert is_lineage_relevant("INSERT INTO t SELECT * FROM s")

    def test_ctas(self):
        assert is_lineage_relevant("CREATE TABLE t AS SELECT * FROM s")

    def test_upsert(self):
        assert is_lineage_relevant("UPSERT INTO t SELECT * FROM s")


class TestPreprocess:

    def test_upsert_to_insert(self):
        result = preprocess("UPSERT INTO kudu_table SELECT * FROM src")
        assert "INSERT INTO" in result
        assert "UPSERT" not in result

    def test_block_hint_removal(self):
        sql = "SELECT /* +BROADCAST */ a.id FROM t1 a JOIN /* +SHUFFLE */ t2 b ON a.id = b.id"
        result = preprocess(sql)
        assert "BROADCAST" not in result
        assert "SHUFFLE" not in result
        assert "a.id" in result

    def test_bracket_hint_removal(self):
        sql = "SELECT a.id FROM t1 a JOIN [BROADCAST] t2 b ON a.id = b.id"
        result = preprocess(sql)
        assert "[BROADCAST]" not in result

    def test_straight_join_removal(self):
        sql = "SELECT STRAIGHT_JOIN a.id FROM t1 a JOIN t2 b ON a.id = b.id"
        result = preprocess(sql)
        assert "STRAIGHT_JOIN" not in result
        assert result.strip().startswith("SELECT")

    def test_normal_sql_unchanged(self):
        sql = "INSERT INTO target SELECT a.id, b.name FROM src_a a JOIN src_b b ON a.id = b.id"
        result = preprocess(sql)
        assert result == sql
