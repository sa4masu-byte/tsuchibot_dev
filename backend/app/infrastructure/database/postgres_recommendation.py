from dataclasses import asdict, dataclass
from decimal import Decimal
from statistics import median
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.application.recommendation import RecommendationRecord
from backend.app.domain.catalog import ProductAnalysis
from backend.app.domain.catalog.analysis import SizeClass
from backend.app.domain.recommendation import RecommendationInput, RecommendationPolicy


@dataclass(frozen=True, slots=True)
class RecommendationCandidate:
    canonical_product_id: UUID
    source_product_id: UUID
    research_session_id: UUID
    run_id: UUID
    inputs: RecommendationInput
    policy: RecommendationPolicy


def _median(values: list[int]) -> int | None:
    return round(float(median(values))) if values else None


def _metadata_integer(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _metadata_score(metadata: dict[str, Any], key: str) -> float | None:
    value = metadata.get(key)
    if (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and 0 <= value <= 100
    ):
        return float(value)
    return None


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


def _known_identity_confidence(analysis: ProductAnalysis | None) -> float:
    if analysis is None:
        return 0
    values = [
        field.confidence
        for field in (analysis.category, analysis.manufacturer, analysis.brand)
        if field.value is not None
    ]
    return sum(values) / len(values) if values else 0


def _policy_from_payload(version: str, payload: dict[str, Any]) -> RecommendationPolicy:
    fee = payload["fee"]
    shipping = payload["shipping"]
    scoring = payload["scoring"]
    thresholds = payload["thresholds"]
    mapping = shipping["standard_by_method"]
    if not all(isinstance(item, int) for item in mapping.values()):
        raise ValueError("shipping configuration values must be integer yen")
    return RecommendationPolicy(
        config_version=version,
        fee_rule_version=str(fee["version"]),
        fee_rate_basis_points=int(fee["rate_basis_points"]),
        shipping_rule_version=str(shipping["version"]),
        standard_shipping_by_method=tuple(
            sorted((str(name), int(amount)) for name, amount in mapping.items())
        ),
        scoring_version=str(scoring["version"]),
        threshold_version=str(thresholds["version"]),
        minimum_candidate_profit_jpy=int(thresholds["minimum_candidate_profit_jpy"]),
        recommended_profit_jpy=int(thresholds["recommended_profit_jpy"]),
        strong_profit_jpy=int(thresholds["strong_profit_jpy"]),
        sales_prospect_threshold=int(thresholds["sales_prospect_threshold"]),
        recommended_confidence_threshold=int(
            thresholds["recommended_confidence_threshold"]
        ),
        strong_confidence_threshold=int(thresholds["strong_confidence_threshold"]),
        strong_return_on_cost=Decimal(str(thresholds["strong_return_on_cost"])),
        maximum_sold_volume=int(scoring["maximum_sold_volume"]),
    )


class PostgresRecommendationCandidateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def get(
        self,
        source_product_id: UUID,
        run_id: UUID,
        research_session_id: UUID | None = None,
    ) -> RecommendationCandidate | None:
        async with await AsyncConnection.connect(
            self._database_url,
            row_factory=dict_row,
        ) as connection:
            base = await self._load_base(
                connection,
                source_product_id,
                run_id,
                research_session_id,
            )
            if base is None:
                return None
            evidence = await self._load_evidence(
                connection,
                UUID(str(base["session_id"])),
                base["evidence_period_start"],
                base["evidence_period_end"],
            )
            policy_row = await (
                await connection.execute(
                    """
                    select version, payload
                    from config.versions
                    where config_type = 'recommendation' and active
                    order by created_at desc
                    limit 1
                    """
                )
            ).fetchone()
            correction_rows = await (
                await connection.execute(
                    """
                    select field_name, corrected_value
                    from catalog.product_corrections
                    where canonical_product_id = %s and is_active
                    """,
                    (base["canonical_product_id"],),
                )
            ).fetchall()
        if policy_row is None:
            raise RuntimeError("active recommendation configuration was not found")
        corrections = {
            str(row["field_name"]): row["corrected_value"] for row in correction_rows
        }
        source_metadata = dict(base["source_raw_metadata"] or {})

        analysis_payload = base["parsed_result"]
        analysis = (
            ProductAnalysis.model_validate(analysis_payload)
            if analysis_payload is not None
            else None
        )
        identity_confidence = _known_identity_confidence(analysis)
        model_confidence = (
            max(
                (candidate.confidence for candidate in analysis.model_number_candidates),
                default=0,
            )
            if analysis is not None
            else 0
        )
        condition_confidence = analysis.condition.confidence if analysis is not None else 0
        if {"display_name", "category", "manufacturer", "brand"} & corrections.keys():
            identity_confidence = 1
        if "model_number" in corrections:
            model_confidence = 1
        if "condition" in corrections:
            condition_confidence = 1
        branded_or_character = bool(
            analysis
            and (analysis.brand.value is not None or analysis.character.value is not None)
        )
        authenticity_supported = source_metadata.get("authenticity_supported") is True
        authenticity_confidence = 0 if branded_or_character and not authenticity_supported else 1
        risks: list[str] = []
        if branded_or_character and not authenticity_supported:
            risks.append("authenticity_unconfirmed")
        if analysis is not None and analysis.size_class.value is SizeClass.OVERSIZED:
            risks.append("oversized_shipping")

        sold_prices = evidence["sold_prices"]
        active_prices = evidence["active_prices"]
        estimated_sale_price = corrections.get(
            "estimated_sale_price_jpy", base["median_price_jpy"]
        )
        active_median = _median(active_prices)
        price_competitiveness = None
        if estimated_sale_price and active_median is not None:
            price_competitiveness = min(1, active_median / int(estimated_sale_price))

        shipping_values = evidence["shipping_values"]
        same_shipping = [
            amount
            for amount, model_similarity in shipping_values
            if model_similarity is not None and model_similarity >= 0.99
        ]
        all_shipping = [amount for amount, _ in shipping_values]
        corrected_shipping = corrections.get("estimated_shipping_jpy")
        same_shipping_median = _median(same_shipping)
        same_shipping_count = len(same_shipping)
        shipping_confidence = float(base["shipping_confidence"] or 0)
        if corrected_shipping is not None:
            same_shipping_median = int(corrected_shipping)
            same_shipping_count = 1
            shipping_confidence = 1
        policy = _policy_from_payload(
            str(policy_row["version"]),
            dict(policy_row["payload"]),
        )
        inputs = RecommendationInput(
            sourcing_price_jpy=(
                int(base["current_price_jpy"])
                if base["current_price_jpy"] is not None
                else None
            ),
            sourcing_shipping_jpy=_metadata_integer(
                source_metadata, "sourcing_shipping_jpy"
            ),
            definite_coupon_jpy=_metadata_integer(
                source_metadata, "definite_coupon_jpy"
            ),
            estimated_sale_price_jpy=(
                int(estimated_sale_price) if estimated_sale_price is not None else None
            ),
            same_product_shipping_median_jpy=same_shipping_median,
            same_product_shipping_count=same_shipping_count,
            similar_product_shipping_median_jpy=_median(all_shipping),
            similar_product_shipping_count=len(all_shipping),
            shipping_method=(
                str(base["shipping_method"]) if base["shipping_method"] else None
            ),
            shipping_evidence_confidence=shipping_confidence,
            sold_count=len(sold_prices),
            active_count=len(active_prices),
            included_sold_comparable_count=int(base["included_count"]),
            sufficient_comparables=bool(base["sufficient_evidence"]),
            average_comparable_similarity=evidence["average_similarity"],
            price_dispersion=(
                float(base["dispersion"]) if base["dispersion"] is not None else None
            ),
            product_identity_confidence=identity_confidence,
            model_number_confidence=model_confidence,
            condition_confidence=condition_confidence,
            authenticity_confidence=authenticity_confidence,
            price_competitiveness=price_competitiveness,
            ec_delivery_score=_metadata_score(source_metadata, "ec_delivery_score"),
            major_risks=tuple(risks),
            research_evidence_snapshot_hash=str(base["evidence_snapshot_hash"]),
        )
        return RecommendationCandidate(
            canonical_product_id=UUID(str(base["canonical_product_id"])),
            source_product_id=source_product_id,
            research_session_id=UUID(str(base["session_id"])),
            run_id=run_id,
            inputs=inputs,
            policy=policy,
        )

    @staticmethod
    async def _load_base(
        connection: AsyncConnection[dict[str, Any]],
        source_product_id: UUID,
        run_id: UUID,
        research_session_id: UUID | None,
    ) -> dict[str, Any] | None:
        cursor = await connection.execute(
            """
            select
                rs.id as session_id,
                rs.canonical_product_id,
                rs.evidence_period_start,
                rs.evidence_period_end,
                sp.current_price_jpy,
                ps.included_count,
                ps.median_price_jpy,
                ps.dispersion,
                ps.sufficient_evidence,
                ps.evidence_snapshot_hash,
                ss.shipping_method,
                ss.confidence as shipping_confidence,
                analysis.parsed_result
                , observation.raw_metadata as source_raw_metadata
            from catalog.source_products sp
            join catalog.source_product_links spl on spl.source_product_id = sp.id
            join research.sessions rs on rs.canonical_product_id = spl.canonical_product_id
            join lateral (
                select * from research.price_statistics
                where research_session_id = rs.id
                order by created_at desc limit 1
            ) ps on true
            join lateral (
                select * from research.shipping_statistics
                where research_session_id = rs.id
                order by created_at desc limit 1
            ) ss on true
            left join lateral (
                select parsed_result
                from catalog.ai_product_analyses
                where source_product_id = sp.id
                  and analysis_status = 'completed'
                  and validation_status = 'valid'
                order by created_at desc limit 1
            ) analysis on true
            left join lateral (
                select raw_metadata
                from catalog.source_observations
                where source_product_id = sp.id
                order by observed_at desc limit 1
            ) observation on true
            where sp.id = %s
              and rs.run_id = %s
              and (%s::uuid is null or rs.id = %s::uuid)
            order by rs.created_at desc
            limit 1
            """,
            (source_product_id, run_id, research_session_id, research_session_id),
        )
        return await cursor.fetchone()

    @staticmethod
    async def _load_evidence(
        connection: AsyncConnection[dict[str, Any]],
        research_session_id: UUID,
        evidence_period_start: Any,
        evidence_period_end: Any,
    ) -> dict[str, Any]:
        cursor = await connection.execute(
            """
            select
                ml.status,
                ml.displayed_price_jpy,
                ml.normalized_attributes,
                ml.estimated_shipping_jpy,
                ml.sold_at,
                ml.listed_at,
                ce.model_similarity,
                ce.total_similarity,
                ce.current_decision,
                ce.included_in_shipping
            from research.comparable_evidence ce
            join research.marketplace_listings ml on ml.id = ce.marketplace_listing_id
            where ce.research_session_id = %s
            """,
            (research_session_id,),
        )
        rows = await cursor.fetchall()
        sold_prices = [
            _effective_listing_price(row)
            for row in rows
            if row["status"] == "sold"
            and (row["sold_at"] is not None or row["listed_at"] is not None)
            and evidence_period_start
            <= (row["sold_at"] or row["listed_at"]).date()
            <= evidence_period_end
            and row["current_decision"] != "exclude"
        ]
        active_prices = [
            _effective_listing_price(row)
            for row in rows
            if row["status"] == "active" and row["current_decision"] != "exclude"
        ]
        similarities = [
            float(row["total_similarity"])
            for row in rows
            if row["current_decision"] != "exclude"
        ]
        shipping_values = [
            (int(row["estimated_shipping_jpy"]), row["model_similarity"])
            for row in rows
            if row["included_in_shipping"]
            and row["estimated_shipping_jpy"] is not None
        ]
        return {
            "sold_prices": sold_prices,
            "active_prices": active_prices,
            "average_similarity": (
                sum(similarities) / len(similarities) if similarities else None
            ),
            "shipping_values": shipping_values,
        }


class PostgresRecommendationRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def save(self, recommendation: RecommendationRecord) -> UUID:
        request = recommendation.request
        result = recommendation.result
        input_snapshot = asdict(request.inputs)
        input_snapshot["major_risks"] = list(request.inputs.major_risks)
        async with (
            await AsyncConnection.connect(self._database_url) as connection,
            connection.transaction(),
        ):
            cursor = await connection.execute(
                """
                insert into recommendation.recommendations (
                    id, canonical_product_id, source_product_id, research_session_id,
                    run_id, input_snapshot, estimated_sale_price_jpy,
                    estimated_shipping_jpy, mercari_fee_jpy, sourcing_cost_jpy,
                    expected_profit_jpy, return_on_cost, sales_margin,
                    sales_prospect_score, confidence_score, overall_sourcing_score,
                    recommendation_tier, config_version, fee_rule_version,
                    shipping_rule_version, scoring_version, threshold_version,
                    evidence_snapshot_hash, created_at
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                on conflict (source_product_id, evidence_snapshot_hash, scoring_version)
                do nothing
                returning id
                """,
                (
                    recommendation.id,
                    request.canonical_product_id,
                    request.source_product_id,
                    request.research_session_id,
                    request.run_id,
                    Jsonb(input_snapshot),
                    result.estimated_sale_price_jpy,
                    result.shipping.amount_jpy,
                    result.mercari_fee_jpy,
                    result.sourcing_cost_jpy,
                    result.expected_profit_jpy,
                    result.return_on_cost,
                    result.sales_margin,
                    result.sales_prospect_score,
                    result.confidence_score,
                    result.overall_sourcing_score,
                    result.tier.value,
                    result.policy.config_version,
                    result.policy.fee_rule_version,
                    result.policy.shipping_rule_version,
                    result.policy.scoring_version,
                    result.policy.threshold_version,
                    recommendation.evidence_snapshot_hash,
                    request.calculated_at,
                ),
            )
            row = await cursor.fetchone()
            if row is None:
                existing = await (
                    await connection.execute(
                        """
                        select id from recommendation.recommendations
                        where source_product_id = %s
                          and evidence_snapshot_hash = %s
                          and scoring_version = %s
                        """,
                        (
                            request.source_product_id,
                            recommendation.evidence_snapshot_hash,
                            result.policy.scoring_version,
                        ),
                    )
                ).fetchone()
                if existing is None:
                    raise RuntimeError("recommendation insert conflict could not be resolved")
                return UUID(str(existing[0]))
            for order, reason in enumerate(result.reasons, start=1):
                await connection.execute(
                    """
                    insert into recommendation.reason_components (
                        recommendation_id, code, label, component_type, value,
                        score_delta, source, display_order
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        recommendation.id,
                        reason.code,
                        reason.label,
                        reason.component_type.value,
                        Jsonb(reason.value),
                        reason.score_delta,
                        reason.source,
                        order,
                    ),
                )
            for quantity in result.quantities:
                await connection.execute(
                    """
                    insert into recommendation.quantity_evaluations (
                        recommendation_id, quantity, total_sourcing_cost_jpy,
                        total_expected_profit_jpy, per_unit_profit_jpy
                    ) values (%s, %s, %s, %s, %s)
                    """,
                    (
                        recommendation.id,
                        quantity.quantity,
                        quantity.total_sourcing_cost_jpy,
                        quantity.total_expected_profit_jpy,
                        quantity.per_unit_profit_jpy,
                    ),
                )
            await connection.execute(
                """
                insert into runs.metrics (run_id, metric_code, value, dimensions)
                values (%s, 'recommendation_calculated', 1, %s)
                """,
                (request.run_id, Jsonb({"tier": result.tier.value})),
            )
            await connection.execute(
                """
                insert into audit.events (
                    actor, action, entity_type, entity_id, after_value, metadata
                ) values ('deterministic-worker', 'recommendation_calculated',
                          'recommendation', %s, %s, %s)
                """,
                (
                    str(recommendation.id),
                    Jsonb({"tier": result.tier.value}),
                    Jsonb({"scoring_version": result.policy.scoring_version}),
                ),
            )
            return recommendation.id
