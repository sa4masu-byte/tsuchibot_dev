# Implementation Status

## Foundation baseline (2026-07-13)

Implemented:

- New Git repository layout described by `03_Architecture.md`.
- Python modular-monolith package boundaries for API, application, domain, and infrastructure.
- FastAPI health, shared-password session, run dispatch/list/detail endpoints.
- Signed HttpOnly cookie with expiry, constant-time password/signature checks, and production-secret validation.
- In-memory run repository for isolated development and tests.
- Server-only GitHub Actions dispatcher selected when repository and token settings exist.
- Exploration worker CLI and manual GitHub Actions workflow with overlap prevention.
- Local manual batch with incremental, full, and failed-item retry modes.
- PostgreSQL foundation migration for runs, configuration, source definitions, and audit events.
- RLS enabled without anonymous browser policies; server credentials mediate database access.
- Both supplied Jimoty profile article URLs seeded as independent source definitions.
- Version-controlled Phase 1 configuration defaults.
- Next.js App Router mobile-first login, dashboard, and run-history baseline.
- Backend and frontend CI gates for lint, strict types, tests, build, and worker smoke execution.

Deferred by roadmap:

- Applying migrations to a real Supabase project and production credential validation.
- Gemini analysis, Mercari evidence, recommendation calculations, review UI, EC exploration, and learning.
- Production deployment configuration, which depends on project identifiers and secrets.

No live source, LLM, marketplace, GitHub, or database calls are made by the default test suite.

## Sprint 2 catalog baseline (2026-07-13)

Implemented without changing the roadmap or domain calculation plan:

- Jimoty profile HTML parser and HTTP adapter for the two configured locations.
- Required normalized fields, explicit unknowns, item-ID extraction, category, price, image,
  availability, and listing-date normalization.
- Configurable page limit, minimum request interval, bounded transient retries, immediate blocked
  response handling, repeated-page protection, and within-run item deduplication.
- Deterministic duplicate evidence order covering item ID, canonical URL, image hash with price and
  location, and high title/price/location similarity. Uncertain matches are never merged.
- New, unchanged, price-changed, availability-changed, and combined-change classification.
- Append-only source, price, and availability histories with immutable database triggers.
- PostgreSQL catalog and run repositories, source status/error persistence, and idempotent
  observation writes.
- Worker integration for independent two-location collection and partial-failure completion.
- Recorded HTML fixtures and contract tests; default CI remains disconnected from live Jimoty.

The project background now ＿records that the user manages Jimoty operations and uses the system for
appropriate price-setting research. Requirements, architecture, roadmap, and implementation order
remain unchanged as requested.

## Connected development environment (2026-07-13)

- Supabase migrations `0001` through `0003` applied with checksum tracking.
- Schema verification found 15 application tables, two Jimoty source definitions, and RLS enabled
  on all 14 application-owned base tables (the migration ledger is separate).
- First live incremental collection completed for both locations: 20 source products, 20 source
  observations, 20 price observations, 20 availability observations, and 20 image references.
- GitHub repository and CI connected; live exploration still requires the database connection to be
  registered as the repository secret `TSUCHIBOT_DATABASE_URL`.

## Sprint 3 structured-analysis baseline (2026-07-13)

- Strict `product-analysis-v1` Pydantic schema with explicit unknowns, bounded confidences and
  severities, model-number candidates, visible text, condition evidence, price bands, search terms,
  and uncertainty notes.
- Unexpected financial or recommendation fields are rejected at validation time.
- Version-controlled prompt explicitly prohibits guessing and deterministic business calculations.
- Replaceable `VisionProvider` application port and Gemini HTTP adapter.
- Gemini requests use JSON structured output, at most five images, supported MIME validation,
  per-image size limits, configurable stable model selection, and usage-token capture.
- Default tests use recorded JSON and mocked HTTP only. Live validation awaits a Gemini API key.
