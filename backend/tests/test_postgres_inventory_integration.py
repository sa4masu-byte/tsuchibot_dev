"""Live database contract, enabled only for a disposable *_test database."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from backend.app.infrastructure.database.migrations import PostgresMigrationRunner
from backend.app.infrastructure.database.postgres_inventory import (
    PostgresInventoryLearningRepository,
)
from psycopg import AsyncConnection
from psycopg.rows import dict_row


@pytest.mark.asyncio
async def test_migrations_and_inventory_command_contract() -> None:
    database_url = os.getenv("TSUCHIBOT_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("disposable PostgreSQL test database is not configured")
    if not urlparse(database_url).path.endswith("_test"):
        pytest.fail("TSUCHIBOT_TEST_DATABASE_URL must name a *_test database")

    migrations = Path(__file__).parents[1] / "migrations"
    runner = PostgresMigrationRunner(database_url, migrations)
    await runner.apply()
    assert await runner.apply() == ()
    _, pending = await runner.status()
    assert pending == ()

    now = datetime.now(UTC)
    session_id = uuid4()
    recommendation_id = uuid4()
    async with await AsyncConnection.connect(database_url, row_factory=dict_row) as connection:
        run = await (
            await connection.execute(
                """
                insert into runs.exploration_runs (mode, trigger_source, requested_by, status)
                values ('incremental', 'test', 'integration-test', 'completed') returning id
                """
            )
        ).fetchone()
        product = await (
            await connection.execute(
                """
                insert into catalog.canonical_products (display_name)
                values ('Test item') returning id
                """
            )
        ).fetchone()
        source = await (
            await connection.execute(
                """
                insert into catalog.source_products (
                    source_type, source_item_id, canonical_url, parser_version,
                    first_seen_at, last_seen_at, current_availability, current_price_jpy
                ) values ('test', %s, %s, 'test-v1', %s, %s, 'available', 1001)
                returning id
                """,
                (str(uuid4()), "https://example.test/item", now, now),
            )
        ).fetchone()
        assert run and product and source
        run_id = UUID(str(run["id"]))
        product_id = UUID(str(product["id"]))
        source_id = UUID(str(source["id"]))
        await connection.execute(
            """
            insert into research.sessions (
                id, canonical_product_id, run_id, provider, evidence_period_start,
                evidence_period_end, config_version, status, started_at
            ) values (%s, %s, %s, 'manual', %s, %s, 'test-v1', 'completed', %s)
            """,
            (session_id, product_id, run_id, now.date(), now.date(), now),
        )
        await connection.execute(
            """
            insert into recommendation.recommendations (
                id, canonical_product_id, source_product_id, research_session_id, run_id,
                input_snapshot, estimated_sale_price_jpy, expected_profit_jpy,
                sales_prospect_score, confidence_score, recommendation_tier,
                config_version, fee_rule_version, shipping_rule_version, scoring_version,
                threshold_version, evidence_snapshot_hash, created_at
            ) values (
                %s, %s, %s, %s, %s, '{}', 2000, 500, 70, 70, 'candidate',
                'test-v1', 'test-v1', 'test-v1', 'test-v1', 'test-v1', %s, %s
            )
            """,
            (
                recommendation_id,
                product_id,
                source_id,
                session_id,
                run_id,
                uuid4().hex,
                now,
            ),
        )

    repository = PostgresInventoryLearningRepository(database_url)
    purchase = {
        "purchased": True,
        "purchased_at": now,
        "quantity": 3,
        "product_amount_jpy": 1001,
        "sourcing_shipping_jpy": 0,
        "coupon_jpy": 0,
        "point_reference_jpy": 0,
        "actual_charged_amount_jpy": 1001,
        "note": None,
    }
    purchase_key = str(uuid4())
    position = await repository.record_purchase(product_id, purchase, "test", purchase_key)
    position_id = UUID(str(position["id"]))
    replay = await repository.record_purchase(product_id, purchase, "test", purchase_key)
    assert replay["id"] == position_id
    with pytest.raises(ValueError, match="already used"):
        await repository.record_purchase(
            product_id, {**purchase, "quantity": 2}, "test", purchase_key
        )

    listing = {
        "listed_at": now,
        "marketplace": "test",
        "listing_price_jpy": 2000,
        "quantity": 3,
        "listing_url": None,
    }
    listing_key = str(uuid4())
    await repository.record_listing(position_id, listing, "test", listing_key)
    await repository.record_listing(position_id, listing, "test", listing_key)
    sale = {
        "sold_at": now,
        "sold_price_jpy": 2000,
        "actual_fee_jpy": 200,
        "actual_shipping_jpy": 210,
        "quantity": 1,
    }
    sale_key = str(uuid4())
    sold = await repository.record_sale(position_id, sale, "test", sale_key)
    assert sold["sold_quantity"] == 1
    assert sold["realised_profit_jpy"] == 1257
    assert (await repository.record_sale(position_id, sale, "test", sale_key))["sold_quantity"] == 1
    with pytest.raises(ValueError, match="remaining inventory"):
        await repository.record_sale(position_id, {**sale, "quantity": 3}, "test", str(uuid4()))

    outcome = {"outcome_type": "damaged", "quantity": 1, "occurred_at": now, "note": None}
    outcome_key = str(uuid4())
    damaged = await repository.record_negative_outcome(position_id, outcome, "test", outcome_key)
    assert damaged["remaining_quantity"] == 1
    assert (await repository.record_negative_outcome(position_id, outcome, "test", outcome_key))[
        "failed_quantity"
    ] == 1

    signal_key = str(uuid4())
    await repository.record_preference(product_id, "want", None, "test", signal_key)
    await repository.record_preference(product_id, "want", None, "test", signal_key)
    with pytest.raises(ValueError, match="already used"):
        await repository.record_research_value(
            product_id, "worth_researching", None, "test", signal_key
        )

    hypotheses = await repository.list_hypotheses()
    assert hypotheses
    hypothesis_id = UUID(str(hypotheses[0]["id"]))
    evidence = {
        "evidence_type": "actual_sale",
        "direction": "supporting",
        "strength": Decimal("0.7"),
        "source_reference_type": "sale_event",
        "source_reference_id": None,
        "summary": "Integration test evidence",
    }
    evidence_key = str(uuid4())
    first = await repository.add_hypothesis_evidence(hypothesis_id, evidence, "test", evidence_key)
    second = await repository.add_hypothesis_evidence(hypothesis_id, evidence, "test", evidence_key)
    assert len(first["evidence"]) == len(second["evidence"]) == 1

    async with await AsyncConnection.connect(database_url, row_factory=dict_row) as connection:
        for table, key in (
            ("inventory.purchase_events", purchase_key),
            ("inventory.listing_events", listing_key),
            ("inventory.sale_events", sale_key),
            ("inventory.negative_outcomes", outcome_key),
            ("learning.user_preference_signals", signal_key),
            ("learning.hypothesis_evidence", evidence_key),
        ):
            row = await (
                await connection.execute(
                    f"select count(*) as count from {table} where idempotency_key = %s",
                    (key,),
                )
            ).fetchone()
            assert row and row["count"] == 1
