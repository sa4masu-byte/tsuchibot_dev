import argparse
import asyncio
import json
import os
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from backend.app.application.catalog import (
    CollectCatalogSources,
    IngestSourceProduct,
    RunContext,
    SourceConfig,
)
from backend.app.application.identification import ResolveModelIdentity
from backend.app.application.recommendation import (
    CalculateRecommendation,
    RecommendationRecord,
    RecommendationRequest,
)
from backend.app.application.research import ConductMercariResearch, ResearchRequest
from backend.app.domain.runs import RunMode
from backend.app.domain.runs.models import ExplorationRun
from backend.app.infrastructure.database import (
    PostgresCanonicalProductRepository,
    PostgresCatalogRepository,
    PostgresRecommendationCandidateRepository,
    PostgresRecommendationRepository,
    PostgresResearchCandidateRepository,
    PostgresResearchRepository,
    PostgresRunRepository,
    PostgresVisualSearchRepository,
)
from backend.app.infrastructure.sources import JimotySpotAdapter, load_manual_research_document
from backend.app.infrastructure.sources.browser_research import (
    BrowserMercariAdapter,
    BrowserResearchSession,
    GoogleLensBrowserAdapter,
)
from backend.app.shared.config import get_settings


async def calculate_saved_recommendation(
    source_product_id: UUID,
    run_id: UUID,
    research_session_id: UUID | None = None,
) -> RecommendationRecord:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("TSUCHIBOT_DATABASE_URL is required for recommendation persistence")
    candidate = await PostgresRecommendationCandidateRepository(settings.database_url).get(
        source_product_id,
        run_id,
        research_session_id,
    )
    if candidate is None:
        raise KeyError("recommendation inputs were not found for the requested product and run")
    return await CalculateRecommendation(
        PostgresRecommendationRepository(settings.database_url)
    ).execute(
        RecommendationRequest(
            canonical_product_id=candidate.canonical_product_id,
            source_product_id=candidate.source_product_id,
            research_session_id=candidate.research_session_id,
            run_id=candidate.run_id,
            inputs=candidate.inputs,
            policy=candidate.policy,
            calculated_at=datetime.now(UTC),
        )
    )


def recommendation_summary(record: RecommendationRecord | None) -> dict[str, object]:
    if record is None:
        return {}
    return {
        "recommendation_id": str(record.id),
        "recommendation_tier": record.result.tier.value,
        "expected_profit_jpy": record.result.expected_profit_jpy,
        "return_on_cost": (
            str(record.result.return_on_cost) if record.result.return_on_cost is not None else None
        ),
        "sales_prospect_score": record.result.sales_prospect_score,
        "confidence_score": record.result.confidence_score,
        "overall_sourcing_score": record.result.overall_sourcing_score,
    }


async def calculate_recommendation_soft(
    source_product_id: UUID,
    run_id: UUID,
    research_session_id: UUID,
    run_repository: PostgresRunRepository,
) -> tuple[RecommendationRecord | None, str]:
    try:
        return (
            await calculate_saved_recommendation(
                source_product_id,
                run_id,
                research_session_id,
            ),
            "completed",
        )
    except Exception as exc:
        await run_repository.record_error(
            run_id,
            "calculating_recommendation",
            "deterministic_recommendation",
            str(source_product_id),
            type(exc).__name__,
            "Recommendation calculation failed; completed research evidence was retained.",
        )
        return None, "failed"


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


async def research_manual(
    canonical_product_id: str | None,
    source_product_id: str | None,
    run_id: str,
    input_path: Path,
) -> int:
    settings = get_settings()
    if not settings.database_url:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "message": "TSUCHIBOT_DATABASE_URL is required for research persistence.",
                },
                ensure_ascii=False,
            )
        )
        return 2
    target, provider = load_manual_research_document(input_path)
    parsed_run_id = UUID(run_id)
    if await PostgresRunRepository(settings.database_url).get(parsed_run_id) is None:
        raise KeyError(f"exploration run not found: {parsed_run_id}")
    if canonical_product_id:
        resolved_canonical_product_id = UUID(canonical_product_id)
    elif source_product_id:
        resolved_canonical_product_id = (
            await PostgresCanonicalProductRepository(settings.database_url).ensure_for_source(
                UUID(source_product_id),
                target,
            )
        )
    else:
        raise ValueError("canonical_product_id or source_product_id is required")
    outcome = await ConductMercariResearch(
        provider,
        PostgresResearchRepository(settings.database_url),
    ).execute(
        ResearchRequest(
            canonical_product_id=resolved_canonical_product_id,
            run_id=parsed_run_id,
            target=target,
            researched_at=datetime.now(UTC),
            sold_limit=settings.mercari_sold_result_limit,
            active_limit=settings.mercari_active_result_limit,
            evidence_days=settings.mercari_evidence_days,
            minimum_sold_comparables=settings.mercari_minimum_sold_comparables,
        )
    )
    recommendation, recommendation_status = (
        await calculate_recommendation_soft(
            UUID(source_product_id),
            parsed_run_id,
            outcome.session_id,
            PostgresRunRepository(settings.database_url),
        )
        if source_product_id
        else (None, "skipped")
    )
    print(
        json.dumps(
            {
                "status": outcome.status,
                "research_session_id": str(outcome.session_id),
                "query_count": len(outcome.executions),
                "comparable_count": len(outcome.comparables),
                "included_sold_count": outcome.price_statistics.included_count,
                "sufficient_evidence": outcome.price_statistics.sufficient_evidence,
                "median_price_jpy": outcome.price_statistics.median_price_jpy,
                **recommendation_summary(recommendation),
                "recommendation_status": recommendation_status,
            },
            ensure_ascii=False,
        )
    )
    return 0 if outcome.status in {"completed", "partial_failure"} else 3


async def research_browser(
    source_product_id: str,
    run_id: str,
    *,
    headless: bool,
) -> int:
    settings = get_settings()
    if not settings.database_url:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "message": "TSUCHIBOT_DATABASE_URL is required for browser research.",
                },
                ensure_ascii=False,
            )
        )
        return 2
    parsed_source_id = UUID(source_product_id)
    parsed_run_id = UUID(run_id)
    if await PostgresRunRepository(settings.database_url).get(parsed_run_id) is None:
        raise KeyError(f"exploration run not found: {parsed_run_id}")
    candidate = await PostgresResearchCandidateRepository(settings.database_url).get(
        parsed_source_id
    )
    if candidate is None:
        raise KeyError(f"source product not found: {parsed_source_id}")

    try:
        async with BrowserResearchSession(
            headless=headless,
            request_interval_seconds=settings.browser_request_interval_seconds,
            navigation_timeout_seconds=settings.browser_navigation_timeout_seconds,
        ) as browser_session:
            identity = await ResolveModelIdentity(
                GoogleLensBrowserAdapter(browser_session),
                threshold=settings.model_visual_search_threshold,
            ).execute(candidate.model_candidates, candidate.image_urls)
            if identity.visual_search_used and candidate.image_urls:
                await PostgresVisualSearchRepository(settings.database_url).save(
                    parsed_source_id,
                    parsed_run_id,
                    candidate.image_urls[0],
                    identity,
                )
            selected_models = tuple(
                item.value for item in identity.candidates if item.confidence >= 0.55
            )[:3]
            target = replace(
                candidate.target,
                model_numbers=selected_models or candidate.target.model_numbers,
            )
            canonical_id = await PostgresCanonicalProductRepository(
                settings.database_url
            ).ensure_for_source(parsed_source_id, target)
            outcome = await ConductMercariResearch(
                BrowserMercariAdapter(
                    browser_session,
                    detail_limit_per_query=settings.browser_detail_limit_per_query,
                ),
                PostgresResearchRepository(settings.database_url),
            ).execute(
                ResearchRequest(
                    canonical_product_id=canonical_id,
                    run_id=parsed_run_id,
                    target=target,
                    researched_at=datetime.now(UTC),
                    sold_limit=settings.mercari_sold_result_limit,
                    active_limit=settings.mercari_active_result_limit,
                    evidence_days=settings.mercari_evidence_days,
                    minimum_sold_comparables=(
                        settings.mercari_minimum_sold_comparables
                    ),
                    config_version="mercari-browser-v1",
                )
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "browser_error",
                    "error_category": type(exc).__name__,
                    "message": "Browser research stopped without bypassing the page restriction.",
                },
                ensure_ascii=False,
            )
        )
        return 4
    recommendation, recommendation_status = await calculate_recommendation_soft(
        parsed_source_id,
        parsed_run_id,
        outcome.session_id,
        PostgresRunRepository(settings.database_url),
    )
    print(
        json.dumps(
            {
                "status": outcome.status,
                "research_session_id": str(outcome.session_id),
                "visual_search_used": identity.visual_search_used,
                "visual_search_status": identity.status,
                "model_candidates": [item.value for item in identity.candidates[:3]],
                "query_count": len(outcome.executions),
                "comparable_count": len(outcome.comparables),
                "included_sold_count": outcome.price_statistics.included_count,
                "sufficient_evidence": outcome.price_statistics.sufficient_evidence,
                "median_price_jpy": outcome.price_statistics.median_price_jpy,
                **recommendation_summary(recommendation),
                "recommendation_status": recommendation_status,
            },
            ensure_ascii=False,
        )
    )
    return 0 if outcome.status in {"completed", "partial_failure"} else 3


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
    research_parser = subparsers.add_parser("research-manual")
    product_group = research_parser.add_mutually_exclusive_group(required=True)
    product_group.add_argument("--canonical-product-id")
    product_group.add_argument("--source-product-id")
    research_parser.add_argument("--run-id", required=True)
    research_parser.add_argument("--input", type=Path, required=True)
    browser_parser = subparsers.add_parser("research-browser")
    browser_parser.add_argument("--source-product-id", required=True)
    browser_parser.add_argument("--run-id", required=True)
    browser_parser.add_argument("--headless", action="store_true")
    recommendation_parser = subparsers.add_parser("recommend")
    recommendation_parser.add_argument("--source-product-id", required=True)
    recommendation_parser.add_argument("--run-id", required=True)
    recommendation_parser.add_argument("--research-session-id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "explore":
        mode = RunMode(args.mode)
        if mode is RunMode.RETRY_FAILED and not args.target_run_id:
            raise SystemExit("--target-run-id is required for retry_failed")
        return asyncio.run(explore(mode, args.target_run_id, args.source_mode))
    if args.command == "research-manual":
        return asyncio.run(
            research_manual(
                args.canonical_product_id,
                args.source_product_id,
                args.run_id,
                args.input,
            )
        )
    if args.command == "research-browser":
        return asyncio.run(
            research_browser(
                args.source_product_id,
                args.run_id,
                headless=args.headless,
            )
        )
    if args.command == "recommend":
        record = asyncio.run(
            calculate_saved_recommendation(
                UUID(args.source_product_id),
                UUID(args.run_id),
                UUID(args.research_session_id) if args.research_session_id else None,
            )
        )
        print(json.dumps(recommendation_summary(record), ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
