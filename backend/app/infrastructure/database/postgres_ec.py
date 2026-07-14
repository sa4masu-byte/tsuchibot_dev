from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.application.ec import ECExplorationRecord


class PostgresECExplorationRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def save(self, record: ECExplorationRecord) -> None:
        async with (
            await AsyncConnection.connect(self._database_url) as connection,
            connection.transaction(),
        ):
            await connection.execute(
                """
                insert into ec.exploration_sessions (
                    id, run_id, trigger_reason, useful_jimoty_candidates,
                    keyword_limit, keyword_count, policy_version, status, observed_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.id,
                    record.request.run_id,
                    record.trigger_reason,
                    record.request.useful_jimoty_candidates,
                    record.policy.keyword_limit,
                    len(record.keywords),
                    record.policy.version,
                    record.status,
                    record.request.observed_at,
                ),
            )
            evaluations = {
                (item.offer.source, item.offer.source_item_id): item
                for item in record.evaluations
            }
            for source_order, collection in enumerate(record.collections, start=1):
                for keyword in record.keywords:
                    collected_count = sum(
                        offer.matched_keyword is None
                        or offer.matched_keyword.casefold() == keyword.value.casefold()
                        for offer in collection.offers
                    )
                    await connection.execute(
                        """
                        insert into ec.search_attempts (
                            exploration_session_id, source, source_order, query_order,
                            keyword, strategy, status, parser_version, collected_count,
                            error_category, error_message
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            record.id,
                            collection.source.value,
                            source_order,
                            keyword.order,
                            keyword.value,
                            keyword.strategy.value,
                            collection.status,
                            collection.parser_version,
                            collected_count,
                            collection.error_category,
                            collection.error_message,
                        ),
                    )
                for offer in collection.offers:
                    cursor = await connection.execute(
                        """
                        insert into ec.offers (
                            exploration_session_id, source, source_item_id, canonical_url,
                            title, displayed_price_jpy, sourcing_shipping_jpy,
                            definite_coupon_jpy, points_reference_jpy, available, category,
                            product_type, selected_variant, variant_price_confirmed,
                            delivery_days, product_rating, review_count, seller_rating,
                            seller_name, shop_id, shop_rating, brand, character_name,
                            authenticity_supported, original_currency, original_amount,
                            matched_keyword, image_urls, raw_metadata
                        ) values (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) returning id
                        """,
                        (
                            record.id,
                            offer.source.value,
                            offer.source_item_id,
                            offer.canonical_url,
                            offer.title,
                            offer.displayed_price_jpy,
                            offer.sourcing_shipping_jpy,
                            offer.definite_coupon_jpy,
                            offer.points_reference_jpy,
                            offer.available,
                            offer.category,
                            offer.product_type.value,
                            offer.selected_variant,
                            offer.variant_price_confirmed,
                            offer.delivery_days,
                            offer.product_rating,
                            offer.review_count,
                            offer.seller_rating,
                            offer.seller_name,
                            offer.shop_id,
                            offer.shop_rating,
                            offer.brand,
                            offer.character_name,
                            offer.authenticity_supported,
                            offer.original_currency,
                            offer.original_amount,
                            offer.matched_keyword,
                            Jsonb(list(offer.image_urls)),
                            Jsonb(offer.raw_metadata or {}),
                        ),
                    )
                    row = await cursor.fetchone()
                    assert row is not None
                    evaluation = evaluations[(offer.source, offer.source_item_id)]
                    await connection.execute(
                        """
                        insert into ec.offer_evaluations (
                            offer_id, eligibility, sourcing_cost_jpy,
                            reason_codes, policy_version
                        ) values (%s, %s, %s, %s, %s)
                        """,
                        (
                            UUID(str(row[0])),
                            evaluation.eligibility.value,
                            evaluation.sourcing_cost_jpy,
                            Jsonb(list(evaluation.reason_codes)),
                            record.policy.version,
                        ),
                    )
            await connection.execute(
                """
                insert into runs.metrics (run_id, metric_code, value, dimensions)
                values (%s, 'ec_exploration_completed', 1, %s)
                """,
                (
                    record.request.run_id,
                    Jsonb(
                        {
                            "status": record.status,
                            "eligible_count": sum(
                                item.eligibility.value == "eligible"
                                for item in record.evaluations
                            ),
                        }
                    ),
                ),
            )
            await connection.execute(
                """
                insert into audit.events (
                    actor, action, entity_type, entity_id, after_value
                ) values ('manual-worker', 'ec_exploration_completed',
                          'ec_exploration_session', %s, %s)
                """,
                (str(record.id), Jsonb({"status": record.status})),
            )

    async def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            rows = await (
                await connection.execute(
                    """
                    select session.*,
                           count(evaluation.id) as offer_count,
                           count(evaluation.id) filter (
                               where evaluation.eligibility = 'eligible'
                           ) as eligible_count,
                           count(evaluation.id) filter (
                               where evaluation.eligibility = 'confirmation_required'
                           ) as confirmation_required_count,
                           count(evaluation.id) filter (
                               where evaluation.eligibility = 'rejected'
                           ) as rejected_count
                    from ec.exploration_sessions session
                    left join ec.offers offer
                      on offer.exploration_session_id = session.id
                    left join ec.offer_evaluations evaluation
                      on evaluation.offer_id = offer.id
                    group by session.id
                    order by session.created_at desc
                    limit %s
                    """,
                    (limit,),
                )
            ).fetchall()
        return [dict(row) for row in rows]

    async def session_detail(self, session_id: UUID) -> dict[str, Any] | None:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            session = await (
                await connection.execute(
                    "select * from ec.exploration_sessions where id = %s",
                    (session_id,),
                )
            ).fetchone()
            if session is None:
                return None
            attempts = await (
                await connection.execute(
                    """
                    select source, source_order, query_order, keyword, strategy,
                           status, parser_version, collected_count,
                           error_category, error_message
                    from ec.search_attempts
                    where exploration_session_id = %s
                    order by source_order, query_order
                    """,
                    (session_id,),
                )
            ).fetchall()
            offers = await (
                await connection.execute(
                    """
                    select offer.*, evaluation.eligibility,
                           evaluation.sourcing_cost_jpy, evaluation.reason_codes,
                           evaluation.policy_version
                    from ec.offers offer
                    join ec.offer_evaluations evaluation on evaluation.offer_id = offer.id
                    where offer.exploration_session_id = %s
                    order by
                        case offer.source
                            when 'amazon' then 1 when 'rakuten' then 2
                            when 'aliexpress' then 3 when 'shein' then 4
                        end,
                        evaluation.sourcing_cost_jpy
                    """,
                    (session_id,),
                )
            ).fetchall()
        return {
            "session": dict(session),
            "attempts": [dict(row) for row in attempts],
            "offers": [dict(row) for row in offers],
        }
