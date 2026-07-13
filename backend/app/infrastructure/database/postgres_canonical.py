from uuid import UUID

from psycopg import AsyncConnection

from backend.app.domain.research import ResearchTarget


class PostgresCanonicalProductRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def ensure_for_source(
        self,
        source_product_id: UUID,
        target: ResearchTarget,
    ) -> UUID:
        async with (
            await AsyncConnection.connect(self._database_url) as connection,
            connection.transaction(),
        ):
            source_cursor = await connection.execute(
                "select id from catalog.source_products where id = %s for update",
                (source_product_id,),
            )
            if await source_cursor.fetchone() is None:
                raise KeyError(f"source product not found: {source_product_id}")
            existing_cursor = await connection.execute(
                """
                select canonical_product_id
                from catalog.source_product_links
                where source_product_id = %s
                order by created_at
                limit 1
                """,
                (source_product_id,),
            )
            existing = await existing_cursor.fetchone()
            if existing is not None:
                return UUID(str(existing[0]))

            canonical_cursor = await connection.execute(
                """
                insert into catalog.canonical_products (
                    display_name, category, manufacturer, brand, model_number, condition
                ) values (%s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    target.source_title,
                    target.category,
                    target.manufacturer,
                    target.brand,
                    target.model_numbers[0] if target.model_numbers else None,
                    target.condition,
                ),
            )
            canonical = await canonical_cursor.fetchone()
            if canonical is None:
                raise RuntimeError("canonical product insert did not return an ID")
            canonical_id = UUID(str(canonical[0]))
            await connection.execute(
                """
                insert into catalog.source_product_links (
                    source_product_id, canonical_product_id, link_type, confidence, created_by
                ) values (%s, %s, 'manual_research', 1, 'manual_research')
                """,
                (source_product_id, canonical_id),
            )
            return canonical_id
