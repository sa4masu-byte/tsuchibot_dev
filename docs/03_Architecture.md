# 仕入れ判断エージェント Tsuchibot
## 03_Architecture.md — Phase 1 Architecture Specification

- Document version: 0.1
- Scope: Phase 1
- Status: Draft for implementation
- Related documents:
  - `00_Project.md`
  - `01_Principles.md`
  - `02_Requirements.md`
  - `12_Codex.md`

---

# 1. Architecture Goals

The Phase 1 architecture shall satisfy the following goals.

1. Implement the full sourcing workflow from collection to recommendation.
2. Keep financial calculations deterministic and testable.
3. Isolate all external-site and AI-provider dependencies.
4. Preserve history for later learning and evaluation.
5. Support partial failure without aborting unrelated work.
6. Allow a smartphone user to review and correct results.
7. Allow Codex or another implementation agent to understand boundaries and responsibilities clearly.
8. Avoid premature microservices and premature machine learning.
9. Support future replacement of Gemini, Supabase, GitHub Actions, or a source adapter.
10. Maintain traceability from requirement IDs to modules, APIs, and persistence.

---

# 2. Architecture Style

## 2.1 Modular Monolith

Phase 1 shall use a modular monolith.

The system is deployed as multiple runtime components, but domain logic remains one coherent codebase with explicit module boundaries.

Primary runtime components:

- Next.js web application
- FastAPI backend
- GitHub Actions exploration worker
- Supabase PostgreSQL
- Supabase Storage

The worker and FastAPI backend shall share the same Python domain and application packages.

## 2.2 Domain-Centred Design

The architecture is organised by domain capability rather than by technical layer alone.

Primary bounded modules:

- `catalog`
- `research`
- `recommendation`
- `learning`
- `inventory`
- `runs`
- `identity`
- `shared`

## 2.3 Clean Boundaries

The core domain must not depend on:

- FastAPI
- Supabase SDK
- GitHub API
- Gemini SDK
- Playwright
- requests/HTTPX page parsing
- Next.js
- source-specific CSS selectors

Infrastructure depends inward on domain interfaces.

---

# 3. High-Level System Context

```text
┌─────────────────────┐
│ Smartphone / Browser│
└──────────┬──────────┘
           │ HTTPS
           ▼
┌─────────────────────┐
│ Next.js on Vercel   │
│ - dashboard         │
│ - product details   │
│ - corrections       │
│ - run trigger       │
└───────┬─────────────┘
        │ REST/HTTPS
        ▼
┌─────────────────────┐
│ FastAPI Backend     │
│ - query APIs        │
│ - command APIs      │
│ - auth/session      │
│ - GitHub dispatch   │
└───────┬─────────────┘
        │
        ├───────────────┐
        │               │
        ▼               ▼
┌───────────────┐  ┌─────────────────────┐
│ Supabase      │  │ GitHub Actions      │
│ PostgreSQL    │  │ Exploration Worker  │
│ Storage       │  │ Python application  │
└───────────────┘  └───────┬─────────────┘
                            │
          ┌─────────────────┼─────────────────────┐
          ▼                 ▼                     ▼
  ┌─────────────┐   ┌──────────────┐      ┌──────────────┐
  │ Source Sites│   │ Gemini API   │      │ Mercari      │
  │ Jimoty / EC │   │ vision/text  │      │ research     │
  └─────────────┘   └──────────────┘      └──────────────┘
```

---

# 4. Repository Structure

```text
tsuchibot/
├── README.md
├── CODEX.md
├── pyproject.toml
├── package.json
├── docker-compose.yml
├── Makefile
├── .env.example
├── .gitignore
│
├── docs/
│   ├── 00_Project.md
│   ├── 01_Principles.md
│   ├── 02_Requirements.md
│   ├── 03_Architecture.md
│   ├── 04_Domain.md
│   ├── 05_Database.md
│   ├── 06_AI.md
│   ├── 07_Scraping.md
│   ├── 08_API.md
│   ├── 09_Frontend.md
│   ├── 10_Roadmap.md
│   ├── 11_Test.md
│   ├── 12_Codex.md
│   └── adr/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── application/
│   │   ├── domain/
│   │   │   ├── catalog/
│   │   │   ├── research/
│   │   │   ├── recommendation/
│   │   │   ├── learning/
│   │   │   ├── inventory/
│   │   │   ├── runs/
│   │   │   └── shared/
│   │   ├── infrastructure/
│   │   │   ├── database/
│   │   │   ├── storage/
│   │   │   ├── vision/
│   │   │   ├── sources/
│   │   │   ├── mercari/
│   │   │   ├── github/
│   │   │   └── security/
│   │   └── main.py
│   ├── migrations/
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   ├── runs/
│   │   │   ├── products/
│   │   │   ├── comparables/
│   │   │   ├── corrections/
│   │   │   ├── inventory/
│   │   │   └── settings/
│   │   └── lib/
│   └── tests/
│
├── worker/
│   ├── cli.py
│   ├── jobs/
│   └── tests/
│
├── prompts/
├── scripts/
├── infra/
├── tests/
└── .github/
    └── workflows/
        ├── explore.yml
        ├── test.yml
        └── deploy-check.yml
```

---

# 5. Backend Module Boundaries

## 5.1 Catalog Module

Responsibilities:

- source product ingestion
- source identity
- source observations
- duplicate detection
- price history
- availability history
- image references
- canonical product representation
- manual product corrections

Primary requirement coverage:

- FR-001 to FR-007
- FR-020 to FR-024
- FR-089
- FR-125

Key entities:

- `SourceProduct`
- `SourceObservation`
- `PriceObservation`
- `ProductImage`
- `CanonicalProduct`
- `ProductCorrection`

Key services:

- `SourceProductIngestionService`
- `DuplicateDetectionService`
- `PriceChangeDetectionService`
- `CanonicalizationService`
- `CorrectionApplicationService`

## 5.2 Research Module

Responsibilities:

- Mercari search query generation
- Mercari result collection
- comparable matching
- comparable inclusion/exclusion
- resale price evidence
- shipping evidence
- demand evidence

Primary requirement coverage:

- FR-030 to FR-044

Key entities:

- `ResearchSession`
- `SearchQuery`
- `MarketplaceListing`
- `ComparableEvidence`
- `ComparableDecision`
- `ShippingEvidence`
- `PriceStatistics`

Key services:

- `SearchQueryGenerationService`
- `ComparableRankingService`
- `ComparableSelectionService`
- `PriceEvidenceService`
- `ShippingEvidenceService`
- `SoldRateService`

## 5.3 Recommendation Module

Responsibilities:

- financial calculations
- 90-day sales prospect score
- confidence score
- overall sourcing score
- recommendation tier
- structured reasons
- recalculation after corrections

Primary requirement coverage:

- FR-040 to FR-066

Key value objects:

- `Money`
- `ProfitEstimate`
- `MarginMetrics`
- `SalesProspectScore`
- `ConfidenceScore`
- `SourcingScore`
- `RecommendationTier`
- `ReasonComponent`

Key services:

- `MercariFeeCalculator`
- `SourcingCostCalculator`
- `ProfitCalculator`
- `SalesProspectScorer`
- `ConfidenceScorer`
- `SourcingRanker`
- `RecommendationClassifier`
- `ExplanationAssembler`

## 5.4 Learning Module

Responsibilities:

- profit hypotheses
- profit patterns
- user-interest feedback
- research-value feedback
- learning event log
- reflection input
- hypothesis evidence updates

Primary requirement coverage:

- FR-090 to FR-091
- FR-110 to FR-114

Key entities:

- `ProfitPattern`
- `ProfitHypothesis`
- `HypothesisEvidence`
- `LearningEvent`
- `UserPreferenceSignal`
- `ReflectionReport`

Phase 1 constraint:

- this module logs and summarises evidence;
- it does not autonomously alter scoring rules.

## 5.5 Inventory Module

Responsibilities:

- purchase decision
- actual purchase
- listing
- sale
- return
- cancellation
- realised profit
- 90-day failure state

Primary requirement coverage:

- FR-100 to FR-104

Key entities:

- `PurchaseRecord`
- `ListingRecord`
- `SaleRecord`
- `NegativeOutcome`
- `InventoryPosition`

## 5.6 Runs Module

Responsibilities:

- exploration run lifecycle
- stages
- progress
- source status
- retries
- errors
- run summary
- rerun modes
- idempotency keys

Primary requirement coverage:

- FR-082 to FR-085
- FR-120 to FR-125

Key entities:

- `ExplorationRun`
- `RunStage`
- `RunProgress`
- `RunError`
- `RunSourceStatus`
- `RunSummary`

## 5.7 Identity and Access Module

Responsibilities:

- shared-password validation
- secure session cookie
- server-side GitHub dispatch authorization

Primary requirement coverage:

- FR-081
- FR-082
- NFR-003

---

# 6. Application Layer Use Cases

Application services orchestrate domain objects and ports.

They shall not contain source-specific parsing.

## 6.1 Exploration Use Cases

- `StartExplorationRun`
- `CollectJimotyProducts`
- `DetectChangedProducts`
- `FilterSourceProducts`
- `AnalyseSelectedProducts`
- `ResearchSelectedProducts`
- `ExploreEcAlternatives`
- `CalculateRecommendations`
- `CompleteExplorationRun`
- `RetryFailedRunItems`
- `RunFullReprocess`

## 6.2 User Interaction Use Cases

- `GetDashboard`
- `GetRunHistory`
- `GetRunDetail`
- `GetCandidateList`
- `GetProductDetail`
- `CorrectProduct`
- `ExcludeComparable`
- `RestoreComparable`
- `RecordPreferenceSignal`
- `RecordResearchValueSignal`
- `RecordPurchase`
- `RecordListing`
- `RecordSale`
- `RecordNegativeOutcome`

## 6.3 Knowledge Use Cases

- `CreateInitialProfitPatterns`
- `RecordLearningEvent`
- `AddHypothesisEvidence`
- `GenerateReflectionReport`

---

# 7. Ports and Adapters

## 7.1 Source Catalog Port

```python
class SourceCatalogProvider(Protocol):
    async def collect(
        self,
        source_config: SourceConfig,
        run_context: RunContext,
    ) -> list[RawSourceProduct]:
        ...
```

Adapters:

- `JimotySpotAdapter`
- `AmazonAdapter`
- `RakutenAdapter`
- `AliExpressAdapter`
- `SheinAdapter`

## 7.2 Vision Provider Port

```python
class VisionProvider(Protocol):
    async def analyse_product(
        self,
        images: list[ImageReference],
        context: ProductAnalysisContext,
    ) -> StructuredProductAnalysis:
        ...
```

Initial adapter:

- `GeminiVisionAdapter`

## 7.3 Marketplace Research Port

```python
class MarketplaceResearchProvider(Protocol):
    async def search(
        self,
        query: MarketplaceSearchQuery,
        limits: ResearchLimits,
    ) -> MarketplaceSearchResult:
        ...
```

Initial adapter:

- `MercariResearchAdapter`

## 7.4 Image Storage Port

```python
class ImageStorage(Protocol):
    async def save(self, image: DownloadedImage, key: str) -> StoredImage:
        ...
```

Initial adapter:

- `SupabaseImageStorage`

## 7.5 Repository Ports

Examples:

- `SourceProductRepository`
- `CanonicalProductRepository`
- `ObservationRepository`
- `ResearchRepository`
- `ComparableRepository`
- `RecommendationRepository`
- `RunRepository`
- `InventoryRepository`
- `LearningRepository`
- `ConfigurationRepository`

## 7.6 Workflow Dispatch Port

```python
class WorkflowDispatcher(Protocol):
    async def dispatch(
        self,
        mode: RunMode,
        requested_by: str,
    ) -> DispatchResult:
        ...
```

Initial adapter:

- `GitHubActionsDispatcher`

---

# 8. Exploration Pipeline

## 8.1 Pipeline Stages

```text
PENDING
  ↓
COLLECTING_SOURCES
  ↓
DETECTING_CHANGES
  ↓
INITIAL_FILTERING
  ↓
VISION_ANALYSIS
  ↓
MERCARI_RESEARCH
  ↓
EC_EXPLORATION
  ↓
CALCULATING
  ↓
REPORTING
  ↓
COMPLETED
```

Alternative terminal states:

- `COMPLETED_WITH_ERRORS`
- `FAILED`
- `CANCELLED`

## 8.2 Stage Isolation

Each stage must:

- persist input identifiers;
- persist progress;
- persist output;
- record errors;
- support bounded retry;
- avoid duplicating completed work.

## 8.3 Normal Incremental Run

```text
1. Create run
2. Collect both Jimoty locations
3. Upsert source identity
4. Append source observations
5. Detect new and changed items
6. Apply lightweight filters
7. Rank research priority
8. Analyse up to configured Gemini limit
9. Rank Mercari research priority
10. Research up to configured Mercari limit
11. Calculate recommendations
12. Determine whether EC exploration is required
13. Generate EC keywords
14. Search EC sources in priority order
15. Evaluate EC candidates
16. Rank all candidates
17. Persist daily summary
18. Complete run
```

## 8.4 Full Re-run

A full re-run may:

- reprocess all current eligible products;
- rerun AI analysis;
- rerun Mercari research;
- recalculate using the latest scoring version.

It must not destroy historical analyses or recommendations.

## 8.5 Failed-Item Retry

The retry mode shall target:

- failed sources;
- failed products;
- failed AI analyses;
- failed research sessions;
- failed report generation.

Already successful independent work shall not be repeated unless necessary.

---

# 9. Alternative EC Exploration Logic

## 9.1 Trigger

EC exploration is triggered when:

- Jimoty produces no recommended candidates;
- Jimoty produces fewer than configured useful candidates;
- configured exploration policy requires a complete daily scan;
- a known high-confidence profit hypothesis warrants active search.

## 9.2 Search Strategy Order

1. historical profit pattern keywords;
2. high-demand Mercari product concepts;
3. current sale and discount concepts.

## 9.3 Source Order

1. Amazon
2. Rakuten
3. AliExpress
4. SHEIN

## 9.4 Search Budget

The application shall track:

- remaining keyword budget;
- remaining AI-analysis budget;
- remaining Mercari-research budget;
- remaining source-request budget.

## 9.5 Stop Conditions

EC exploration stops when:

- all configured sources are attempted;
- keyword budget is exhausted;
- research budget is exhausted;
- source policy prevents further access;
- the run is cancelled.

It shall not stop merely because one profitable item was found.

---

# 10. Data Flow

## 10.1 Product Collection Data Flow

```text
Source Adapter
  → RawSourceProduct
  → validation
  → source identity matching
  → SourceProduct
  → SourceObservation
  → PriceObservation
  → image URL records
```

## 10.2 AI Analysis Data Flow

```text
Candidate Product
  → selected image URLs
  → download
  → storage
  → VisionProvider
  → raw model response
  → schema validation
  → StructuredProductAnalysis
  → canonical product fields
  → research priority recalculation
```

## 10.3 Mercari Research Data Flow

```text
Canonical Product
  → staged queries
  → Mercari adapter
  → raw results
  → normalized MarketplaceListing
  → deterministic candidate ranking
  → Gemini final comparable review
  → ComparableEvidence
  → price and shipping statistics
```

## 10.4 Recommendation Data Flow

```text
Product Evidence
  + Resale Price Evidence
  + Shipping Evidence
  + Fee Configuration
  + Source Cost
  + Demand Evidence
  → deterministic calculators
  → scores
  → tier
  → structured reasons
  → persisted recommendation version
```

## 10.5 Outcome Data Flow

```text
User purchase record
  → listing record
  → sale or failure outcome
  → realised profit
  → learning event
  → hypothesis evidence
  → evaluation dataset
```

---

# 11. Recommendation Calculation Architecture

## 11.1 Calculation Inputs

All calculation inputs shall be represented in a serializable input snapshot.

```json
{
  "sourcing_cost": 1800,
  "estimated_sale_price": 3200,
  "mercari_fee_rule_version": "2026-01",
  "estimated_shipping": 750,
  "sold_comparable_count": 7,
  "active_comparable_count": 5,
  "price_dispersion": 0.12,
  "product_match_confidence": 0.91,
  "shipping_confidence": 0.80,
  "seasonality_score": 72
}
```

## 11.2 Output Snapshot

```json
{
  "expected_profit": 330,
  "return_on_cost": 0.1833,
  "sales_margin": 0.1031,
  "sales_prospect_score": 74,
  "confidence_score": 82,
  "overall_sourcing_score": 69,
  "recommendation_tier": "candidate",
  "scoring_version": "phase1-v1"
}
```

## 11.3 Versioning

Version separately:

- fee rules;
- shipping mappings;
- sales-prospect formula;
- confidence formula;
- overall sourcing formula;
- recommendation thresholds.

A recommendation record must reference all relevant versions.

---

# 12. Manual Correction Architecture

## 12.1 Correction Model

AI-extracted and user-corrected values are separate.

```text
effective_value =
latest_active_user_override
or
latest_validated_ai_value
or
source_value
or
unknown
```

## 12.2 Correction Effects

A correction may trigger:

- canonical product update;
- Mercari query regeneration;
- comparable reranking;
- shipping recalculation;
- profit recalculation;
- score recalculation;
- recommendation version creation.

## 12.3 Comparable Exclusion

Excluding a comparable shall:

1. store a user decision;
2. retain the original comparable;
3. rebuild price statistics;
4. recalculate recommendation;
5. append a recommendation version.

---

# 13. Persistence Architecture

## 13.1 PostgreSQL

Supabase PostgreSQL is the system of record.

Use relational tables for:

- source identities;
- observations;
- products;
- analyses;
- comparables;
- recommendations;
- runs;
- outcomes;
- learning events;
- configuration versions.

## 13.2 Supabase Storage

Use object storage for:

- selected source product images;
- final candidate images;
- optional raw evidence snapshots where legally and technically appropriate.

## 13.3 Append-Only History

The following are append-only or versioned:

- price observations;
- availability observations;
- AI analyses;
- comparable decisions;
- recommendation snapshots;
- score snapshots;
- configuration versions;
- user corrections;
- outcome events;
- learning events.

## 13.4 Current-State Views

For efficient UI queries, create database views or materialized current-state projections such as:

- current product state;
- latest recommendation;
- current source price;
- current active override;
- current inventory status.

Historical records remain authoritative.

---

# 14. API Architecture

## 14.1 API Style

Use REST JSON APIs for Phase 1.

Use explicit command endpoints for state-changing operations.

## 14.2 Endpoint Groups

```text
/auth
/runs
/dashboard
/products
/products/{id}/corrections
/products/{id}/comparables
/products/{id}/recommendations
/products/{id}/feedback
/inventory
/settings
/internal/workflows
```

## 14.3 Query and Command Separation

Queries:

- `GET /dashboard`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /products`
- `GET /products/{product_id}`

Commands:

- `POST /runs/dispatch`
- `POST /products/{id}/corrections`
- `POST /products/{id}/comparables/{comparable_id}/exclude`
- `POST /products/{id}/purchase`
- `POST /products/{id}/sale`

## 14.4 Server-Side Workflow Dispatch

`POST /runs/dispatch` must:

1. validate the shared session;
2. validate requested mode;
3. use server-side GitHub credentials;
4. dispatch the workflow;
5. create or link a pending run record;
6. return a public run identifier.

---

# 15. Frontend Architecture

## 15.1 Rendering Strategy

Use Next.js App Router.

Recommended approach:

- server components for data-heavy read pages;
- client components for interactive corrections, filters, and progress polling;
- server-side proxy/API routes for authenticated commands.

## 15.2 Feature Modules

- dashboard
- run progress
- run history
- product candidate list
- product detail
- comparable review
- correction forms
- inventory lifecycle
- settings

## 15.3 Mobile-First Layout

Core layouts shall prioritize:

- one-column candidate cards;
- concise metrics;
- clear recommendation badge;
- tap-friendly actions;
- collapsible evidence sections;
- no mandatory wide tables.

## 15.4 Progress Updates

Phase 1 may use polling.

Recommended:

- poll every 5–10 seconds while a run is active;
- stop polling at terminal state;
- display last update timestamp.

WebSockets are not required for Phase 1.

---

# 16. Security Architecture

## 16.1 Shared Password

The shared password shall:

- be stored as a server-side environment secret;
- be compared using secure hashing or constant-time comparison;
- create an HTTP-only secure session cookie;
- not be exposed in frontend JavaScript.

## 16.2 Secret Management

Secrets include:

- GitHub token;
- Gemini API key;
- Supabase service-role key;
- shared password;
- source credentials if any.

Secrets are provided through:

- GitHub Actions secrets;
- Vercel environment variables;
- local `.env` files excluded from Git.

## 16.3 Supabase Access

Preferred model:

- frontend never uses the service-role key;
- FastAPI and worker use server-side credentials;
- browser access is limited to authenticated application APIs;
- direct public table access is disabled or tightly restricted.

## 16.4 GitHub Dispatch Token

The GitHub token must:

- be server-side only;
- have the minimum required repository/workflow permission;
- never be returned in API responses;
- never be embedded in browser bundles.

---

# 17. Error and Resilience Architecture

## 17.1 Error Categories

- transient network error
- source blocked
- authentication failure
- parsing error
- schema validation error
- AI provider error
- rate-limit error
- persistence error
- business validation error
- unknown error

## 17.2 Error Record

Each error record shall include:

- run ID;
- stage;
- source;
- product or item ID;
- category;
- retryable flag;
- message;
- technical detail;
- occurred timestamp;
- retry count;
- resolution status.

## 17.3 Retry Policy

Use bounded retries with exponential backoff for retryable failures.

No infinite retry loops.

## 17.4 Circuit Behaviour

When a source repeatedly fails within one run:

- mark source status degraded or failed;
- stop excessive requests;
- continue with other sources;
- report the source failure in the summary.

## 17.5 Transaction Boundaries

Use short transactions.

Do not wrap live HTTP or AI calls in database transactions.

Persist stage checkpoints before and after external calls.

---

# 18. Idempotency Architecture

## 18.1 Source Observation Idempotency

A source observation uses a unique key based on:

- source;
- source item ID;
- observed timestamp or normalized observation window;
- observed price;
- availability state.

## 18.2 AI Analysis Idempotency

Analysis uniqueness may use:

- product ID;
- image set hash;
- prompt version;
- model;
- schema version.

## 18.3 Research Idempotency

Research uniqueness may use:

- product ID;
- normalized query;
- research window;
- provider;
- research configuration version.

## 18.4 Recommendation Idempotency

Recommendation uniqueness may use:

- product ID;
- evidence snapshot hash;
- scoring version.

---

# 19. Configuration Architecture

## 19.1 Configuration Categories

- business thresholds;
- source location definitions;
- source order;
- source request limits;
- AI model and prompt versions;
- analysis limits;
- Mercari search limits;
- evidence period;
- shipping mappings;
- fee rules;
- score formulas;
- recommendation thresholds;
- excluded categories;
- overseas review thresholds;
- delivery-day threshold.

## 19.2 Configuration Sources

Priority order:

1. environment-specific secret variables;
2. database configuration;
3. version-controlled defaults.

## 19.3 Configuration Versioning

Business-significant settings must have a version.

Recommendation snapshots must reference the applicable version.

---

# 20. Observability Architecture

## 20.1 Structured Logging

Use JSON structured logs.

Required fields:

- timestamp;
- level;
- run ID;
- stage;
- module;
- source;
- product ID;
- event code;
- message.

## 20.2 Run Metrics

Store:

- products collected by source;
- new products;
- price changes;
- products filtered;
- AI calls;
- AI failures;
- Mercari searches;
- comparables collected;
- recommendations by tier;
- EC searches by source;
- errors by category;
- duration by stage.

## 20.3 Audit Trail

Audit events include:

- correction created;
- comparable excluded/restored;
- recommendation recalculated;
- purchase recorded;
- sale recorded;
- workflow dispatched;
- configuration changed.

---

# 21. Testing Architecture

## 21.1 Test Layers

### Unit Tests

For:

- fee calculator;
- sourcing cost;
- profit;
- margins;
- median and quartile statistics;
- shipping fallback;
- sales-prospect score;
- confidence score;
- recommendation thresholds;
- duplicate detection;
- price-change detection;
- correction precedence.

### Application Tests

For:

- full use-case orchestration with fake ports;
- partial failure;
- rerun modes;
- alternative exploration;
- comparable exclusion recalculation.

### Adapter Contract Tests

For:

- normalized source product output;
- normalized Mercari listing output;
- Gemini schema output;
- repository behaviour.

### Integration Tests

For:

- PostgreSQL repositories;
- migrations;
- FastAPI routes;
- GitHub dispatch adapter using mocked HTTP.

### End-to-End Tests

For:

- login;
- dashboard;
- start run;
- progress;
- view candidate;
- correct product;
- exclude comparable;
- record purchase and sale.

## 21.2 External-Service Policy

Default CI tests must not depend on:

- live Gemini;
- live Mercari;
- live Jimoty;
- live Amazon;
- live Rakuten;
- live AliExpress;
- live SHEIN.

Use recorded fixtures and fake adapters.

---

# 22. Deployment Architecture

## 22.1 Vercel

Deploy:

- Next.js web application;
- server-side workflow dispatch route if implemented in Next.js.

## 22.2 FastAPI

Phase 1 options:

- deploy FastAPI to a managed service;
- or expose only read/write API through a lightweight backend host.

The architecture must not require FastAPI to stay active during the GitHub Actions worker run, because the worker writes directly through repositories.

## 22.3 GitHub Actions

The exploration workflow:

1. checks out repository;
2. installs Python dependencies;
3. validates configuration;
4. starts or links run record;
5. executes worker CLI;
6. persists results;
7. uploads diagnostic artifacts when needed;
8. exits with success or partial-failure status.

## 22.4 Database

Supabase PostgreSQL is shared by:

- FastAPI;
- GitHub Actions worker;
- migrations;
- administrative tooling.

---

# 23. GitHub Actions Workflow Design

## 23.1 Inputs

```yaml
workflow_dispatch:
  inputs:
    mode:
      type: choice
      options:
        - incremental
        - full
        - retry_failed
    target_run_id:
      required: false
```

## 23.2 Worker Command

```bash
python -m worker.cli explore --mode incremental
```

## 23.3 Concurrency

Use a concurrency group preventing two normal exploration runs from overlapping.

## 23.4 Artifacts

Upload when appropriate:

- run summary JSON;
- failed parser snapshots;
- validation error samples;
- redacted diagnostics.

Do not upload secrets or unnecessary personal data.

---

# 24. External Source Adapter Architecture

## 24.1 Adapter Contract

Each adapter shall provide:

- collection/search entry point;
- normalized outputs;
- rate-limit behaviour;
- retry classification;
- source metadata;
- parser version;
- raw evidence reference where permitted.

## 24.2 Parser Versioning

Store parser version with each collected observation.

When markup changes, historical observations remain interpretable.

## 24.3 Anti-Coupling Rule

No source adapter may call recommendation logic directly.

Adapters return normalized evidence only.

---

# 25. AI Integration Architecture

## 25.1 AI Responsibilities

AI may:

- interpret images;
- extract visible text;
- propose product identity;
- infer condition;
- identify characters;
- generate search terms;
- qualitatively review top comparables;
- draft explanations;
- draft reflection.

## 25.2 AI Prohibitions

AI must not authoritatively calculate:

- profit;
- fee;
- shipping;
- scores;
- recommendation tier.

## 25.3 Schema Validation

All AI outputs must pass strict validation.

On failure:

1. retry with correction prompt if configured;
2. otherwise store raw response and failure;
3. mark analysis unavailable;
4. continue the run.

## 25.4 Provider Replacement

Application code depends on `VisionProvider`, not Gemini SDK directly.

---

# 26. Requirement-to-Module Traceability

| Requirement Range | Primary Module |
|---|---|
| FR-000 | runs, research |
| FR-001–FR-007 | catalog, infrastructure.sources |
| FR-010–FR-015 | recommendation, catalog |
| FR-020–FR-026 | catalog, infrastructure.vision |
| FR-030–FR-039 | research, infrastructure.mercari |
| FR-040–FR-044 | research, recommendation |
| FR-050–FR-057 | recommendation |
| FR-060–FR-066 | recommendation |
| FR-070–FR-077 | research, infrastructure.sources |
| FR-080–FR-091 | api, frontend |
| FR-100–FR-104 | inventory |
| FR-110–FR-114 | learning |
| FR-120–FR-125 | runs, worker |
| FR-130 | catalog, runs, inventory |

---

# 27. Key Architecture Decisions

The following ADRs shall be created.

- ADR-0001 — Modular Monolith
- ADR-0002 — Supabase PostgreSQL
- ADR-0003 — FastAPI and Python Domain Core
- ADR-0004 — Next.js on Vercel
- ADR-0005 — GitHub Actions Worker
- ADR-0006 — LLM Extraction, Deterministic Calculation
- ADR-0007 — Append-Only History
- ADR-0008 — Precision Over Recall

---

# 28. Implementation Order

## Sprint 1 — Foundation

- repository structure;
- configuration;
- logging;
- migrations;
- FastAPI skeleton;
- Next.js skeleton;
- GitHub Actions skeleton;
- shared-password gate.

## Sprint 2 — Catalog

- source-product entities;
- Jimoty adapters;
- observations;
- duplicate detection;
- price history;
- image references.

## Sprint 3 — AI Analysis

- Gemini adapter;
- schema validation;
- prompt versioning;
- image storage;
- structured product analysis.

## Sprint 4 — Mercari Research

- query generation;
- Mercari adapter;
- normalized listings;
- comparable ranking;
- manual exclusion model;
- price and shipping evidence.

## Sprint 5 — Recommendation

- financial calculations;
- scores;
- reason components;
- recommendation tiers;
- recalculation.

## Sprint 6 — EC Exploration

- Amazon;
- Rakuten;
- AliExpress;
- SHEIN;
- alternative exploration loop;
- source-specific policies.

## Sprint 7 — Web UI

- dashboard;
- progress;
- run history;
- candidate list;
- detail;
- corrections;
- comparable review.

## Sprint 8 — Outcomes and Learning

- purchase;
- listing;
- sale;
- negative outcomes;
- preference feedback;
- learning events;
- initial profit hypotheses.

## Sprint 9 — Hardening

- integration tests;
- end-to-end tests;
- error recovery;
- observability;
- documentation consistency;
- deployment validation.

---

# 29. Architecture Acceptance Criteria

The architecture is accepted when:

1. every P0 requirement maps to a module and use case;
2. external services are behind ports;
3. domain calculations run without live services;
4. history is preserved;
5. manual corrections trigger versioned recalculation;
6. the worker tolerates independent source failure;
7. the UI can operate without privileged browser secrets;
8. the same domain packages are reusable by FastAPI and the worker;
9. no source-specific parser exists in the domain layer;
10. all business-significant calculations reference versioned configuration.

---

# 30. Open Architecture Questions

The following remain for later documents or ADRs:

1. exact FastAPI hosting provider;
2. exact Mercari data-access method and constraints;
3. exact Amazon, Rakuten, AliExpress, and SHEIN access methods;
4. whether source collection uses HTTP parsing, browser automation, or mixed adapters;
5. whether `pgvector` is introduced in Phase 1;
6. image retention schedule for non-candidates;
7. precise review and seller-rating thresholds;
8. exact formulas for sales-prospect, confidence, and sourcing scores;
9. exact database row-level-security policy;
10. exact shared-session implementation.

These questions do not block the overall module architecture.
