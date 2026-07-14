from pathlib import Path

import pytest
from backend.app.infrastructure.database.migrations import (
    MigrationError,
    discover_migrations,
    pending_migrations,
)

MIGRATIONS = Path(__file__).parents[1] / "migrations"


def test_all_migrations_are_pending_for_empty_database() -> None:
    migrations = discover_migrations(MIGRATIONS)
    assert [migration.name for migration in pending_migrations(migrations, {})] == [
        "0001_foundation.sql",
        "0002_seed_sources.sql",
        "0003_catalog.sql",
        "0004_ai_analysis.sql",
        "0005_mercari_research.sql",
        "0006_visual_search_evidence.sql",
        "0007_recommendations.sql",
        "0008_web_review.sql",
        "0009_ec_exploration.sql",
    ]


def test_applied_migration_checksum_cannot_change() -> None:
    migrations = discover_migrations(MIGRATIONS)
    with pytest.raises(MigrationError, match="checksum changed"):
        pending_migrations(migrations, {migrations[0].name: "incorrect"})


def test_unknown_database_migration_is_rejected() -> None:
    migrations = discover_migrations(MIGRATIONS)
    applied = {migration.name: migration.checksum for migration in migrations}
    applied["9999_unknown.sql"] = "checksum"
    with pytest.raises(MigrationError, match="unknown migrations"):
        pending_migrations(migrations, applied)
