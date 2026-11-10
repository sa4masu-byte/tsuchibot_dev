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

The project background now records that the user manages Jimoty operations and uses the system for
appropriate price-setting research. Requirements, architecture, roadmap, and implementation order
remain unchanged as requested.

## Connected development environment (2026-07-13)

- Supabase migrations `0001` through `0007` applied with checksum tracking.
- Schema verification found 30 application tables, two Jimoty source definitions, and RLS enabled
  on all 30 application-owned base tables (the migration ledger is separate).
- First live incremental collection completed for both locations: 20 source products, 20 source
  observations, 20 price observations, 20 availability observations, and 20 image references.
- GitHub repository, CI, and the database repository secret are connected.
- GitHub Actions converts the Supabase direct URL to the project's IPv4-capable session-pooler URL
  without logging the credential. A live Actions collection completed both locations with 10 items
  each and no source errors, increasing source observations from 40 to 60.

## Sprint 3 structured-analysis baseline (2026-07-13)

- Strict `product-analysis-v1` Pydantic schema with explicit unknowns, bounded confidences and
  severities, model-number candidates, visible text, condition evidence, price bands, search terms,
  and uncertainty notes.
- Unexpected financial or recommendation fields are rejected at validation time.
- Version-controlled prompt explicitly prohibits guessing and deterministic business calculations.
- Replaceable `VisionProvider` application port and Gemini HTTP adapter.
- Gemini requests use JSON structured output, at most five images, supported MIME validation,
  per-image size limits, configurable stable model selection, and usage-token capture.
- Default tests use recorded JSON and mocked HTTP only; the connected environment also has a
  validated Gemini API key for explicit live checks.
- Migration `0004_ai_analysis.sql` adds canonical products, source links, immutable AI analysis
  history, idempotency inputs, validation state, token usage, latency, and failure metadata.
- Live Gemini validation succeeded with the current stable `gemini-3.5-flash`; one real image
  analysis was schema-valid and persisted with usage and latency metadata.
- Generic CDN image responses are detected by JPEG/PNG/WebP signatures, and transient Gemini
  408/429/selected-5xx responses use bounded exponential retries.

## Sprint 4 Mercari research baseline (2026-07-13)

- Deterministic five-stage query generation covering exact model, manufacturer and model, series
  and product type, manufacturer and product type, and similar-product terms.
- Unified sold and active listing model with listing-ID deduplication, 50-result limits per status,
  query provenance, parser version, and explicit shipping evidence.
- Comparable ranking records model, title, condition, and attribute similarity independently before
  applying bundle, junk, reserved-listing, evidence-period, and manual-review rules.
- Price evidence uses included sold comparables from the previous 90 days. Median, lower quartile,
  range, dispersion, snapshot hash, and the three-comparable sufficiency result are persisted.
- Shipping evidence records the median explicit or normalized amount, dominant method, count,
  confidence, and reason separately from later recommendation calculations.
- Migration `0005_mercari_research.sql` creates research sessions, staged queries, executions,
  normalized marketplace listings, query links, comparable evidence and append-only decisions,
  price statistics, and shipping statistics. All nine research tables have RLS enabled.
- A strict `mercari-manual-v1` JSON adapter and worker batch provide the required manual fallback.
  Source products can be linked to a new or existing canonical product before research.
- A manually triggered, slow, sequential Playwright adapter now follows the public web workflow.
  Strong Gemini model evidence skips visual search; uncertain products use the first Jimoty image
  with Google Lens before staged Mercari sold and active searches.
- Mercari search cards and detail pages provide title, price, status, listing-age upper bound,
  condition, shipping responsibility, method, and explicit shipping amount. Listing time is used as
  a conservative 90-day upper bound only when an exact sold timestamp is unavailable.
- Migration `0006_visual_search_evidence.sql` stores append-only Lens titles, resolved model
  candidates, confidence, source agreement, and failures without duplicating the source image URL.
- CAPTCHA, login requirements, and access blocks are never bypassed. Browser runs stop or retain
  partial evidence, and diagnostic screenshots are written only on failure.
- A live local smoke run retained a Google Lens block as failure evidence, continued on the
  independent Mercari origin, saved two query executions and eight comparables, and correctly
  withheld a price estimate because no sold comparable met the inclusion rules.
- Migrations are applied to the connected Supabase project with no pending migrations. Default CI
  uses recorded HTML and JSON evidence only and does not call Google Lens or Mercari.

## Sprint 5 deterministic-recommendation baseline (2026-07-13)

- Versioned integer-yen fee, sourcing-cost, shipping fallback, profit, return-on-cost, and sales
  margin calculators are isolated from AI and external adapters.
- `phase1-scores-v1` deterministically calculates the 90-day sales-prospect heuristic, confidence,
  and overall sourcing score with a structured component for each material input or deduction.
- `phase1-thresholds-v1` applies the documented JPY 300/500/1,000 profit thresholds, prospect and
  confidence gates, comparable sufficiency, unresolved risks, and four recommendation tiers.
- Migration `0007_recommendations.sql` creates append-only recommendation snapshots, structured
  reason components, quantity-one-through-four evaluations, active versioned configuration, RLS,
  idempotency, audit events, and run metrics.
- Browser and source-linked manual Mercari research calculate a recommendation after persistence;
  `scripts/recommend.sh` recalculates from an existing evidence snapshot without live access.
- A connected-data smoke calculation preserved an evidence-limited Disney plush result as reject,
  with no invented sale price, shipping, profit, or overall score. Its latest corrected evidence
  input produced prospect 9 and confidence 29, with confirmation and risk reasons persisted.

## Sprint 6 web-review baseline (2026-07-13)

- Authenticated dashboard, candidate list, and product detail APIs expose the latest deterministic
  recommendation, structured reasons, research statistics, and comparable evidence.
- Product corrections and comparable exclude/restore commands require idempotency keys, reject
  disallowed browser origins, append audit/history records, and recalculate the recommendation.
- Active corrections can override confirmed product identity, model, condition, appropriate sale
  price, and shipping inputs without changing the underlying AI analysis history.
- Candidate and detail screens are mobile-first, preserve unknown values as `未確認`, and link back
  to source evidence instead of presenting estimates without provenance.
- Migration `0008_web_review.sql` adds RLS-protected correction history and comparable-command
  idempotency. It was applied successfully to the connected Supabase project through the manual
  GitHub workflow.
- Backend lint, strict typing, and 80 tests pass. Frontend lint, type checking, four tests, and the
  Next.js production build pass for dashboard, candidate list, and dynamic product-detail routes.

## Sprint 7 EC-exploration baseline (2026-07-14)

- Amazon, Rakuten, AliExpress, and SHEIN are represented by isolated source adapters sharing a
  strict `ec-manual-v1` fallback document; default tests and batches make no live EC requests.
- The alternative exploration coordinator triggers below the configured useful-Jimoty threshold,
  preserves source order, deduplicates up to 20 keywords in profit-pattern, Mercari-demand, then
  sale-discount order, and isolates missing or failed sources.
- Overseas policy deterministically checks selected-variant price, seven-day delivery, review
  count, product rating, seller rating, authenticity support, and excluded product types.
- Displayed price, sourcing shipping, definite coupon, points reference, original currency, and
  sourcing cost remain separate. Points never reduce Phase 1 sourcing cost.
- Eligible EC offers enter the existing catalog so Gemini, Mercari evidence, and deterministic
  recommendation can continue without a separate calculation path.
- Migration `0009_ec_exploration.sql` adds append-only sessions, source/query attempts, offers,
  evaluations, RLS, indexes, audit/metrics, and versioned EC policy configuration. It is applied to
  the connected Supabase project.
- Authenticated EC history and evidence pages expose attempts, offers, sourcing costs, policy
  outcomes, and structured rejection or confirmation reasons on mobile.

## Sprint 8 inventory-and-learning baseline (2026-08-03)

- Authenticated purchase decisions preserve both purchased and not-purchased outcomes. Purchased
  quantities are limited to one through four, and the actual charged amount is validated from the
  product amount, sourcing shipping, and definite coupon; points remain reference-only.
- Each inventory position freezes the recommendation available at purchase time in a prediction
  snapshot. Purchase, listing, sale, and negative-outcome values are stored separately as actual
  append-only events and never overwrite that snapshot.
- Remaining inventory prevents over-sale and over-allocation to return, cancellation, 90-day
  unsold, damaged, lost, or other outcomes. Split sales use cumulative integer-yen cost allocation
  so their allocated purchase costs sum exactly to the actual charged amount.
- Realised profit is calculated on the server from actual sale revenue, fee, sale shipping, and
  allocated purchase cost. Inventory detail exposes predicted profit for the sold quantity, actual
  profit, and their difference.
- Personal appeal and research-value Feedback are append-only learning signals. The five initial
  FR-110 profit patterns and hypotheses are seeded, and supporting, contradictory, or neutral
  evidence can be appended without autonomously changing confidence or scoring rules.
- Candidate detail now records purchase decisions and Feedback. Mobile inventory screens guide
  listing, sale, negative outcome, and hypothesis-evidence entry and show balance, actual financial
  totals, prediction-versus-actual comparison, and learning history.
- Migration `0010_inventory_learning.sql` adds inventory and learning schemas, constraints,
  append-only guards, RLS, indexes, initial patterns, hypotheses, command idempotency, and audit
  records. Default tests remain disconnected from external sites and never purchase or list items.

## Sprint 9 hardening in progress (2026-11-10)

- Login, logout, and run dispatch reject disallowed browser origins and explicit cross-site Fetch
  Metadata. Login attempts are bounded per client address within one API process, with a 429 and
  `Retry-After` response. This is not yet a distributed rate limiter.
- API mutation bodies have a configurable size ceiling that is enforced before JSON parsing,
  including streamed requests. Malformed signed cookies now fail closed as unauthenticated.
- New migration `0011_command_idempotency.sql` reserves one command key globally across inventory
  and learning operations, binds it to the action, target, and payload hash, and rejects a reused
  key with different intent. Run dispatch now uses the same ledger, so a replay returns the same
  Run without a second GitHub request. Inventory replays do not duplicate learning or audit events.
- CI now provisions disposable PostgreSQL, applies every migration, and exercises purchase,
  listing, sale, negative outcome, feedback, and hypothesis evidence replay. Local tests skip
  this integration contract unless an explicit `*_test` database URL is provided.
- Migration 0011 has not yet been applied to the connected Supabase project. Production deployment,
  complete mobile E2E coverage, and the remaining Sprint 9 acceptance checks are pending.
