from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from backend.app.domain.runs import ExplorationRun, RunMode, RunStatus


class PostgresRunRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def add(self, run: ExplorationRun) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            await connection.execute(
                """
                insert into runs.exploration_runs (
                    id, mode, trigger_source, requested_by, status, current_stage,
                    progress_numerator, progress_denominator, target_run_id,
                    started_at, finished_at, created_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                self._values(run),
            )

    async def get(self, run_id: UUID) -> ExplorationRun | None:
        async with await AsyncConnection.connect(
            self._database_url,
            row_factory=dict_row,
        ) as connection:
            cursor = await connection.execute(
                "select * from runs.exploration_runs where id = %s",
                (run_id,),
            )
            row = await cursor.fetchone()
        return self._from_row(row) if row else None

    async def list(self, limit: int = 50) -> list[ExplorationRun]:
        async with await AsyncConnection.connect(
            self._database_url,
            row_factory=dict_row,
        ) as connection:
            cursor = await connection.execute(
                """
                select * from runs.exploration_runs
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return [self._from_row(row) for row in rows]

    async def has_active_run(self) -> bool:
        async with await AsyncConnection.connect(self._database_url) as connection:
            cursor = await connection.execute(
                """
                select exists (
                    select 1 from runs.exploration_runs
                    where status in ('pending', 'running')
                )
                """
            )
            row = await cursor.fetchone()
        return bool(row and row[0])

    async def update(self, run: ExplorationRun) -> None:
        async with await AsyncConnection.connect(self._database_url) as connection:
            cursor = await connection.execute(
                """
                update runs.exploration_runs
                set status = %s, current_stage = %s,
                    progress_numerator = %s, progress_denominator = %s,
                    started_at = %s, finished_at = %s
                where id = %s
                """,
                (
                    run.status.value,
                    run.current_stage,
                    run.progress_numerator,
                    run.progress_denominator,
                    run.started_at,
                    run.finished_at,
                    run.id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(run.id)

    async def record_source_outcome(
        self,
        run_id: UUID,
        source_code: str,
        status: str,
        collected_count: int,
        error_category: str | None,
        error_message: str | None,
    ) -> None:
        error_count = 1 if error_category else 0
        async with (
            await AsyncConnection.connect(self._database_url) as connection,
            connection.transaction(),
        ):
            await connection.execute(
                """
                    insert into runs.source_statuses (
                        run_id, source_code, status, collected_count, error_count
                    ) values (%s, %s, %s, %s, %s)
                    on conflict (run_id, source_code) do update
                    set status = excluded.status,
                        collected_count = excluded.collected_count,
                        error_count = excluded.error_count,
                        updated_at = now()
                    """,
                (run_id, source_code, status, collected_count, error_count),
            )
            if error_category:
                await connection.execute(
                    """
                        insert into runs.errors (
                            run_id, stage, source, category, retryable,
                            user_message, technical_detail
                        ) values (%s, 'collecting_sources', %s, %s, %s, %s, %s)
                        """,
                    (
                        run_id,
                        source_code,
                        error_category,
                        error_category in {"TimeoutException", "NetworkError", "TimeoutError"},
                        "Source collection failed; independent sources continued.",
                        error_message,
                    ),
                )

    @staticmethod
    def _values(run: ExplorationRun) -> Sequence[object]:
        return (
            run.id,
            run.mode.value,
            run.trigger_source,
            run.requested_by,
            run.status.value,
            run.current_stage,
            run.progress_numerator,
            run.progress_denominator,
            run.target_run_id,
            run.started_at,
            run.finished_at,
            run.created_at,
        )

    @staticmethod
    def _from_row(row: Mapping[str, Any]) -> ExplorationRun:
        return ExplorationRun(
            id=UUID(str(row["id"])),
            mode=RunMode(row["mode"]),
            trigger_source=row["trigger_source"],
            requested_by=row["requested_by"],
            status=RunStatus(row["status"]),
            current_stage=row["current_stage"],
            progress_numerator=row["progress_numerator"],
            progress_denominator=row["progress_denominator"],
            target_run_id=UUID(str(row["target_run_id"])) if row["target_run_id"] else None,
            created_at=row["created_at"],
            started_at=row["started_at"] if isinstance(row["started_at"], datetime) else None,
            finished_at=row["finished_at"] if isinstance(row["finished_at"], datetime) else None,
        )
