# 仕入れ判断エージェント Tsuchibot
## 04_Domain.md — Phase 1 Domain Model

- Document version: 0.1
- Scope: Phase 1
- Related requirements: FR-001–FR-130
- Related architecture: `03_Architecture.md`

---

# 1. Domain Objective

The domain model represents the complete lifecycle of a sourcing opportunity:

```text
source observation
→ product understanding
→ market research
→ recommendation
→ user correction
→ purchase
→ listing
→ sale or failure
→ learning evidence
```

The domain shall preserve both what Tsuchibot believed at a given time and what actually happened later.

---

# 2. Bounded Modules

## 2.1 Catalog

Owns source identity, observations, canonical products, product images, AI-extracted facts, user corrections, duplicate decisions, and price-change decisions.

## 2.2 Research

Owns search queries, Mercari listings, comparable evidence, inclusion or exclusion decisions, price statistics, shipping statistics, and sold-rate evidence.

## 2.3 Recommendation

Owns calculation inputs, financial outputs, 90-day sales prospect score, confidence, overall sourcing score, recommendation tier, and structured reasons.

## 2.4 Inventory

Owns purchase, listing, sale, return, cancellation, unsold-after-90-days outcome, and realised profit.

## 2.5 Learning

Owns profit patterns, hypotheses, user-interest feedback, research-value feedback, learning events, and reflection reports.

## 2.6 Runs

Owns run lifecycle, stages, progress, source status, retries, errors, rerun modes, and run summaries.

---

# 3. Core Aggregates

## 3.1 SourceProduct

Represents one product identity on one sourcing site.

Business identity:

```text
(source_type, source_item_id)
```

Core fields:

- source type
- source location
- source item ID
- canonical URL
- first and last seen timestamps
- current availability
- current price
- parser version

Rules:

1. Historical observations are append-only.
2. Current price is derived from the latest valid price observation.
3. Duplicate decisions retain their evidence.
4. Price decreases trigger reevaluation.

## 3.2 CanonicalProduct

Represents Tsuchibot's best current understanding of the item.

Core fields:

- display name
- category
- manufacturer
- brand
- model number
- character
- size
- color
- condition
- new/used state
- estimated original-price band

Effective-value precedence:

```text
active user correction
> latest validated AI extraction
> source-provided value
> unknown
```

Rules:

1. Unknown remains explicit.
2. User corrections never delete AI output.
3. Uncertain model numbers may retain multiple candidates.
4. Effective values must be traceable.

## 3.3 ResearchSession

Represents one Mercari research attempt for one product and one evidence period.

Contains:

- staged search queries
- query executions
- normalized marketplace listings
- comparable evidence
- research errors

Rules:

1. Every comparable originates from a recorded query or manual addition.
2. Research failure is not a business rejection.
3. Query order and evidence period are retained.
4. Active and sold listings remain distinct.

## 3.4 Recommendation

Represents one versioned sourcing decision.

Contains:

- exact input snapshot
- estimated sale price
- estimated shipping
- Mercari fee
- sourcing cost
- expected profit
- margins
- 90-day sales prospect score
- confidence
- overall sourcing score
- recommendation tier
- structured reasons and risks
- scoring and rule versions

Rules:

1. Financial values are deterministic outputs.
2. Recommendation history is append-only.
3. Manual corrections create a new recommendation version.
4. A recommendation without reasons is invalid.
5. Weak evidence cannot produce high confidence without explicit justification.

## 3.5 InventoryPosition

Tracks what happened after recommendation.

Contains:

- purchased quantity
- purchase amount
- listing events
- sale events
- return and cancellation events
- realised profit
- 90-day failure state

Rules:

1. Sold quantity cannot exceed purchased quantity.
2. Actual values never overwrite predicted values.
3. Realised profit uses actual purchase, fee, shipping, and sale values.

## 3.6 ProfitHypothesis

Represents a versioned belief such as “replacement remote controls can be profitable.”

Fields:

- statement
- type
- scope
- category
- brand or character
- source
- season
- confidence
- state
- supporting and contradicting evidence

States:

- active
- narrowed
- disproven
- archived

Rules:

1. Hypotheses are not silently deleted.
2. Confidence changes require evidence and reason.
3. Previous scope and confidence remain traceable.

## 3.7 ExplorationRun

Coordinates one execution.

Contains:

- mode
- trigger
- status
- current stage
- progress
- source statuses
- errors
- metrics
- summary

Rules:

1. A run has one mode.
2. Partial source failure does not force full failure.
3. Stage progress is monotonic.
4. Duplicate completion is idempotent.

---

# 4. Value Objects

## Money

- integer yen
- no binary floating-point arithmetic
- decimal or integer calculations only

## ConfidenceScore

Range 0–100.

Represents evidence reliability, not profit probability.

## SalesProspectScore

Range 0–100.

Represents a heuristic 90-day sales prospect, not a calibrated probability.

## SourcingScore

Range 0–100.

Represents overall ranking under a versioned formula.

## ProductCondition

- new
- unused
- like_new
- good
- fair
- poor
- junk
- unknown

## RecommendationTier

- strongly_recommended
- recommended
- candidate
- reject

## ComparableDecision

- included
- excluded_by_rule
- excluded_by_user
- pending_review

---

# 5. Domain Services

## DuplicateDetectionService

Evaluation order:

1. exact source item ID
2. canonical URL
3. image hash, price, and location
4. title, image, and attribute similarity

Uncertain matches must not be silently merged.

## PriceChangeDetectionService

Outputs:

- unchanged
- decreased
- increased
- newly available
- unavailable

Every meaningful change is historical evidence. A price decrease triggers recalculation.

## ResearchPriorityService

Combines deterministic signals with AI-extracted attributes:

- brand or manufacturer
- new condition
- character
- product recency
- estimated original price
- seasonality
- known profit pattern
- dirt penalty
- large-shipping penalty

AI may supply attributes but not final arithmetic.

## ComparableRankingService

Category-specific weighting:

### Model-number products

- model number
- manufacturer
- title
- image
- condition

### Character goods

- character
- item type
- design
- size
- condition
- image

### Clothing

- brand
- new condition
- item type
- size
- season
- image

### Craft kits

- kit identity
- contents
- brand
- completeness
- condition

## PriceEvidenceService

Rules:

1. default evidence period is 90 days
2. normal recommendation requires three sold comparables
3. condition-similar median is the primary estimate
4. lower quartile and dispersion are retained
5. excluded comparables do not contribute
6. research failure does not imply zero market value

## ShippingEvidenceService

Fallback order:

1. same-product median
2. similar-product median
3. standard shipping mapping
4. unknown

Every estimate includes amount, source type, evidence count, confidence, and reason.

## ProfitCalculator

```text
expected_profit =
estimated_sale_price
- mercari_fee
- estimated_resale_shipping
- sourcing_cost
```

Phase 1 excludes labour, packaging materials, travel, storage, cleaning, repair, and risk reserves.

## SalesProspectScorer

Possible inputs:

- sold count
- active count
- sold-rate heuristic
- price competitiveness
- product similarity
- seasonality
- hypothesis evidence
- EC delivery time

Outputs a score and structured components.

## ConfidenceScorer

Possible inputs:

- product identity confidence
- model confidence
- comparable count
- comparable similarity
- price dispersion
- condition confidence
- shipping confidence
- authenticity confidence

## RecommendationClassifier

Configuration-driven.

Default minimum candidate requirement:

```text
expected_profit >= 300 JPY
```

Normal recommendation additionally expects:

```text
sales_prospect_score >= 70
```

Insufficient evidence may force downgrade.

## Phase 1 Recommendation Formula (`phase1-v1`)

All monetary calculations use integer yen. The standard Mercari fee uses a versioned 10% rule and
rounds fractional yen down. Shipping follows same-product median, similar-product median, exact
method mapping, then unknown. Unknown price or shipping never becomes zero for profit calculation.
The July 2026 defaults were verified against the official
[Mercari fee guide](https://help.jp.mercari.com/guide/articles/65/) and
[Mercari shipping guide](https://help.jp.mercari.com/guide/articles/652/). Oversized specialist
shipping remains an unresolved risk rather than reusing the standard fee assumption confidently.

The sales-prospect score is a 0–100 heuristic, not a probability:

- sold volume within the evidence period: 30 points, capped at 10 sales;
- retrieved-evidence sold-rate: 30 points;
- average comparable similarity: 20 points;
- price competitiveness: 10 points;
- seasonality: 5 points;
- hypothesis evidence: 3 points;
- EC delivery evidence: 2 points.

Only non-excluded sold evidence with a sold timestamp, or a conservative listing-time upper bound,
inside the configured evidence period contributes to sold volume and sold rate.

Confidence weights are identity 20, model 15, sufficient comparable count 25, comparable similarity
15, price dispersion 10, condition 5, shipping 5, and authenticity 5. Missing evidence contributes
zero rather than a neutral assumption.

Overall sourcing score weights are profit 25, return on cost 20, sales prospect 25, confidence 20,
and research priority 10, with 15 points removed per major unresolved risk up to 30 points.

Strong recommendation requires at least JPY 1,000 profit, 50% return on cost, sales prospect 70,
confidence 80, sufficient comparables, and no major risk. Recommendation requires at least JPY 500
profit, sales prospect 70, confidence 65, sufficient comparables, and no major risk. Profit of at
least JPY 300 may remain a candidate. Missing calculable profit or profit below JPY 300 is rejected
with structured confirmation or negative reasons; technical research failure remains a separate
research status.

---

# 6. State Machines

## Product Processing

```text
unanalysed
→ initially_filtered
→ detailed_analysis_in_progress
→ detailed_analysis_complete
→ research_in_progress
→ research_complete
→ calculated
```

Exceptional states:

- analysis_unavailable
- research_unavailable

## Recommendation

```text
not_calculated
→ strongly_recommended
→ recommended
→ candidate
→ reject
```

Recalculation creates a new version.

## Inventory

```text
not_purchased
→ purchased
→ listed
→ partially_sold
→ sold
```

Alternative outcomes:

- returned
- cancelled
- unsold_90_days
- damaged
- lost

## Run

```text
pending
→ running
→ completed
```

Alternative terminal states:

- completed_with_errors
- failed
- cancelled

---

# 7. Domain Events

Suggested events:

- SourceProductCollected
- SourceProductDetectedAsNew
- SourcePriceChanged
- ProductSelectedForDetailedAnalysis
- ProductAnalysisCompleted
- ProductAnalysisFailed
- ResearchSessionStarted
- ComparableIncluded
- ComparableExcluded
- ResearchCompleted
- RecommendationCalculated
- RecommendationTierChanged
- UserCorrectionApplied
- ProductPurchased
- ProductListed
- ProductSold
- ProductReturned
- ProductMarkedUnsoldAfter90Days
- LearningEventRecorded
- HypothesisEvidenceAdded
- RunStageCompleted
- RunCompletedWithErrors

Phase 1 may persist these as audit or learning events without a distributed event bus.

---

# 8. Domain Policies

## Precision Policy

When uncertainty is high, downgrade, request confirmation, or reject.

## Unknown Policy

Unreadable or uncertain values remain unknown.

## History Policy

Prices, observations, AI results, corrections, comparable decisions, recommendations, and outcomes remain available.

## Human Override Policy

User corrections override AI values for future calculations while preserving AI history.

## Price Opportunity Policy

Previously rejected products may reappear after a price decrease.

## No Forced Recommendation Policy

A run may validly finish with zero recommended products after all configured exploration paths are attempted.

---

# 9. Initial Profit Patterns

## Replacement Products

Examples:

- remote controls
- replacement filters

Signals:

- explicit need
- niche search
- low shipping
- low sourcing price

## Character Goods

Examples:

- Hello Kitty
- keychains
- plush toys

Signals:

- collection demand
- overseas demand
- gift demand

Authenticity remains mandatory.

## New Clothing

Examples:

- shirts
- undershirts

Signals:

- new
- branded
- easy condition verification

## Craft Kits

Signals:

- clear target buyer
- completeness
- hobby demand
- compact shipping

## Seasonal Goods

Example:

- folding fans

Signals:

- demand growth before warm season
- seasonal evidence may compensate for weak off-season recency

---

# 10. Domain Acceptance Criteria

1. Source identity and product identity are distinct.
2. Historical observations are immutable.
3. User overrides preserve AI output.
4. Recommendation versions are append-only.
5. Deterministic calculators use no live service.
6. Research failure is separate from rejection.
7. Outcomes preserve original predictions.
8. Hypotheses preserve confidence history.
9. Price decreases trigger reevaluation.
10. Unknown cannot be represented as confirmed.
