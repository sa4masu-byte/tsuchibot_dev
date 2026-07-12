from datetime import datetime
from typing import cast
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.application.catalog import observation_idempotency_key
from backend.app.domain.catalog import (
    Availability,
    ChangeKind,
    NormalizedSourceProduct,
    ProductChange,
    SourceProductState,
)


class PostgresCatalogRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def get_state(self, source_type: str, source_item_id: str) -> SourceProductState | None:
        async with await AsyncConnection.connect(
            self._database_url,
            row_factory=dict_row,
        ) as connection:
            row = await connection.execute(
                """
                select source_type, source_item_id, canonical_url,
                       current_price_jpy, current_availability
                from catalog.source_products
                where source_type = %s and source_item_id = %s
                """,
                (source_type, source_item_id),
            )
            result = await row.fetchone()
        if result is None:
            return None
        return SourceProductState(
            source_type=result["source_type"],
            source_item_id=result["source_item_id"],
            canonical_url=result["canonical_url"],
            current_price_jpy=result["current_price_jpy"],
            current_availability=Availability(result["current_availability"]),
        )

    async def append_observation(
        self,
        product: NormalizedSourceProduct,
        run_id: UUID,
        observed_at: datetime,
        change: ProductChange,
    ) -> bool:
        key = observation_idempotency_key(product, run_id, observed_at)
        async with (
            await AsyncConnection.connect(self._database_url) as connection,
            connection.transaction(),
        ):
            product_id = await self._upsert_identity(connection, product, observed_at)
            observation = await connection.execute(
                """
                    insert into catalog.source_observations (
                        source_product_id, run_id, observed_at, title, displayed_category,
                        displayed_price_jpy, availability, listing_timestamp, raw_metadata,
                        parser_version, idempotency_key
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (idempotency_key) do nothing
                    returning id
                    """,
                (
                    product_id,
                    run_id,
                    observed_at,
                    product.title,
                    product.category,
                    product.displayed_price_jpy,
                    product.availability.value,
                    product.listing_timestamp,
                    Jsonb(product.raw_metadata),
                    product.parser_version,
                    key,
                ),
            )
            if await observation.fetchone() is None:
                return False
            await self._append_histories(connection, product_id, run_id, observed_at, change)
            await self._upsert_images(connection, product_id, product, observed_at)
            await connection.execute(
                """
                    update catalog.source_products
                    set canonical_url = %s, parser_version = %s, last_seen_at = %s,
                        current_availability = %s, current_price_jpy = %s, updated_at = now()
                    where id = %s
                    """,
                (
                    product.canonical_url,
                    product.parser_version,
                    observed_at,
                    product.availability.value,
                    product.displayed_price_jpy,
                    product_id,
                ),
            )
        return True

    async def _upsert_identity(
        self,
        connection: AsyncConnection[tuple[object, ...]],
        product: NormalizedSourceProduct,
        observed_at: datetime,
    ) -> UUID:
        cursor = await connection.execute(
            """
            insert into catalog.source_products (
                source_type, source_location_id, source_item_id, canonical_url, parser_version,
                first_seen_at, last_seen_at, current_availability, current_price_jpy
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (source_type, source_item_id) do update
                set last_seen_at = greatest(
                    catalog.source_products.last_seen_at,
                    excluded.last_seen_at
                )
            returning id
            """,
            (
                product.source_type,
                product.source_location_id,
                product.source_item_id,
                product.canonical_url,
                product.parser_version,
                observed_at,
                observed_at,
                product.availability.value,
                product.displayed_price_jpy,
            ),
        )
        row = await cursor.fetchone()
        assert row is not None
        return cast(UUID, row[0])

    async def _append_histories(
        self,
        connection: AsyncConnection[tuple[object, ...]],
        product_id: UUID,
        run_id: UUID,
        observed_at: datetime,
        change: ProductChange,
    ) -> None:
        current_price = change.current_price_jpy
        previous_price = change.previous_price_jpy
        if (
            change.kind
            in {
                ChangeKind.NEW,
                ChangeKind.PRICE_CHANGED,
                ChangeKind.PRICE_AND_AVAILABILITY_CHANGED,
            }
            and current_price is not None
        ):
            rate = None
            if previous_price is not None and previous_price != 0:
                rate = (current_price - previous_price) / previous_price
            await connection.execute(
                """
                insert into catalog.price_observations (
                    source_product_id, run_id, amount_jpy, observed_at,
                    change_from_previous_jpy, change_rate
                ) values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    product_id,
                    run_id,
                    current_price,
                    observed_at,
                    change.price_delta_jpy,
                    rate,
                ),
            )
        if change.kind in {
            ChangeKind.NEW,
            ChangeKind.AVAILABILITY_CHANGED,
            ChangeKind.PRICE_AND_AVAILABILITY_CHANGED,
        }:
            await connection.execute(
                """
                insert into catalog.availability_observations (
                    source_product_id, run_id, availability, observed_at
                ) values (%s, %s, %s, %s)
                """,
                (product_id, run_id, change.current_availability.value, observed_at),
            )

    async def _upsert_images(
        self,
        connection: AsyncConnection[tuple[object, ...]],
        product_id: UUID,
        product: NormalizedSourceProduct,
        observed_at: datetime,
    ) -> None:
        for image_order, image_url in enumerate(product.image_urls):
            await connection.execute(
                """
                insert into catalog.product_images (
                    source_product_id, source_url, image_order, first_seen_at
                ) values (%s, %s, %s, %s)
                on conflict (source_product_id, source_url) do nothing
                """,
                (product_id, image_url, image_order, observed_at),
            )
