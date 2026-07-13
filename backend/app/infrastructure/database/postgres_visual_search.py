import hashlib
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from backend.app.application.identification import ModelIdentificationResult


class PostgresVisualSearchRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def save(
        self,
        source_product_id: UUID,
        run_id: UUID,
        image_url: str,
        result: ModelIdentificationResult,
    ) -> UUID | None:
        if not result.visual_search_used or result.provider is None:
            return None
        async with await AsyncConnection.connect(self._database_url) as connection:
            cursor = await connection.execute(
                """
                insert into research.visual_search_evidence (
                    source_product_id, run_id, provider, image_url_hash, status,
                    result_titles, resolved_candidates, failure_type, failure_message
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    source_product_id,
                    run_id,
                    result.provider,
                    hashlib.sha256(image_url.encode()).hexdigest(),
                    result.status,
                    Jsonb(
                        [
                            {"title": hit.title, "url": hit.url, "source": hit.source}
                            for hit in result.visual_hits
                        ]
                    ),
                    Jsonb(
                        [
                            {
                                "value": candidate.value,
                                "confidence": candidate.confidence,
                                "evidence": candidate.evidence,
                                "sources": candidate.sources,
                            }
                            for candidate in result.candidates
                        ]
                    ),
                    result.error_category,
                    result.error_message,
                ),
            )
            row = await cursor.fetchone()
        return UUID(str(row[0])) if row else None
