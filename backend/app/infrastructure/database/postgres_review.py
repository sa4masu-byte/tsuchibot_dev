import hashlib
import json
from collections import Counter
from statistics import median
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def _integer_median(values: list[int]) -> int | None:
    return round(float(median(values))) if values else None


def _effective_listing_price(row: dict[str, Any]) -> int:
    attributes = dict(row.get("normalized_attributes") or {})
    unit_count = attributes.get("bundle_unit_count")
    if (
        attributes.get("is_bundle") is True
        and isinstance(unit_count, int)
        and not isinstance(unit_count, bool)
        and unit_count > 0
    ):
        return round(int(row["displayed_price_jpy"]) / unit_count)
    return int(row["displayed_price_jpy"])


class PostgresReviewRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def dashboard(self) -> dict[str, Any]:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            latest_run = await (
                await connection.execute(
                    "select * from runs.exploration_runs order by created_at desc limit 1"
                )
            ).fetchone()
            rows = await (
                await connection.execute(
                    """
                    select distinct on (r.source_product_id)
                        r.*, coalesce(correction.display_name, cp.display_name) as display_name,
                        sp.source_type, image.source_url as image_url
                    from recommendation.recommendations r
                    join catalog.canonical_products cp on cp.id = r.canonical_product_id
                    join catalog.source_products sp on sp.id = r.source_product_id
                    left join lateral (
                        select source_url from catalog.product_images
                        where source_product_id = sp.id order by image_order limit 1
                    ) image on true
                    left join lateral (
                        select corrected_value #>> '{}' as display_name
                        from catalog.product_corrections
                        where canonical_product_id = cp.id
                          and field_name = 'display_name' and is_active
                    ) correction on true
                    order by r.source_product_id, r.created_at desc
                    """
                )
            ).fetchall()
            error_count_row = await (
                await connection.execute(
                    """
                    select count(*) as open_error_count
                    from runs.errors where resolution_status = 'open'
                    """
                )
            ).fetchone()
        tiers = Counter(str(row["recommendation_tier"]) for row in rows)
        useful = [
            row
            for row in rows
            if row["recommendation_tier"] in {
                "strongly_recommended",
                "recommended",
                "candidate",
            }
        ]
        best = max(
            useful,
            key=lambda row: int(row["overall_sourcing_score"] or -1),
            default=None,
        )
        return {
            "latest_run": dict(latest_run) if latest_run else None,
            "tier_counts": {
                "strongly_recommended": tiers["strongly_recommended"],
                "recommended": tiers["recommended"],
                "candidate": tiers["candidate"],
                "reject": tiers["reject"],
            },
            "total_candidate_cost_jpy": sum(int(row["sourcing_cost_jpy"] or 0) for row in useful),
            "total_expected_profit_jpy": sum(
                int(row["expected_profit_jpy"] or 0) for row in useful
            ),
            "average_sales_prospect": (
                round(sum(int(row["sales_prospect_score"]) for row in useful) / len(useful), 1)
                if useful
                else None
            ),
            "open_error_count": (
                int(error_count_row["open_error_count"]) if error_count_row else 0
            ),
            "best_candidate": self._candidate_row(best) if best else None,
        }

    async def list_products(
        self,
        *,
        tier: str | None = None,
        search: str | None = None,
        sort: str = "overall_sourcing_score",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sort_columns = {
            "overall_sourcing_score": "overall_sourcing_score",
            "expected_profit_jpy": "expected_profit_jpy",
            "confidence_score": "confidence_score",
            "sales_prospect_score": "sales_prospect_score",
            "sourcing_cost_jpy": "sourcing_cost_jpy",
            "created_at": "created_at",
        }
        order_column = sort_columns.get(sort, "overall_sourcing_score")
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            rows = await (
                await connection.execute(
                    f"""
                    with latest as (
                        select distinct on (source_product_id) *
                        from recommendation.recommendations
                        order by source_product_id, created_at desc
                    )
                    select latest.*,
                           coalesce(correction.display_name, cp.display_name) as display_name,
                           sp.source_type,
                           observation.title as source_title,
                           image.source_url as image_url
                    from latest
                    join catalog.canonical_products cp on cp.id = latest.canonical_product_id
                    join catalog.source_products sp on sp.id = latest.source_product_id
                    left join lateral (
                        select title from catalog.source_observations
                        where source_product_id = sp.id order by observed_at desc limit 1
                    ) observation on true
                    left join lateral (
                        select source_url from catalog.product_images
                        where source_product_id = sp.id order by image_order limit 1
                    ) image on true
                    left join lateral (
                        select corrected_value #>> '{{}}' as display_name
                        from catalog.product_corrections
                        where canonical_product_id = cp.id
                          and field_name = 'display_name' and is_active
                    ) correction on true
                    where (%s is null or latest.recommendation_tier = %s)
                      and (
                          %s is null
                          or coalesce(
                              correction.display_name, cp.display_name,
                              observation.title, ''
                          )
                              ilike '%%' || %s || '%%'
                      )
                    order by {order_column} desc nulls last, latest.created_at desc
                    limit %s
                    """,
                    (tier, tier, search, search, limit),
                )
            ).fetchall()
        return [self._candidate_row(row) for row in rows]

    async def product_detail(self, product_id: UUID) -> dict[str, Any] | None:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            base = await (
                await connection.execute(
                    """
                    select cp.*, sp.id as source_product_id, sp.source_type,
                           sp.canonical_url as source_url, sp.current_price_jpy,
                           observation.title as source_title,
                           observation.displayed_category as source_category,
                           image.source_url as image_url
                    from catalog.canonical_products cp
                    join catalog.source_product_links spl on spl.canonical_product_id = cp.id
                    join catalog.source_products sp on sp.id = spl.source_product_id
                    left join lateral (
                        select title, displayed_category from catalog.source_observations
                        where source_product_id = sp.id order by observed_at desc limit 1
                    ) observation on true
                    left join lateral (
                        select source_url from catalog.product_images
                        where source_product_id = sp.id order by image_order limit 1
                    ) image on true
                    where cp.id = %s
                    order by spl.created_at desc limit 1
                    """,
                    (product_id,),
                )
            ).fetchone()
            if base is None:
                return None
            recommendation = await (
                await connection.execute(
                    """
                    select * from recommendation.recommendations
                    where canonical_product_id = %s order by created_at desc limit 1
                    """,
                    (product_id,),
                )
            ).fetchone()
            corrections = await (
                await connection.execute(
                    """
                    select id, field_name, corrected_value, reason, created_at
                    from catalog.product_corrections
                    where canonical_product_id = %s and is_active
                    order by created_at
                    """,
                    (product_id,),
                )
            ).fetchall()
            reasons: list[dict[str, Any]] = []
            comparables: list[dict[str, Any]] = []
            research: dict[str, Any] | None = None
            if recommendation is not None:
                reasons = [
                    dict(row)
                    for row in await (
                        await connection.execute(
                            """
                            select code, label, component_type, value, score_delta, source
                            from recommendation.reason_components
                            where recommendation_id = %s order by display_order
                            """,
                            (recommendation["id"],),
                        )
                    ).fetchall()
                ]
                research_row = await (
                    await connection.execute(
                        """
                        select rs.id, rs.status, rs.evidence_period_start, rs.evidence_period_end,
                               ps.included_count, ps.median_price_jpy,
                               ps.lower_quartile_price_jpy, ps.dispersion,
                               ps.sufficient_evidence
                        from research.sessions rs
                        join lateral (
                            select * from research.price_statistics
                            where research_session_id = rs.id order by created_at desc limit 1
                        ) ps on true
                        where rs.id = %s
                        """,
                        (recommendation["research_session_id"],),
                    )
                ).fetchone()
                research = dict(research_row) if research_row else None
                comparables = [
                    dict(row)
                    for row in await (
                        await connection.execute(
                            """
                            select ce.id, ml.title, ml.canonical_url, ml.image_url,
                                   ml.status, ml.displayed_price_jpy, ml.condition,
                                   ml.shipping_method, ml.estimated_shipping_jpy,
                                   ml.sold_at, ml.listed_at, ce.total_similarity,
                                   ce.current_decision, ce.decision_reason,
                                   ce.included_in_price
                            from research.comparable_evidence ce
                            join research.marketplace_listings ml
                              on ml.id = ce.marketplace_listing_id
                            where ce.research_session_id = %s
                            order by ce.total_similarity desc
                            """,
                            (recommendation["research_session_id"],),
                        )
                    ).fetchall()
                ]
        effective = dict(base)
        for correction in corrections:
            effective[str(correction["field_name"])] = correction["corrected_value"]
        return {
            "product": effective,
            "source": {
                "source_product_id": base["source_product_id"],
                "source_type": base["source_type"],
                "source_url": base["source_url"],
                "source_title": base["source_title"],
                "source_category": base["source_category"],
                "current_price_jpy": base["current_price_jpy"],
                "image_url": base["image_url"],
            },
            "recommendation": dict(recommendation) if recommendation else None,
            "reasons": reasons,
            "research": research,
            "comparables": comparables,
            "corrections": [dict(row) for row in corrections],
        }

    async def create_correction(
        self,
        product_id: UUID,
        field_name: str,
        corrected_value: object,
        reason: str | None,
        actor: str,
        idempotency_key: str,
    ) -> dict[str, UUID]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            context = await self._product_context(connection, product_id)
            if context is None:
                raise KeyError(product_id)
            existing = await (
                await connection.execute(
                    "select id from catalog.product_corrections where idempotency_key = %s",
                    (idempotency_key,),
                )
            ).fetchone()
            if existing is not None:
                return context
            previous = await (
                await connection.execute(
                    """
                    select corrected_value from catalog.product_corrections
                    where canonical_product_id = %s and field_name = %s and is_active
                    """,
                    (product_id, field_name),
                )
            ).fetchone()
            if previous is None:
                previous = await (
                    await connection.execute(
                        """
                        select case
                            when %s in (
                                'estimated_sale_price_jpy', 'estimated_shipping_jpy'
                            ) then (
                                select to_jsonb(r) -> %s
                                from recommendation.recommendations r
                                where r.canonical_product_id = cp.id
                                order by r.created_at desc limit 1
                            )
                            else to_jsonb(cp) -> %s
                        end as corrected_value
                        from catalog.canonical_products cp where cp.id = %s
                        """,
                        (field_name, field_name, field_name, product_id),
                    )
                ).fetchone()
            await connection.execute(
                """
                update catalog.product_corrections
                set is_active = false, superseded_at = now()
                where canonical_product_id = %s and field_name = %s and is_active
                """,
                (product_id, field_name),
            )
            cursor = await connection.execute(
                """
                insert into catalog.product_corrections (
                    canonical_product_id, field_name, old_effective_value,
                    corrected_value, reason, created_by, idempotency_key
                ) values (%s, %s, %s, %s, %s, %s, %s) returning id
                """,
                (
                    product_id,
                    field_name,
                    Jsonb(previous["corrected_value"] if previous else None),
                    Jsonb(corrected_value),
                    reason,
                    actor,
                    idempotency_key,
                ),
            )
            correction = await cursor.fetchone()
            await connection.execute(
                """
                insert into audit.events (
                    actor, action, entity_type, entity_id, before_value, after_value
                ) values (%s, 'product_corrected', 'canonical_product', %s, %s, %s)
                """,
                (
                    actor,
                    str(product_id),
                    Jsonb(previous["corrected_value"] if previous else None),
                    Jsonb({"field": field_name, "value": corrected_value}),
                ),
            )
            if correction is not None:
                context["correction_id"] = UUID(str(correction["id"]))
            return context

    async def set_comparable_decision(
        self,
        product_id: UUID,
        comparable_id: UUID,
        *,
        exclude: bool,
        actor: str,
        reason: str | None,
        idempotency_key: str,
    ) -> dict[str, UUID]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            row = await (
                await connection.execute(
                    """
                    select ce.*, rs.canonical_product_id, rs.run_id,
                           rs.evidence_period_start, rs.evidence_period_end,
                           ml.status, ml.sold_at, ml.listed_at,
                           ml.estimated_shipping_jpy
                    from research.comparable_evidence ce
                    join research.sessions rs on rs.id = ce.research_session_id
                    join research.marketplace_listings ml on ml.id = ce.marketplace_listing_id
                    where ce.id = %s and rs.canonical_product_id = %s
                    """,
                    (comparable_id, product_id),
                )
            ).fetchone()
            if row is None:
                raise KeyError(comparable_id)
            context = await self._product_context(connection, product_id)
            if context is None:
                raise KeyError(product_id)
            existing = await (
                await connection.execute(
                    "select id from research.comparable_decisions where idempotency_key = %s",
                    (idempotency_key,),
                )
            ).fetchone()
            if existing is not None:
                return context
            decision = "exclude" if exclude else str(row["default_decision"])
            in_period = bool(
                row["status"] == "sold"
                and (row["sold_at"] is not None or row["listed_at"] is not None)
                and row["evidence_period_start"]
                <= (row["sold_at"] or row["listed_at"]).date()
                <= row["evidence_period_end"]
            )
            included_in_price = not exclude and decision == "include" and in_period
            included_in_shipping = bool(
                not exclude
                and decision != "exclude"
                and row["estimated_shipping_jpy"] is not None
            )
            await connection.execute(
                """
                update research.comparable_evidence
                set current_decision = %s, decision_reason = %s,
                    included_in_price = %s,
                    included_in_shipping = %s,
                    updated_at = now()
                where id = %s
                """,
                (
                    decision,
                    reason,
                    included_in_price,
                    included_in_shipping,
                    comparable_id,
                ),
            )
            await connection.execute(
                """
                insert into research.comparable_decisions (
                    comparable_evidence_id, decision, reason, decided_by, idempotency_key
                ) values (%s, %s, %s, %s, %s)
                """,
                (comparable_id, decision, reason, actor, idempotency_key),
            )
            await self._append_research_statistics(
                connection, UUID(str(row["research_session_id"]))
            )
            await connection.execute(
                """
                insert into audit.events (
                    actor, action, entity_type, entity_id, after_value
                ) values (%s, %s, 'comparable_evidence', %s, %s)
                """,
                (
                    actor,
                    "comparable_excluded" if exclude else "comparable_restored",
                    str(comparable_id),
                    Jsonb({"decision": decision, "reason": reason}),
                ),
            )
            return context

    @staticmethod
    async def _product_context(
        connection: AsyncConnection[dict[str, Any]], product_id: UUID
    ) -> dict[str, UUID] | None:
        row = await (
            await connection.execute(
                """
                select sp.id as source_product_id, rs.id as research_session_id, rs.run_id
                from catalog.source_product_links spl
                join catalog.source_products sp on sp.id = spl.source_product_id
                join research.sessions rs on rs.canonical_product_id = spl.canonical_product_id
                where spl.canonical_product_id = %s
                order by rs.created_at desc limit 1
                """,
                (product_id,),
            )
        ).fetchone()
        if row is None:
            return None
        return {
            "source_product_id": UUID(str(row["source_product_id"])),
            "research_session_id": UUID(str(row["research_session_id"])),
            "run_id": UUID(str(row["run_id"])),
        }

    @staticmethod
    async def _append_research_statistics(
        connection: AsyncConnection[dict[str, Any]], research_session_id: UUID
    ) -> None:
        rows = await (
            await connection.execute(
                """
                select ml.external_listing_id, ml.displayed_price_jpy,
                       ml.normalized_attributes,
                       ml.estimated_shipping_jpy, ml.shipping_method,
                       ce.included_in_price, ce.included_in_shipping
                from research.comparable_evidence ce
                join research.marketplace_listings ml on ml.id = ce.marketplace_listing_id
                where ce.research_session_id = %s
                """,
                (research_session_id,),
            )
        ).fetchall()
        prices = sorted(
            (str(row["external_listing_id"]), _effective_listing_price(row))
            for row in rows
            if row["included_in_price"]
        )
        amounts = sorted(price for _, price in prices)
        snapshot = json.dumps(prices, separators=(",", ":"), ensure_ascii=False)
        snapshot_hash = hashlib.sha256(snapshot.encode()).hexdigest()
        midpoint = len(amounts) // 2
        lower = amounts[: midpoint + 1] if len(amounts) == 1 else amounts[:midpoint]
        med = _integer_median(amounts)
        dispersion = (
            (max(amounts) - min(amounts)) / med if amounts and med else None
        )
        await connection.execute(
            """
            insert into research.price_statistics (
                research_session_id, evidence_snapshot_hash, included_count,
                median_price_jpy, lower_quartile_price_jpy, minimum_price_jpy,
                maximum_price_jpy, dispersion, sufficient_evidence
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                research_session_id,
                snapshot_hash,
                len(amounts),
                med,
                _integer_median(lower),
                min(amounts) if amounts else None,
                max(amounts) if amounts else None,
                dispersion,
                len(amounts) >= 3,
            ),
        )
        shipping_rows = [row for row in rows if row["included_in_shipping"]]
        shipping_amounts = sorted(
            int(row["estimated_shipping_jpy"])
            for row in shipping_rows
            if row["estimated_shipping_jpy"] is not None
        )
        methods = Counter(
            str(row["shipping_method"])
            for row in shipping_rows
            if row["shipping_method"] is not None
        )
        method = methods.most_common(1)[0][0] if methods else None
        await connection.execute(
            """
            insert into research.shipping_statistics (
                research_session_id, source_type, evidence_count,
                median_shipping_jpy, shipping_method, confidence, reason
            ) values (%s, 'mercari_listing', %s, %s, %s, %s, %s)
            """,
            (
                research_session_id,
                len(shipping_amounts),
                _integer_median(shipping_amounts),
                method,
                min(1, len(shipping_amounts) / 3),
                "recalculated_after_manual_comparable_decision",
            ),
        )

    @staticmethod
    def _candidate_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "product_id": row["canonical_product_id"],
            "source_product_id": row["source_product_id"],
            "name": row.get("display_name") or row.get("source_title") or "名称未確認",
            "source_type": row["source_type"],
            "image_url": row.get("image_url"),
            "sourcing_cost_jpy": row["sourcing_cost_jpy"],
            "estimated_sale_price_jpy": row["estimated_sale_price_jpy"],
            "expected_profit_jpy": row["expected_profit_jpy"],
            "sales_prospect_score": row["sales_prospect_score"],
            "confidence_score": row["confidence_score"],
            "overall_sourcing_score": row["overall_sourcing_score"],
            "recommendation_tier": row["recommendation_tier"],
            "created_at": row["created_at"],
        }
