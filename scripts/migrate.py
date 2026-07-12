import argparse
import asyncio
import json
from pathlib import Path

from backend.app.infrastructure.database.migrations import PostgresMigrationRunner
from backend.app.shared.config import get_settings


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Apply or inspect Tsuchibot PostgreSQL migrations")
    result.add_argument("command", choices=["apply", "status"], nargs="?", default="apply")
    return result


async def run(command: str) -> int:
    settings = get_settings()
    if not settings.database_url:
        print(json.dumps({"status": "error", "message": "TSUCHIBOT_DATABASE_URL is required"}))
        return 2
    migration_directory = Path(__file__).parents[1] / "backend" / "migrations"
    runner = PostgresMigrationRunner(settings.database_url, migration_directory)
    if command == "apply":
        applied = await runner.apply()
        print(json.dumps({"status": "ok", "applied": applied}))
    else:
        applied, pending = await runner.status()
        print(json.dumps({"status": "ok", "applied": applied, "pending": pending}))
    return 0


def main() -> int:
    return asyncio.run(run(parser().parse_args().command))


if __name__ == "__main__":
    raise SystemExit(main())
