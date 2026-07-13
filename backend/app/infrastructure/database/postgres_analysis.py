from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from backend.app.application.vision import ProductVisionResult


class PostgresAnalysisRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def save_success(
        self,
        source_product_id: UUID,
        run_id: UUID,
        image_set_hash: str,
        request_hash: str,
        result: ProductVisionResult,
        latency_ms: int,
    ) -> UUID | None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            cursor = await connection.execute(
                """
                insert into catalog.ai_product_analyses (
                    source_product_id, run_id, provider, model, prompt_version,
                    schema_version, image_set_hash, request_hash, raw_response,
                    parsed_result, validation_status, analysis_status,
                    input_tokens, output_tokens, latency_ms
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'valid', 'completed', %s, %s, %s
                )
                on conflict (
                    source_product_id, image_set_hash, prompt_version, model, schema_version
                ) do nothing
                returning id
                """,
                (
                    source_product_id,
                    run_id,
                    result.provider,
                    result.model,
                    result.prompt_version,
                    result.schema_version,
                    image_set_hash,
                    request_hash,
                    Jsonb(result.raw_response),
                    Jsonb(result.analysis.model_dump(mode="json")),
                    result.input_tokens,
                    result.output_tokens,
                    latency_ms,
                ),
            )
            row = await cursor.fetchone()
        return row[0] if row else None
