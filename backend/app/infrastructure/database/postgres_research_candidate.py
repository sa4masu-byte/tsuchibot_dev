from dataclasses import dataclass
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from backend.app.domain.catalog import ProductAnalysis
from backend.app.domain.research import ModelIdentityCandidate, ResearchTarget


@dataclass(frozen=True, slots=True)
class ProductResearchCandidate:
    source_product_id: UUID
    target: ResearchTarget
    model_candidates: tuple[ModelIdentityCandidate, ...]
    image_urls: tuple[str, ...]


class PostgresResearchCandidateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def get(self, source_product_id: UUID) -> ProductResearchCandidate | None:
        async with await AsyncConnection.connect(
            self._database_url,
            row_factory=dict_row,
        ) as connection:
            cursor = await connection.execute(
                """
                select
                    sp.id,
                    sp.source_item_id,
                    observation.title,
                    observation.displayed_category,
                    analysis.parsed_result
                from catalog.source_products sp
                left join lateral (
                    select title, displayed_category
                    from catalog.source_observations
                    where source_product_id = sp.id
                    order by observed_at desc
                    limit 1
                ) observation on true
                left join lateral (
                    select parsed_result
                    from catalog.ai_product_analyses
                    where source_product_id = sp.id
                      and analysis_status = 'completed'
                      and validation_status = 'valid'
                      and parsed_result is not null
                    order by created_at desc
                    limit 1
                ) analysis on true
                where sp.id = %s
                """,
                (source_product_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            image_cursor = await connection.execute(
                """
                select source_url
                from catalog.product_images
                where source_product_id = %s
                order by image_order
                limit 5
                """,
                (source_product_id,),
            )
            image_rows = await image_cursor.fetchall()

        analysis_payload = row["parsed_result"]
        analysis = (
            ProductAnalysis.model_validate(analysis_payload)
            if analysis_payload is not None
            else None
        )
        title = str(row["title"] or row["source_item_id"])
        displayed_category = (
            str(row["displayed_category"]) if row["displayed_category"] else None
        )
        if analysis is None:
            target = ResearchTarget(source_title=title, category=displayed_category)
            model_candidates: tuple[ModelIdentityCandidate, ...] = ()
        else:
            category = analysis.category.value or displayed_category
            model_candidates = tuple(
                ModelIdentityCandidate(
                    value=candidate.value,
                    confidence=candidate.confidence,
                    evidence=(candidate.evidence,),
                    sources=("gemini",),
                )
                for candidate in sorted(
                    analysis.model_number_candidates,
                    key=lambda item: -item.confidence,
                )
            )
            target = ResearchTarget(
                source_title=title,
                category=category,
                manufacturer=analysis.manufacturer.value,
                brand=analysis.brand.value,
                model_numbers=tuple(candidate.value for candidate in model_candidates),
                product_type=category,
                condition=analysis.condition.value.value,
                search_terms=tuple(analysis.search_terms),
            )
        return ProductResearchCandidate(
            source_product_id=source_product_id,
            target=target,
            model_candidates=model_candidates,
            image_urls=tuple(str(item["source_url"]) for item in image_rows),
        )
