"""Tests for Impala lineage parser."""

from sqlglot_impala.lineage_parser import ImpalaLineageParser


parser = ImpalaLineageParser()


class TestImpalaLineageParser:

    def test_insert_select_with_join(self):
        sql = """
        INSERT INTO analytics.summary
        SELECT a.user_id, b.product_name, SUM(a.amount) as total
        FROM sales.orders a
        JOIN catalog.products b ON a.product_id = b.id
        GROUP BY a.user_id, b.product_name
        """
        r = parser.parse(sql)
        assert r is not None
        assert "sales.orders" in r.source_tables
        assert "catalog.products" in r.source_tables
        assert r.target_tables == ["analytics.summary"]
        assert len(r.joins) == 1
        assert len(r.column_lineages) == 3

    def test_ctas(self):
        sql = """
        CREATE TABLE default.user_summary AS
        SELECT user_id, COUNT(*) as cnt
        FROM default.login_history
        GROUP BY user_id
        """
        r = parser.parse(sql)
        assert r is not None
        assert r.source_tables == ["default.login_history"]
        assert r.target_tables == ["default.user_summary"]

    def test_upsert_parsed_as_insert(self):
        sql = """
        UPSERT INTO kudu_db.target_table
        SELECT id, name, value FROM staging.source_table
        """
        r = parser.parse(sql)
        assert r is not None
        assert r.source_tables == ["staging.source_table"]
        assert r.target_tables == ["kudu_db.target_table"]

    def test_compute_stats_skipped(self):
        assert parser.parse("COMPUTE STATS db.table") is None

    def test_invalidate_metadata_skipped(self):
        assert parser.parse("INVALIDATE METADATA db.table") is None

    def test_refresh_skipped(self):
        assert parser.parse("REFRESH db.table") is None

    def test_hints_stripped_before_parse(self):
        sql = """
        INSERT INTO target
        SELECT /* +BROADCAST */ a.id, b.name
        FROM src_a a JOIN [SHUFFLE] src_b b ON a.id = b.id
        """
        r = parser.parse(sql)
        assert r is not None
        assert "src_a" in r.source_tables
        assert "src_b" in r.source_tables

    def test_simple_select(self):
        r = parser.parse("SELECT id, name FROM mydb.users")
        assert r is not None
        assert r.source_tables == ["mydb.users"]
        assert r.target_tables == []

    def test_column_transform_types(self):
        sql = """
        INSERT INTO target
        SELECT a.id, SUM(a.amount), CASE WHEN a.status = 1 THEN 'Y' ELSE 'N' END
        FROM source a
        GROUP BY a.id, a.status
        """
        r = parser.parse(sql)
        assert r is not None
        types = [cl.transform_type for cl in r.column_lineages]
        assert "DIRECT" in types
        assert "AGGREGATION" in types
        assert "EXPRESSION" in types
