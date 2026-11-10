import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.domain.inventory import (
    InventoryBalance,
    allocated_purchase_cost,
    charged_amount,
    realised_profit,
)


class PostgresInventoryLearningRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def list_positions(self, limit: int = 100) -> list[dict[str, Any]]:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            rows = await (
                await connection.execute(
                    """
                    select p.*, cp.display_name, cp.category, sp.source_type,
                           image.source_url as image_url,
                           p.purchased_quantity - p.sold_quantity - p.failed_quantity
                               as remaining_quantity
                    from inventory.positions p
                    join catalog.canonical_products cp on cp.id = p.canonical_product_id
                    left join catalog.source_products sp on sp.id = p.source_product_id
                    left join lateral (
                        select source_url from catalog.product_images
                        where source_product_id = p.source_product_id
                        order by image_order limit 1
                    ) image on true
                    order by p.updated_at desc limit %s
                    """,
                    (limit,),
                )
            ).fetchall()
        return [self._position_summary(row) for row in rows]

    async def position_detail(self, position_id: UUID) -> dict[str, Any] | None:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            row = await (
                await connection.execute(
                    """
                    select p.*, cp.display_name, cp.category, cp.brand, cp.model_number,
                           sp.source_type, sp.canonical_url as source_url,
                           image.source_url as image_url,
                           p.purchased_quantity - p.sold_quantity - p.failed_quantity
                               as remaining_quantity
                    from inventory.positions p
                    join catalog.canonical_products cp on cp.id = p.canonical_product_id
                    left join catalog.source_products sp on sp.id = p.source_product_id
                    left join lateral (
                        select source_url from catalog.product_images
                        where source_product_id = p.source_product_id
                        order by image_order limit 1
                    ) image on true
                    where p.id = %s
                    """,
                    (position_id,),
                )
            ).fetchone()
            if row is None:
                return None
            purchases = await self._events(connection, "purchase_events", position_id)
            listings = await self._events(connection, "listing_events", position_id)
            sales = await self._events(connection, "sale_events", position_id)
            outcomes = await self._events(connection, "negative_outcomes", position_id)
            learning_events = [
                dict(item)
                for item in await (
                    await connection.execute(
                        """
                        select id, event_type, payload, created_at
                        from learning.events where inventory_position_id = %s
                        order by created_at desc
                        """,
                        (position_id,),
                    )
                ).fetchall()
            ]
        summary = self._position_summary(row)
        prediction = dict(row["prediction_snapshot"])
        actual_revenue = sum(int(event["sold_price_jpy"]) for event in sales)
        actual_fees = sum(int(event["actual_fee_jpy"]) for event in sales)
        actual_sale_shipping = sum(int(event["actual_shipping_jpy"]) for event in sales)
        predicted_unit_profit = prediction.get("expected_profit_jpy")
        predicted_profit_for_sold = (
            int(predicted_unit_profit) * int(row["sold_quantity"])
            if predicted_unit_profit is not None
            else None
        )
        summary.update(
            {
                "product": {
                    "id": row["canonical_product_id"],
                    "name": row["display_name"] or "名称未確認",
                    "category": row["category"],
                    "brand": row["brand"],
                    "model_number": row["model_number"],
                    "image_url": row["image_url"],
                },
                "source": {
                    "type": row["source_type"],
                    "url": row["source_url"],
                },
                "prediction": prediction,
                "actual": {
                    "purchase_cost_jpy": row["actual_charged_amount_jpy"],
                    "sale_revenue_jpy": actual_revenue,
                    "selling_fees_jpy": actual_fees,
                    "sale_shipping_jpy": actual_sale_shipping,
                    "realised_profit_jpy": row["realised_profit_jpy"],
                },
                "comparison": {
                    "predicted_profit_for_sold_jpy": predicted_profit_for_sold,
                    "actual_profit_for_sold_jpy": row["realised_profit_jpy"],
                    "profit_difference_jpy": (
                        int(row["realised_profit_jpy"]) - predicted_profit_for_sold
                        if predicted_profit_for_sold is not None
                        else None
                    ),
                },
                "purchase_events": purchases,
                "listing_events": listings,
                "sale_events": sales,
                "negative_outcomes": outcomes,
                "learning_events": learning_events,
            }
        )
        return summary

    async def record_purchase(
        self,
        product_id: UUID,
        command: dict[str, Any],
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            await self._claim_command(connection, "purchase", product_id, command, idempotency_key)
            existing = await (
                await connection.execute(
                    """
                    select pd.id, pd.purchased, pe.inventory_position_id
                    from inventory.purchase_decisions pd
                    left join inventory.purchase_events pe
                      on pe.idempotency_key = pd.idempotency_key
                    where pd.idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
            ).fetchone()
            if existing is not None:
                if existing["inventory_position_id"] is None:
                    return {"purchased": False, "decision_id": existing["id"]}
                position_id = UUID(str(existing["inventory_position_id"]))
            else:
                context = await (
                    await connection.execute(
                        """
                        select cp.id as canonical_product_id, r.id as recommendation_id,
                               r.source_product_id, r.input_snapshot,
                               r.estimated_sale_price_jpy, r.estimated_shipping_jpy,
                               r.mercari_fee_jpy, r.sourcing_cost_jpy,
                               r.expected_profit_jpy, r.sales_prospect_score,
                               r.confidence_score, r.overall_sourcing_score,
                               r.recommendation_tier, r.scoring_version
                        from catalog.canonical_products cp
                        left join lateral (
                            select * from recommendation.recommendations
                            where canonical_product_id = cp.id
                            order by created_at desc limit 1
                        ) r on true
                        where cp.id = %s for update of cp
                        """,
                        (product_id,),
                    )
                ).fetchone()
                if context is None:
                    raise KeyError(product_id)
                decision = await (
                    await connection.execute(
                        """
                        insert into inventory.purchase_decisions (
                            canonical_product_id, recommendation_id, purchased, note,
                            decided_by, idempotency_key, decided_at
                        ) values (%s, %s, %s, %s, %s, %s, %s) returning id
                        """,
                        (
                            product_id,
                            context["recommendation_id"],
                            command["purchased"],
                            command.get("note"),
                            actor,
                            idempotency_key,
                            command["purchased_at"],
                        ),
                    )
                ).fetchone()
                if not command["purchased"]:
                    await self._insert_learning_event(
                        connection,
                        "purchase_skipped",
                        actor,
                        product_id=product_id,
                        payload={"note": command.get("note")},
                        reference=("purchase_decision", decision["id"] if decision else None),
                    )
                    await self._audit(
                        connection,
                        actor,
                        "purchase_skipped",
                        product_id,
                        {"note": command.get("note")},
                        entity_type="canonical_product",
                    )
                    return {
                        "purchased": False,
                        "decision_id": decision["id"] if decision else None,
                    }
                if context["recommendation_id"] is None:
                    raise ValueError("a recommendation is required before recording a purchase")
                expected_charge = charged_amount(
                    command["product_amount_jpy"],
                    command["sourcing_shipping_jpy"],
                    command["coupon_jpy"],
                )
                if command["actual_charged_amount_jpy"] != expected_charge:
                    raise ValueError(
                        "actual charged amount must equal product amount plus shipping minus coupon"
                    )
                prediction = {
                    key: context[key]
                    for key in (
                        "recommendation_id",
                        "estimated_sale_price_jpy",
                        "estimated_shipping_jpy",
                        "mercari_fee_jpy",
                        "sourcing_cost_jpy",
                        "expected_profit_jpy",
                        "sales_prospect_score",
                        "confidence_score",
                        "overall_sourcing_score",
                        "recommendation_tier",
                        "scoring_version",
                    )
                }
                prediction["input_snapshot"] = context["input_snapshot"]
                position = await (
                    await connection.execute(
                        """
                        insert into inventory.positions (
                            canonical_product_id, source_product_id, recommendation_id,
                            prediction_snapshot, status, purchased_quantity,
                            actual_charged_amount_jpy, purchase_date
                        ) values (%s, %s, %s, %s, 'purchased', %s, %s, %s) returning id
                        """,
                        (
                            product_id,
                            context["source_product_id"],
                            context["recommendation_id"],
                            Jsonb(self._json_value(prediction)),
                            command["quantity"],
                            command["actual_charged_amount_jpy"],
                            command["purchased_at"].date(),
                        ),
                    )
                ).fetchone()
                assert position is not None
                position_id = UUID(str(position["id"]))
                purchase = await (
                    await connection.execute(
                        """
                        insert into inventory.purchase_events (
                            inventory_position_id, quantity, product_amount_jpy,
                            sourcing_shipping_jpy, coupon_jpy, point_reference_jpy,
                            actual_charged_amount_jpy, purchased_at, note, idempotency_key
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id
                        """,
                        (
                            position_id,
                            command["quantity"],
                            command["product_amount_jpy"],
                            command["sourcing_shipping_jpy"],
                            command["coupon_jpy"],
                            command["point_reference_jpy"],
                            command["actual_charged_amount_jpy"],
                            command["purchased_at"],
                            command.get("note"),
                            idempotency_key,
                        ),
                    )
                ).fetchone()
                await self._insert_learning_event(
                    connection,
                    "purchased",
                    actor,
                    product_id=product_id,
                    position_id=position_id,
                    payload={"quantity": command["quantity"]},
                    reference=("purchase_event", purchase["id"] if purchase else None),
                )
                await self._audit(connection, actor, "product_purchased", position_id, command)
        detail = await self.position_detail(position_id)
        assert detail is not None
        return detail

    async def record_listing(
        self,
        position_id: UUID,
        command: dict[str, Any],
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            await self._claim_command(connection, "listing", position_id, command, idempotency_key)
            existing = await self._event_by_key(connection, "listing_events", idempotency_key)
            if existing is None:
                position = await self._locked_position(connection, position_id)
                balance = self._balance(position)
                balance.require_available(command["quantity"])
                event = await (
                    await connection.execute(
                        """
                        insert into inventory.listing_events (
                            inventory_position_id, marketplace, quantity, listing_price_jpy,
                            listing_url, listed_at, idempotency_key
                        ) values (%s, %s, %s, %s, %s, %s, %s) returning id
                        """,
                        (
                            position_id,
                            command["marketplace"],
                            command["quantity"],
                            command["listing_price_jpy"],
                            command.get("listing_url"),
                            command["listed_at"],
                            idempotency_key,
                        ),
                    )
                ).fetchone()
                if position["status"] == "purchased":
                    await connection.execute(
                        """
                        update inventory.positions
                        set status = 'listed', updated_at = now() where id = %s
                        """,
                        (position_id,),
                    )
                await self._insert_learning_event(
                    connection,
                    "listed",
                    actor,
                    product_id=UUID(str(position["canonical_product_id"])),
                    position_id=position_id,
                    payload=command,
                    reference=("listing_event", event["id"] if event else None),
                )
                await self._audit(connection, actor, "product_listed", position_id, command)
        return await self._required_detail(position_id)

    async def record_sale(
        self,
        position_id: UUID,
        command: dict[str, Any],
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            await self._claim_command(connection, "sale", position_id, command, idempotency_key)
            existing = await self._event_by_key(connection, "sale_events", idempotency_key)
            if existing is None:
                position = await self._locked_position(connection, position_id)
                balance = self._balance(position)
                balance.require_available(command["quantity"])
                allocation = allocated_purchase_cost(
                    int(position["actual_charged_amount_jpy"]),
                    balance.purchased_quantity,
                    balance.sold_quantity,
                    command["quantity"],
                )
                profit = realised_profit(
                    sold_price_jpy=command["sold_price_jpy"],
                    actual_fee_jpy=command["actual_fee_jpy"],
                    actual_shipping_jpy=command["actual_shipping_jpy"],
                    allocated_purchase_cost_jpy=allocation,
                )
                event = await (
                    await connection.execute(
                        """
                        insert into inventory.sale_events (
                            inventory_position_id, quantity, sold_price_jpy, actual_fee_jpy,
                            actual_shipping_jpy, allocated_purchase_cost_jpy,
                            realised_profit_jpy, sold_at, idempotency_key
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id
                        """,
                        (
                            position_id,
                            command["quantity"],
                            command["sold_price_jpy"],
                            command["actual_fee_jpy"],
                            command["actual_shipping_jpy"],
                            allocation,
                            profit,
                            command["sold_at"],
                            idempotency_key,
                        ),
                    )
                ).fetchone()
                sold_after = balance.sold_quantity + command["quantity"]
                remaining_after = balance.purchased_quantity - sold_after - balance.failed_quantity
                await connection.execute(
                    """
                    update inventory.positions
                    set sold_quantity = %s,
                        realised_profit_jpy = realised_profit_jpy + %s,
                        status = %s, updated_at = now()
                    where id = %s
                    """,
                    (
                        sold_after,
                        profit,
                        "sold" if remaining_after == 0 else "partially_sold",
                        position_id,
                    ),
                )
                await self._insert_learning_event(
                    connection,
                    "sold",
                    actor,
                    product_id=UUID(str(position["canonical_product_id"])),
                    position_id=position_id,
                    payload={**command, "realised_profit_jpy": profit},
                    reference=("sale_event", event["id"] if event else None),
                )
                await self._audit(
                    connection,
                    actor,
                    "product_sold",
                    position_id,
                    {**command, "realised_profit_jpy": profit},
                )
        return await self._required_detail(position_id)

    async def record_negative_outcome(
        self,
        position_id: UUID,
        command: dict[str, Any],
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            await self._claim_command(
                connection, "negative_outcome", position_id, command, idempotency_key
            )
            existing = await self._event_by_key(connection, "negative_outcomes", idempotency_key)
            if existing is None:
                position = await self._locked_position(connection, position_id)
                balance = self._balance(position)
                balance.require_available(command["quantity"])
                event = await (
                    await connection.execute(
                        """
                        insert into inventory.negative_outcomes (
                            inventory_position_id, outcome_type, quantity, occurred_at,
                            note, idempotency_key
                        ) values (%s, %s, %s, %s, %s, %s) returning id
                        """,
                        (
                            position_id,
                            command["outcome_type"],
                            command["quantity"],
                            command["occurred_at"],
                            command.get("note"),
                            idempotency_key,
                        ),
                    )
                ).fetchone()
                failed_after = balance.failed_quantity + command["quantity"]
                remaining_after = balance.purchased_quantity - balance.sold_quantity - failed_after
                outcome_status = (
                    "other_failure"
                    if command["outcome_type"] == "other"
                    else command["outcome_type"]
                )
                await connection.execute(
                    """
                    update inventory.positions
                    set failed_quantity = %s,
                        status = case when %s = 0 then %s else status end,
                        updated_at = now()
                    where id = %s
                    """,
                    (failed_after, remaining_after, outcome_status, position_id),
                )
                await self._insert_learning_event(
                    connection,
                    command["outcome_type"],
                    actor,
                    product_id=UUID(str(position["canonical_product_id"])),
                    position_id=position_id,
                    payload=command,
                    reference=("negative_outcome", event["id"] if event else None),
                )
                await self._audit(
                    connection, actor, "negative_outcome_recorded", position_id, command
                )
        return await self._required_detail(position_id)

    async def record_preference(
        self,
        product_id: UUID,
        signal: str,
        note: str | None,
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._record_signal(
            "user_preference_signals",
            "user_appeal_feedback",
            product_id,
            signal,
            note,
            actor,
            idempotency_key,
        )

    async def record_research_value(
        self,
        product_id: UUID,
        signal: str,
        note: str | None,
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._record_signal(
            "research_value_signals",
            "research_value_feedback",
            product_id,
            signal,
            note,
            actor,
            idempotency_key,
        )

    async def list_hypotheses(self) -> list[dict[str, Any]]:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            rows = await (
                await connection.execute(
                    """
                    select h.*, p.code as pattern_code, p.name as pattern_name,
                           count(e.id) filter (where e.direction = 'supporting')
                               as supporting_count,
                           count(e.id) filter (where e.direction = 'contradictory')
                               as contradictory_count
                    from learning.profit_hypotheses h
                    left join learning.profit_patterns p on p.id = h.pattern_id
                    left join learning.hypothesis_evidence e on e.hypothesis_id = h.id
                    group by h.id, p.code, p.name order by h.created_at
                    """
                )
            ).fetchall()
        return [dict(row) for row in rows]

    async def hypothesis_detail(self, hypothesis_id: UUID) -> dict[str, Any] | None:
        async with await AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            row = await (
                await connection.execute(
                    """
                    select h.*, p.code as pattern_code, p.name as pattern_name
                    from learning.profit_hypotheses h
                    left join learning.profit_patterns p on p.id = h.pattern_id
                    where h.id = %s
                    """,
                    (hypothesis_id,),
                )
            ).fetchone()
            if row is None:
                return None
            evidence = [
                dict(item)
                for item in await (
                    await connection.execute(
                        """
                        select * from learning.hypothesis_evidence
                        where hypothesis_id = %s order by created_at desc
                        """,
                        (hypothesis_id,),
                    )
                ).fetchall()
            ]
        return {**dict(row), "evidence": evidence}

    async def add_hypothesis_evidence(
        self,
        hypothesis_id: UUID,
        command: dict[str, Any],
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            replayed = await self._claim_command(
                connection, "hypothesis_evidence", hypothesis_id, command, idempotency_key
            )
            hypothesis = await (
                await connection.execute(
                    "select id from learning.profit_hypotheses where id = %s",
                    (hypothesis_id,),
                )
            ).fetchone()
            if hypothesis is None:
                raise KeyError(hypothesis_id)
            if not replayed:
                event = await (
                    await connection.execute(
                        """
                    insert into learning.hypothesis_evidence (
                        hypothesis_id, evidence_type, direction, strength,
                        source_reference_type, source_reference_id, summary, idempotency_key
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    returning id
                    """,
                        (
                            hypothesis_id,
                            command["evidence_type"],
                            command["direction"],
                            command["strength"],
                            command["source_reference_type"],
                            command.get("source_reference_id"),
                            command["summary"],
                            idempotency_key,
                        ),
                    )
                ).fetchone()
                await self._insert_learning_event(
                    connection,
                    "hypothesis_evidence_added",
                    actor,
                    payload={**command, "hypothesis_id": hypothesis_id},
                    reference=("hypothesis_evidence", event["id"] if event else None),
                )
                await self._audit(
                    connection,
                    actor,
                    "hypothesis_evidence_added",
                    hypothesis_id,
                    command,
                    entity_type="profit_hypothesis",
                )
        detail = await self.hypothesis_detail(hypothesis_id)
        assert detail is not None
        return detail

    async def _record_signal(
        self,
        table: str,
        event_type: str,
        product_id: UUID,
        signal: str,
        note: str | None,
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        async with (
            await AsyncConnection.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            await self._claim_command(
                connection,
                event_type,
                product_id,
                {"signal": signal, "note": note},
                idempotency_key,
            )
            product = await (
                await connection.execute(
                    "select id from catalog.canonical_products where id = %s",
                    (product_id,),
                )
            ).fetchone()
            if product is None:
                raise KeyError(product_id)
            existing = await (
                await connection.execute(
                    f"select * from learning.{table} where idempotency_key = %s",
                    (idempotency_key,),
                )
            ).fetchone()
            if existing is None:
                existing = await (
                    await connection.execute(
                        f"""
                        insert into learning.{table} (
                            canonical_product_id, signal, note, recorded_by, idempotency_key
                        ) values (%s, %s, %s, %s, %s) returning *
                        """,
                        (product_id, signal, note, actor, idempotency_key),
                    )
                ).fetchone()
                await self._insert_learning_event(
                    connection,
                    event_type,
                    actor,
                    product_id=product_id,
                    payload={"signal": signal, "note": note},
                    reference=(event_type, existing["id"] if existing else None),
                )
                await self._audit(
                    connection,
                    actor,
                    event_type,
                    product_id,
                    {"signal": signal, "note": note},
                    entity_type="canonical_product",
                )
        assert existing is not None
        return dict(existing)

    async def _required_detail(self, position_id: UUID) -> dict[str, Any]:
        detail = await self.position_detail(position_id)
        if detail is None:
            raise KeyError(position_id)
        return detail

    @staticmethod
    async def _claim_command(
        connection: AsyncConnection[dict[str, Any]],
        action: str,
        target_id: UUID,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> bool:
        canonical_payload = PostgresInventoryLearningRepository._json_value(payload)
        payload_hash = hashlib.sha256(
            json.dumps(
                canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        inserted = await (
            await connection.execute(
                """
                insert into audit.command_requests (
                    idempotency_key, action, target_id, payload_hash
                ) values (%s, %s, %s, %s)
                on conflict (idempotency_key) do nothing
                returning idempotency_key
                """,
                (idempotency_key, action, target_id, payload_hash),
            )
        ).fetchone()
        if inserted is not None:
            return False
        existing = await (
            await connection.execute(
                """
                select action, target_id, payload_hash from audit.command_requests
                where idempotency_key = %s
                """,
                (idempotency_key,),
            )
        ).fetchone()
        if existing is None or (
            existing["action"] != action
            or existing["target_id"] != target_id
            or existing["payload_hash"] != payload_hash
        ):
            raise ValueError("idempotency key was already used for a different command")
        return True

    @staticmethod
    async def _events(
        connection: AsyncConnection[dict[str, Any]], table: str, position_id: UUID
    ) -> list[dict[str, Any]]:
        rows = await (
            await connection.execute(
                f"select * from inventory.{table} where inventory_position_id = %s "
                "order by created_at desc",
                (position_id,),
            )
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    async def _event_by_key(
        connection: AsyncConnection[dict[str, Any]], table: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        row = await (
            await connection.execute(
                f"select * from inventory.{table} where idempotency_key = %s",
                (idempotency_key,),
            )
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    async def _locked_position(
        connection: AsyncConnection[dict[str, Any]], position_id: UUID
    ) -> dict[str, Any]:
        row = await (
            await connection.execute(
                "select * from inventory.positions where id = %s for update",
                (position_id,),
            )
        ).fetchone()
        if row is None:
            raise KeyError(position_id)
        return dict(row)

    @staticmethod
    def _balance(position: dict[str, Any]) -> InventoryBalance:
        return InventoryBalance(
            int(position["purchased_quantity"]),
            int(position["sold_quantity"]),
            int(position["failed_quantity"]),
        )

    @staticmethod
    async def _insert_learning_event(
        connection: AsyncConnection[dict[str, Any]],
        event_type: str,
        actor: str,
        *,
        product_id: UUID | None = None,
        position_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
        reference: tuple[str, object | None] | None = None,
    ) -> None:
        await connection.execute(
            """
            insert into learning.events (
                event_type, canonical_product_id, inventory_position_id, actor,
                payload, source_reference_type, source_reference_id
            ) values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_type,
                product_id,
                position_id,
                actor,
                Jsonb(PostgresInventoryLearningRepository._json_value(payload or {})),
                reference[0] if reference else None,
                reference[1] if reference else None,
            ),
        )

    @staticmethod
    async def _audit(
        connection: AsyncConnection[dict[str, Any]],
        actor: str,
        action: str,
        entity_id: UUID,
        value: dict[str, Any],
        *,
        entity_type: str = "inventory_position",
    ) -> None:
        await connection.execute(
            """
            insert into audit.events (actor, action, entity_type, entity_id, after_value)
            values (%s, %s, %s, %s, %s)
            """,
            (
                actor,
                action,
                entity_type,
                str(entity_id),
                Jsonb(PostgresInventoryLearningRepository._json_value(value)),
            ),
        )

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, datetime | date):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {
                str(key): PostgresInventoryLearningRepository._json_value(item)
                for key, item in value.items()
            }
        if isinstance(value, list | tuple):
            return [PostgresInventoryLearningRepository._json_value(item) for item in value]
        return value

    @staticmethod
    def _position_summary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "canonical_product_id": row["canonical_product_id"],
            "name": row.get("display_name") or "名称未確認",
            "category": row.get("category"),
            "source_type": row.get("source_type"),
            "image_url": row.get("image_url"),
            "status": row["status"],
            "purchased_quantity": row["purchased_quantity"],
            "sold_quantity": row["sold_quantity"],
            "failed_quantity": row["failed_quantity"],
            "remaining_quantity": row["remaining_quantity"],
            "actual_charged_amount_jpy": row["actual_charged_amount_jpy"],
            "realised_profit_jpy": row["realised_profit_jpy"],
            "purchase_date": row["purchase_date"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
