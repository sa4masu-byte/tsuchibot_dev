from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "migrations"


def test_migrations_are_ordered_and_parse_as_postgresql() -> None:
    migrations = sorted(MIGRATIONS.glob("*.sql"))
    assert [migration.name for migration in migrations] == [
        "0001_foundation.sql",
        "0002_seed_sources.sql",
        "0003_catalog.sql",
        "0004_ai_analysis.sql",
        "0005_mercari_research.sql",
        "0006_visual_search_evidence.sql",
        "0007_recommendations.sql",
        "0008_web_review.sql",
    ]
    for migration in migrations:
        statements = parse_sql(migration.read_text())
        assert statements, f"{migration.name} must contain SQL statements"


def test_catalog_history_tables_have_append_only_guards() -> None:
    catalog_sql = (MIGRATIONS / "0003_catalog.sql").read_text()
    for table in (
        "source_observations",
        "price_observations",
        "availability_observations",
    ):
        assert f"create trigger {table}_append_only" in catalog_sql


def test_research_history_tables_have_append_only_guards() -> None:
    research_sql = (MIGRATIONS / "0005_mercari_research.sql").read_text()
    for trigger in (
        "research_search_queries_append_only",
        "research_query_executions_append_only",
        "research_query_listing_links_append_only",
        "research_comparable_decisions_append_only",
        "research_price_statistics_append_only",
        "research_shipping_statistics_append_only",
    ):
        assert f"create trigger {trigger}" in research_sql

    visual_sql = (MIGRATIONS / "0006_visual_search_evidence.sql").read_text()
    assert "create trigger visual_search_evidence_append_only" in visual_sql

    recommendation_sql = (MIGRATIONS / "0007_recommendations.sql").read_text()
    for trigger in (
        "recommendations_append_only",
        "recommendation_reasons_append_only",
        "recommendation_quantities_append_only",
    ):
        assert f"create trigger {trigger}" in recommendation_sql


def test_web_review_migration_has_correction_history_and_rls() -> None:
    review_sql = (MIGRATIONS / "0008_web_review.sql").read_text()
    assert "create table catalog.product_corrections" in review_sql
    assert "idempotency_key text not null unique" in review_sql
    assert "alter table catalog.product_corrections enable row level security" in review_sql
