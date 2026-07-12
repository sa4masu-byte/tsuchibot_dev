import hashlib
from dataclasses import dataclass
from pathlib import Path

from psycopg import AsyncConnection
from psycopg.rows import dict_row


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    name: str
    checksum: str
    sql: str


def discover_migrations(directory: Path) -> tuple[Migration, ...]:
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        sql = path.read_text()
        migrations.append(
            Migration(
                name=path.name,
                checksum=hashlib.sha256(sql.encode()).hexdigest(),
                sql=sql,
            )
        )
    if not migrations:
        raise MigrationError(f"no SQL migrations found in {directory}")
    return tuple(migrations)


def pending_migrations(
    migrations: tuple[Migration, ...],
    applied: dict[str, str],
) -> tuple[Migration, ...]:
    pending: list[Migration] = []
    for migration in migrations:
        previous_checksum = applied.get(migration.name)
        if previous_checksum is None:
            pending.append(migration)
        elif previous_checksum != migration.checksum:
            raise MigrationError(f"applied migration checksum changed: {migration.name}")
    unknown = sorted(set(applied) - {migration.name for migration in migrations})
    if unknown:
        raise MigrationError(f"database contains unknown migrations: {', '.join(unknown)}")
    return tuple(pending)


class PostgresMigrationRunner:
    def __init__(self, database_url: str, migration_directory: Path) -> None:
        self._database_url = database_url
        self._migrations = discover_migrations(migration_directory)

    async def apply(self) -> tuple[str, ...]:
        async with await AsyncConnection.connect(
            self._database_url,
            row_factory=dict_row,
        ) as connection:
            await connection.execute(
                "select pg_advisory_lock(hashtext('tsuchibot_schema_migrations'))"
            )
            try:
                await self._ensure_ledger(connection)
                applied = await self._load_applied(connection)
                pending = pending_migrations(self._migrations, applied)
                for migration in pending:
                    async with connection.transaction():
                        await connection.execute(migration.sql)
                        await connection.execute(
                            """
                            insert into public.schema_migrations (name, checksum)
                            values (%s, %s)
                            """,
                            (migration.name, migration.checksum),
                        )
                return tuple(migration.name for migration in pending)
            finally:
                await connection.execute(
                    "select pg_advisory_unlock(hashtext('tsuchibot_schema_migrations'))"
                )

    async def status(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        async with await AsyncConnection.connect(
            self._database_url,
            row_factory=dict_row,
        ) as connection:
            await self._ensure_ledger(connection)
            applied = await self._load_applied(connection)
        pending = pending_migrations(self._migrations, applied)
        return tuple(applied), tuple(migration.name for migration in pending)

    @staticmethod
    async def _ensure_ledger(connection: AsyncConnection[dict[str, object]]) -> None:
        await connection.execute(
            """
            create table if not exists public.schema_migrations (
                name text primary key,
                checksum text not null,
                applied_at timestamptz not null default now()
            )
            """
        )
        await connection.commit()

    @staticmethod
    async def _load_applied(
        connection: AsyncConnection[dict[str, object]],
    ) -> dict[str, str]:
        cursor = await connection.execute(
            "select name, checksum from public.schema_migrations order by name"
        )
        rows = await cursor.fetchall()
        return {str(row["name"]): str(row["checksum"]) for row in rows}
