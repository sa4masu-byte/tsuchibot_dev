# CODEX.md — Tsuchibot Implementation Guide

## 1. Your Role

You are implementing **Tsuchibot**, a sourcing-decision and profit-opportunity discovery agent.

Read these documents before making architectural or domain changes:

1. `docs/00_Project.md`
2. `docs/01_Principles.md`
3. `docs/02_Requirements.md`
4. `docs/03_Architecture.md`
5. the document specific to the area you are changing

If two documents conflict, stop and report the conflict before implementing domain behaviour.

## 2. Product Mission

Tsuchibot helps the user discover products that may be sourced and resold on Mercari profitably.

It must:

- identify products worth researching;
- use Mercari evidence;
- calculate conservative profit;
- minimize false-positive recommendations;
- explain all important decisions;
- continue with alternative search strategies when initial sources produce no useful candidates;
- preserve data required for future learning.

Tsuchibot is not an automatic purchasing system.

## 3. Highest Priorities

When trade-offs are necessary, use this order:

1. correctness of financial calculations
2. avoidance of unsafe or misleading recommendations
3. traceability and reproducibility
4. explainability
5. maintainability
6. replaceability of external integrations
7. performance
8. cosmetic polish

## 4. Core Technical Rules

### 4.1 LLM boundary

LLMs may extract or interpret information.

LLMs must not be the authoritative calculator for:

- fees
- shipping
- profit
- margins
- sales prospect score
- confidence
- recommendation tier
- ranking

These must be implemented as deterministic, tested domain logic.

### 4.2 Manual corrections

Manual corrections override AI-extracted values.

Never discard the original AI output.

### 4.3 Historical data

Do not overwrite price, state, score, or decision history where the previous value has analytical value.

Use append-only history tables or explicit version records for historical facts.

### 4.4 Unknown data

Never turn unknown data into a confident fact.

Use explicit `unknown`, nullable fields, confidence reductions, and user-review flags.

### 4.5 External integrations

All source-specific behaviour must be behind adapters.

Domain services must not import scraper-specific, Gemini-specific, Supabase-specific, or GitHub-specific modules.

## 5. Preferred Architecture

Use a modular monolith with domain-oriented boundaries.

Suggested backend structure:

```text
backend/
  app/
    api/
    application/
    domain/
      catalog/
      research/
      recommendation/
      learning/
      inventory/
      runs/
    infrastructure/
      database/
      storage/
      vision/
      sources/
      mercari/
      github/
    shared/
```

Suggested frontend structure:

```text
frontend/
  src/
    app/
    components/
    features/
      dashboard/
      runs/
      products/
      comparables/
      corrections/
      inventory/
      settings/
    lib/
```

Do not create microservices during Phase 1.

## 6. Domain Behaviour Requirements

### 6.1 New products

A source product is normally new when its source item ID has not been seen.

Listing dates are supporting evidence, not the sole identifier.

### 6.2 Price changes

A previously seen product with a changed price must:

1. receive a new price-history record;
2. be reevaluated;
3. be surfaced again if its recommendation improves or it newly meets minimum conditions.

### 6.3 Mercari evidence

Default Phase 1 evidence:

- previous three months
- at least three sufficiently comparable sold listings
- median sold price of condition-similar products
- sold and active results retained for sell-through analysis
- each comparable can be manually excluded

### 6.4 Profit

The required Phase 1 profit formula is:

```text
profit = estimated_sale_price
         - mercari_fee
         - estimated_resale_shipping
         - sourcing_cost
```

Do not include labour, storage, transportation, or packing material in Phase 1 calculations unless requirements are updated.

### 6.5 Recommendation strategy

Prioritize precision over recall.

The system may reject or defer uncertain items.

Recommendations must include:

- expected profit
- profit margin on sourcing cost
- 90-day sales prospect score
- confidence
- reasons
- risks
- evidence summary

### 6.6 Recommendation tiers

Use four tiers:

- strongly recommended
- recommended
- candidate
- reject

Thresholds belong in versioned configuration, not scattered constants.

## 7. Testing Rules

Domain calculation logic requires automated tests.

At minimum, test:

- fee calculation
- shipping fallback order
- profit calculation
- margin calculation
- comparable filtering
- median-price selection
- minimum-comparable rule
- confidence reductions
- recommendation thresholds
- price-change reevaluation
- manual override precedence
- partial-run failure handling

Use fixtures for external integrations.

Do not require live scraping or live LLM calls in the default test suite.

## 8. Security Rules

Never commit or expose:

- GitHub tokens
- Gemini API keys
- Supabase service-role keys
- access passwords
- private source credentials

Browser code must never receive privileged secrets.

Web-triggered GitHub Actions must be dispatched through a server-side endpoint.

## 9. Error Handling

One failed adapter or product must not terminate an entire exploration run unless continuation would corrupt data.

Record:

- source
- stage
- item ID when applicable
- exception category
- retryability
- user-visible summary
- technical details
- timestamp

Continue with independent stages and sources.

## 10. Observability

Each exploration run must have:

- run ID
- trigger source
- current stage
- progress numerator and denominator
- start and finish times
- per-source results
- errors
- LLM-call counts
- selected model names
- approximate usage when available
- final summary

## 11. Database Changes

Every schema change must include:

- migration
- updated database documentation
- repository updates
- tests
- rollback or forward-fix notes

Avoid direct database access from UI components.

## 12. Definition of Done

A feature is complete only when:

- behaviour matches documented requirements;
- domain logic is tested;
- errors are handled;
- important decisions are explainable;
- manual corrections are preserved where relevant;
- documentation is updated;
- secrets are not exposed;
- linting and type checks pass;
- the feature can be demonstrated without undocumented manual database edits.

## 13. Working Method

For a large task:

1. read the relevant documents;
2. inspect the current implementation;
3. state assumptions and detected conflicts;
4. propose a small implementation plan;
5. implement in coherent commits;
6. run tests and quality checks;
7. summarize changed files, tests, migrations, and remaining limitations.

Do not silently redesign major domain behaviour.

## 14. Prohibited Shortcuts

Do not:

- let an LLM return the final profit number without deterministic recalculation;
- hard-code secrets;
- overwrite useful history;
- hide uncertainty;
- mix scraper parsing with recommendation rules;
- treat a sales-prospect score as a calibrated probability;
- mark a feature complete without tests for its core domain behaviour;
- automatically purchase an item;
- fabricate unavailable marketplace evidence.

## 15. Tsuchibot Personality

Tsuchibot should behave like an experienced reseller who explains their reasoning.

It should not behave like an oracle that only gives answers.

When uncertain, it should say what is unknown, explain why it matters, and identify the most useful next confirmation.
