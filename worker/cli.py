import argparse
import asyncio
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from backend.app.application.catalog import (
    CollectCatalogSources,
    IngestSourceProduct,
    RunContext,
    SourceConfig,
)
from backend.app.domain.runs import RunMode
from backend.app.domain.runs.models import ExplorationRun
from backend.app.infrastructure.database import (
    PostgresCatalogRepository,
    PostgresRunRepository,
)
from backend.app.infrastructure.sources import JimotySpotAdapter
from backend.app.shared.config import get_settings


async def explore(mode: RunMode, target_run_id: str | None, source_mode: str) -> int:
    if source_mode == "live":
        return await collect_live_catalog(mode, target_run_id)
    summary = {
        "status": "collection_skipped",
        "mode": mode.value,
        "target_run_id": target_run_id,
        "message": "Live source collection is disabled for this invocation.",
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


async def collect_live_catalog(mode: RunMode, target_run_id: str | None) -> int:
    settings = get_settings()
    if not settings.database_url:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "message": "TSUCHIBOT_DATABASE_URL is required for live collection.",
                },
                ensure_ascii=False,
            )
        )
        return 2

    target = UUID(target_run_id) if target_run_id else None
    trigger_source = "github_actions" if os.getenv("GITHUB_ACTIONS") == "true" else "worker_cli"
    run = ExplorationRun.pending(mode, "manual-worker", target, trigger_source)
    run_repository = PostgresRunRepository(settings.database_url)
    await run_repository.add(run)
    run = run.start()
    run = run.advance("collecting_sources", 0, 2)
    await run_repository.update(run)

    configs = (
        SourceConfig(
            "jimoty",
            "profile-67cea788596d2b1549267ce8",
            "Jimoty Spot 1",
            "https://jmty.jp/profiles/67cea788596d2b1549267ce8/articles",
            settings.jimoty_max_pages,
            settings.jimoty_request_interval_seconds,
        ),
        SourceConfig(
            "jimoty",
            "profile-68e5fa043b084d63ba34bea6",
            "Jimoty Spot 2",
            "https://jmty.jp/profiles/68e5fa043b084d63ba34bea6/articles",
            settings.jimoty_max_pages,
            settings.jimoty_request_interval_seconds,
        ),
    )
    catalog_repository = PostgresCatalogRepository(settings.database_url)
    collector = CollectCatalogSources(
        JimotySpotAdapter(),
        IngestSourceProduct(catalog_repository),
    )
    outcomes = await collector.execute(
        configs,
        RunContext(run.id, datetime.now(UTC)),
    )
    for outcome in outcomes:
        await run_repository.record_source_outcome(
            run.id,
            f"jimoty:{outcome.location_id}",
            outcome.status,
            outcome.collected_count,
            outcome.error_category,
            outcome.error_message,
        )
    partial_failure = any(outcome.status == "failed" for outcome in outcomes)
    run = run.complete(with_errors=partial_failure)
    await run_repository.update(run)
    print(
        json.dumps(
            {
                "status": run.status.value,
                "run_id": str(run.id),
                "mode": mode.value,
                "sources": [asdict(outcome) for outcome in outcomes],
            },
            ensure_ascii=False,
        )
    )
    return 0 if not partial_failure else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tsuchibot-worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    explore_parser = subparsers.add_parser("explore")
    explore_parser.add_argument("--mode", choices=[mode.value for mode in RunMode], required=True)
    explore_parser.add_argument("--target-run-id")
    explore_parser.add_argument(
        "--source-mode",
        choices=["disabled", "live"],
        default="disabled",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "explore":
        mode = RunMode(args.mode)
        if mode is RunMode.RETRY_FAILED and not args.target_run_id:
            raise SystemExit("--target-run-id is required for retry_failed")
        return asyncio.run(explore(mode, args.target_run_id, args.source_mode))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
