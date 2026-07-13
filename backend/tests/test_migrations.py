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
