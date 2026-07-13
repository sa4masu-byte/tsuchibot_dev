from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from backend.app.application.research import QueryExecution, ResearchOutcome
from backend.app.domain.research import ListingStatus, MarketplaceListing


class PostgresResearchRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def save(self, outcome: ResearchOutcome) -> None:
        async with (
            await AsyncConnection.connect(self._database_url) as connection,
            connection.transaction(),
        ):
            await connection.execute(
                """
                insert into research.sessions (
                    id, canonical_product_id, run_id, provider,
                    evidence_period_start, evidence_period_end, config_version,
                    status, started_at, completed_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    outcome.session_id,
                    outcome.request.canonical_product_id,
                    outcome.request.run_id,
                    outcome.provider,
                    outcome.evidence_period_start.date(),
                    outcome.evidence_period_end.date(),
                    outcome.request.config_version,
                    outcome.status,
                    outcome.request.researched_at,
                    outcome.completed_at,
                ),
            )
            listing_ids: dict[str, UUID] = {}
            for execution in outcome.executions:
                query_id = await self._insert_query(connection, outcome, execution)
                error_id = await self._insert_error(connection, outcome, execution)
                await self._insert_execution(connection, execution, query_id, error_id)
                for rank, listing in enumerate(execution.listings, start=1):
                    listing_id = listing_ids.get(listing.external_listing_id)
                    if listing_id is None:
                        listing_id = await self._upsert_listing(connection, outcome, listing)
                        listing_ids[listing.external_listing_id] = listing_id
                    await connection.execute(
                        """
                        insert into research.query_listing_links (
                            query_execution_id, marketplace_listing_id, result_rank
                        ) values (%s, %s, %s)
                        on conflict (query_execution_id, marketplace_listing_id) do nothing
                        """,
                        (execution.id, listing_id, rank),
                    )
            for comparable in outcome.comparables:
                listing_id = await self._upsert_listing(
                    connection,
                    outcome,
                    comparable.listing,
                )
                listing_ids[comparable.listing.external_listing_id] = listing_id
                cursor = await connection.execute(
                    """
                    insert into research.comparable_evidence (
                        research_session_id, marketplace_listing_id,
                        model_similarity, title_similarity, condition_similarity,
                        attribute_similarity, total_similarity, default_decision,
                        current_decision, decision_reason, included_in_price,
                        included_in_shipping
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    returning id
                    """,
                    (
                        outcome.session_id,
                        listing_id,
                        comparable.model_similarity,
                        comparable.title_similarity,
                        comparable.condition_similarity,
                        comparable.attribute_similarity,
                        comparable.total_similarity,
                        comparable.default_decision.value,
                        comparable.current_decision.value,
                        comparable.decision_reason,
                        comparable.included_in_price,
                        comparable.included_in_shipping,
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError("comparable evidence insert did not return an ID")
                await connection.execute(
                    """
                    insert into research.comparable_decisions (
                        comparable_evidence_id, decision, reason, decided_by
                    ) values (%s, %s, %s, 'deterministic_rule')
                    """,
                    (row[0], comparable.current_decision.value, comparable.decision_reason),
                )
            await self._insert_statistics(connection, outcome)

    @staticmethod
    async def _insert_query(
        connection: AsyncConnection[tuple[object, ...]],
        outcome: ResearchOutcome,
        execution: QueryExecution,
    ) -> UUID:
        cursor = await connection.execute(
            """
            insert into research.search_queries (
                research_session_id, query_order, query_text, query_stage,
                normalized_query, generated_by
            ) values (%s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                outcome.session_id,
                execution.query.order,
                execution.query.text,
                execution.query.stage.value,
                execution.query.normalized_text,
                execution.query.generated_by,
            ),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("search query insert did not return an ID")
        return UUID(str(row[0]))

    @staticmethod
    async def _insert_error(
        connection: AsyncConnection[tuple[object, ...]],
        outcome: ResearchOutcome,
        execution: QueryExecution,
    ) -> UUID | None:
        if execution.error_category is None:
            return None
        cursor = await connection.execute(
            """
            insert into runs.errors (
                run_id, stage, source, item_id, category, retryable,
                user_message, technical_detail
            ) values (%s, 'mercari_research', 'mercari', %s, %s, false, %s, %s)
            returning id
            """,
            (
                outcome.request.run_id,
                execution.query.text,
                execution.error_category,
                "Mercari research was unavailable for one query.",
                execution.error_message,
            ),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("research error insert did not return an ID")
        return UUID(str(row[0]))

    @staticmethod
    async def _insert_execution(
        connection: AsyncConnection[tuple[object, ...]],
        execution: QueryExecution,
        query_id: UUID,
        error_id: UUID | None,
    ) -> None:
        sold_count = sum(
            listing.status is ListingStatus.SOLD for listing in execution.listings
        )
        active_count = len(execution.listings) - sold_count
        await connection.execute(
            """
            insert into research.query_executions (
                id, search_query_id, status, sold_result_count,
                active_result_count, raw_result_ref, parser_version, error_id,
                started_at, completed_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                execution.id,
                query_id,
                execution.status,
                sold_count,
                active_count,
                execution.raw_result_ref,
                execution.parser_version,
                error_id,
                execution.started_at,
                execution.completed_at,
            ),
        )

    @staticmethod
    async def _upsert_listing(
        connection: AsyncConnection[tuple[object, ...]],
        outcome: ResearchOutcome,
        listing: MarketplaceListing,
    ) -> UUID:
        attributes = dict(listing.normalized_attributes or {})
        attributes.update(
            {
                "is_bundle": listing.is_bundle,
                "bundle_unit_count": listing.bundle_unit_count,
                "is_junk": listing.is_junk,
                "is_reserved": listing.is_reserved,
            }
        )
        cursor = await connection.execute(
            """
            insert into research.marketplace_listings (
                marketplace, external_listing_id, canonical_url, title, status,
                displayed_price_jpy, sold_at, listed_at, condition,
                shipping_method, shipping_responsibility, estimated_shipping_jpy,
                image_url, normalized_attributes, first_seen_at, last_seen_at
            ) values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            on conflict (marketplace, external_listing_id) do update
            set canonical_url = excluded.canonical_url,
                title = excluded.title,
                status = excluded.status,
                displayed_price_jpy = excluded.displayed_price_jpy,
                sold_at = excluded.sold_at,
                listed_at = excluded.listed_at,
                condition = excluded.condition,
                shipping_method = excluded.shipping_method,
                shipping_responsibility = excluded.shipping_responsibility,
                estimated_shipping_jpy = excluded.estimated_shipping_jpy,
                image_url = excluded.image_url,
                normalized_attributes = excluded.normalized_attributes,
                last_seen_at = excluded.last_seen_at,
                updated_at = now()
            returning id
            """,
            (
                listing.marketplace,
                listing.external_listing_id,
                listing.canonical_url,
                listing.title,
                listing.status.value,
                listing.displayed_price_jpy,
                listing.sold_at,
                listing.listed_at,
                listing.condition,
                listing.shipping_method,
                listing.shipping_responsibility.value,
                listing.estimated_shipping_jpy,
                listing.image_url,
                Jsonb(attributes),
                outcome.completed_at,
                outcome.completed_at,
            ),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("marketplace listing upsert did not return an ID")
        return UUID(str(row[0]))

    @staticmethod
    async def _insert_statistics(
        connection: AsyncConnection[tuple[object, ...]],
        outcome: ResearchOutcome,
    ) -> None:
        price = outcome.price_statistics
        await connection.execute(
            """
            insert into research.price_statistics (
                research_session_id, evidence_snapshot_hash, included_count,
                median_price_jpy, lower_quartile_price_jpy, minimum_price_jpy,
                maximum_price_jpy, dispersion, sufficient_evidence
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                outcome.session_id,
                price.evidence_snapshot_hash,
                price.included_count,
                price.median_price_jpy,
                price.lower_quartile_price_jpy,
                price.minimum_price_jpy,
                price.maximum_price_jpy,
                price.dispersion,
                price.sufficient_evidence,
            ),
        )
        shipping = outcome.shipping_statistics
        await connection.execute(
            """
            insert into research.shipping_statistics (
                research_session_id, source_type, evidence_count,
                median_shipping_jpy, shipping_method, confidence, reason
            ) values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                outcome.session_id,
                shipping.source_type,
                shipping.evidence_count,
                shipping.median_shipping_jpy,
                shipping.shipping_method,
                shipping.confidence,
                shipping.reason,
            ),
        )
