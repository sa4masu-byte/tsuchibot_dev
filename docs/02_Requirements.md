# 仕入れ判断エージェント Tsuchibot
## 02_Requirements.md — Phase 1 Requirements Specification

- Document version: 0.2
- Scope: Phase 1
- Status: Draft for architecture review
- Primary implementation audience: Codex and human reviewers

---

# 1. Introduction

## 1.1 Purpose

This document defines the Phase 1 requirements for **仕入れ判断エージェント Tsuchibot**.

Tsuchibot supports the user in identifying products that may be purchased from local or online sources and resold on Mercari for profit.

The system shall not merely estimate prices. It shall:

1. identify products worth researching;
2. research recent Mercari evidence;
3. calculate conservative profit;
4. rank opportunities;
5. explain recommendation reasons and risks;
6. continue searching alternative sources when the initial search produces insufficient opportunities;
7. accumulate data for future improvement.

## 1.2 Design Manifesto

Tsuchibot is designed to augment human intuition, not replace it.

The objective is not to automate sourcing.

The objective is to transform sourcing experience into reusable and continuously improving knowledge.

Every recommendation should teach the user something.

Every correction should teach Tsuchibot something.

## 1.3 Phase 1 Operating Assumptions

- The system is executed approximately once per day.
- Real-time monitoring is not required.
- Accuracy is prioritized over speed.
- The user manually makes all purchase decisions.
- The system may be run from GitHub Actions or triggered from the web application.
- Results must be viewable from a smartphone.
- Existing code is not reused; implementation starts from a new repository.
- Phase 1 is implemented as a modular monolith.
- Phase 1 prioritizes recommendation precision over recall.

## 1.4 Requirement Priority

Each functional requirement has one of the following priorities.

- **P0**: essential for Phase 1 release
- **P1**: important for Phase 1 but may be deferred if a source limitation blocks implementation
- **P2**: useful enhancement; implementation may follow after core workflow is stable

---

# 2. Business Objectives

## BO-001 Monthly Profit Target

The initial monthly realized-profit target is **JPY 30,000**.

## BO-002 Monthly Sales Target

The initial target sales volume is **60 sold products per month**.

## BO-003 Minimum Product Profit

A product must have an expected profit of at least **JPY 300** to qualify as a candidate.

The system shall also distinguish higher-value products:

- minimum candidate: JPY 300 or more
- recommended target: JPY 500 or more
- strong-profit indicator: JPY 1,000 or more

These thresholds shall be configurable.

## BO-004 Purchasing Budget

The initial monthly sourcing budget is approximately **JPY 50,000**.

Phase 1 does not need to optimize a purchase portfolio against this limit.

The application may display actual purchasing totals, but strict budget blocking is out of scope.

## BO-005 Inventory Failure Definition

A sourced product that remains unsold for **90 days** is considered a failed sourcing decision for evaluation purposes.

## BO-006 Risk Preference

Tsuchibot shall prefer:

- fewer recommendations with higher reliability;
- lower false-positive purchase recommendations;
- explicit uncertainty;
- conservative market assumptions.

Missing some profitable products is acceptable.

---

# 3. Actors and External Systems

## ACT-001 User

The user:

- starts exploration runs;
- reviews recommendations;
- corrects extracted information;
- excludes incorrect Mercari comparables;
- records purchases and sales outcomes;
- provides personal-interest and research-value feedback;
- makes all final purchase decisions.

## ACT-002 Tsuchibot

Tsuchibot:

- collects source products;
- filters products;
- invokes AI analysis;
- researches Mercari evidence;
- searches EC sites;
- calculates financial metrics;
- ranks products;
- provides explanations;
- stores evidence and history.

## ACT-003 GitHub Actions

GitHub Actions is the primary Phase 1 execution environment for exploration runs.

## ACT-004 Next.js Web Application

The Next.js application:

- displays results;
- displays run progress;
- enables corrections and outcome entry;
- may trigger GitHub Actions securely through a server-side endpoint.

## ACT-005 FastAPI Backend

FastAPI provides application APIs and Python-based orchestration interfaces.

## ACT-006 Supabase

Supabase provides:

- PostgreSQL persistence;
- image storage;
- database management support.

## ACT-007 Gemini

Gemini is the initial image and language analysis provider.

Google AI Pro subscription benefits shall not be assumed to include Gemini API billing or API quotas.

Model and provider configuration shall be replaceable.

## ACT-008 Source Sites

Phase 1 source priority:

1. nearby Jimoty Spot location 1;
2. nearby Jimoty Spot location 2;
3. Amazon;
4. Rakuten;
5. AliExpress;
6. SHEIN.

## ACT-009 Mercari

Mercari is the only resale marketplace used for Phase 1 market evidence.

---

# 4. Domain Terms

## 4.1 Source Product

A product listed on a sourcing site.

## 4.2 Comparable Listing

A Mercari listing used as evidence for resale price, demand, condition, or shipping.

## 4.3 Sold Comparable

A comparable listing shown as sold.

## 4.4 Active Comparable

A comparable listing still available for purchase.

## 4.5 Research Priority Score

A score used to decide which source products deserve detailed analysis.

## 4.6 90-Day Sales Prospect Score

A Phase 1 heuristic score indicating the relative likelihood of a product selling within 90 days.

It is not a statistically calibrated probability and must not be labelled as one.

## 4.7 Confidence Score

A score representing the reliability of the product identification, comparable evidence, shipping estimate, and calculated recommendation.

## 4.8 Profit Hypothesis

A versioned belief about a product pattern, brand, character, category, source, season, or demand characteristic that may lead to profitable sourcing.

## 4.9 Profit Pattern

A reusable structure associated with sourcing opportunity, such as:

- replacement products;
- character goods;
- new clothing;
- craft kits;
- seasonal goods.

---

# 5. End-to-End Business Workflow

## 5.1 Daily Exploration Flow

1. A user starts an exploration run.
2. The system collects newly discovered products from both configured Jimoty Spot locations.
3. The system detects price changes for previously seen products.
4. All new and relevant changed products pass through lightweight filtering.
5. The highest-priority products receive detailed Gemini analysis.
6. The highest-priority analysed products receive Mercari research.
7. The system calculates resale price, shipping estimate, profit, margin, sales prospect, confidence, and recommendation tier.
8. The system searches EC sites using:
   1. known profit patterns;
   2. Mercari demand evidence;
   3. sale and discount opportunities.
9. EC candidates receive the same Mercari and profit evaluation.
10. All candidates are ranked using the overall sourcing score.
11. The system generates a daily result summary.
12. The user reviews and corrects results.
13. Purchase and resale outcomes are recorded over time.

## 5.2 Alternative Exploration Requirement

### FR-000 — Continue Alternative Exploration
**Priority: P0**

When the initial Jimoty exploration produces no acceptable recommendation, or produces too few useful candidates, Tsuchibot shall continue exploring alternative sources and search hypotheses within the configured exploration budget.

The system shall not fabricate or force a recommendation.

The final result may state that no acceptable candidate was found after all configured exploration paths were attempted.

### Acceptance Criteria

- The run does not end solely because both Jimoty locations return no recommended products.
- Amazon is searched before Rakuten, AliExpress, and SHEIN.
- The system records which alternative strategies were attempted.
- The report distinguishes “no opportunity found” from “source could not be researched.”

---

# 6. Source Product Collection Requirements

## FR-001 — Collect Jimoty Spot Products
**Priority: P0**

The system shall collect product listings from two separately configured nearby Jimoty Spot locations.

### Required fields when available

- source name;
- source location ID;
- source item ID;
- source URL;
- title;
- displayed price;
- image URLs;
- displayed category;
- listing timestamp;
- collection timestamp;
- availability status.

### Acceptance Criteria

- Both configured locations are processed independently.
- Failure at one location does not prevent processing the other.
- Collected items are persisted before detailed analysis.

## FR-002 — Detect New Jimoty Products
**Priority: P0**

A source item shall normally be considered new when its source item ID has not previously been stored.

Listing timestamp may be used as supporting information but shall not be the sole identifier.

## FR-003 — Detect Duplicate Products
**Priority: P0**

Duplicate detection shall use the following order:

1. identical source item ID;
2. identical canonical source URL;
3. image hash, price, and location combination;
4. high similarity of title, image, price, and source.

Potential duplicates shall not be silently merged if confidence is insufficient.

## FR-004 — Detect and Preserve Price Changes
**Priority: P0**

For a previously seen source product, a changed price shall:

1. create a new price-history record;
2. retain the previous price;
3. trigger recalculation of profit and recommendation;
4. resurface the product if it newly satisfies recommendation conditions.

A price change is a business opportunity and must not be ignored.

## FR-005 — Price-Change Re-notification
**Priority: P0**

A changed product shall be re-notified only when the new calculation satisfies or improves the recommendation condition.

A one-yen decrease alone does not require notification.

## FR-006 — Store EC Price and Availability History
**Priority: P1**

For EC products, the system shall retain daily or observed price and availability history.

At minimum:

- product;
- shop or seller;
- displayed price;
- shipping;
- coupon value;
- availability;
- observed timestamp.

## FR-007 — Source Adapter Isolation
**Priority: P0**

Each source site shall be implemented behind a source adapter interface.

Domain logic must not depend on site-specific HTML or CSS selectors.

---

# 7. Initial Filtering and Research Prioritization

## FR-010 — Lightweight Initial Filtering
**Priority: P0**

All collected Jimoty products shall first pass through deterministic lightweight filtering using available title, price, category, and source data.

Items that cannot be confidently classified by rules may receive a lightweight Gemini analysis.

## FR-011 — Positive Initial Signals
**Priority: P0**

The initial rules shall support positive indicators including:

- known manufacturer or brand;
- popular character;
- new or unused wording;
- replacement product;
- consumable or maintenance item;
- craft kit;
- branded clothing;
- seasonal product;
- historically successful profit pattern.

## FR-012 — Negative Initial Signals
**Priority: P0**

The initial rules shall support negative indicators including:

- severe visible or stated soiling;
- excessively large product;
- high shipping-risk product;
- excluded category;
- prohibited or unsafe product;
- unclear authenticity where authenticity matters.

## FR-013 — Research Priority Score
**Priority: P0**

Research priority shall combine:

- deterministic rule score;
- profit-pattern evidence;
- brand or manufacturer score;
- new-condition score;
- popular-character score;
- product recency;
- estimated original price band;
- seasonality;
- Gemini qualitative score;
- dirt or damage penalty;
- large-shipping-risk penalty.

The score calculation shall be deterministic once AI-extracted inputs are provided.

## FR-014 — Consumer Appeal Reference Score
**Priority: P2**

Gemini may generate reference values for:

- general consumer appeal;
- visual attractiveness;
- gift demand;
- whether a typical consumer may want the product.

These values are advisory only and shall not independently determine recommendation.

## FR-015 — Configurable Analysis Limits
**Priority: P0**

Default run limits:

- all newly collected Jimoty products: initial filtering;
- up to 30 products: detailed Gemini analysis;
- up to 20 products: detailed Mercari research;
- up to 20 EC search keywords;
- up to 10 final displayed candidates.

All limits shall be configurable.

---

# 8. Image and AI Analysis Requirements

## FR-020 — Detailed Image Analysis
**Priority: P0**

Gemini shall analyse selected product images and return structured output.

### Target fields

- inferred product category;
- manufacturer;
- brand;
- model-number candidates;
- visible text;
- character;
- new or used;
- condition observations;
- visible wear;
- visible dirt;
- approximate size class;
- apparent product recency;
- estimated original-price band;
- relevant search terms;
- analysis confidence by field;
- uncertainty notes.

## FR-021 — Structured AI Output
**Priority: P0**

AI responses shall conform to a versioned JSON schema.

Invalid output shall be retried or marked as analysis failure.

## FR-022 — AI Prompt and Model Versioning
**Priority: P0**

Each AI analysis record shall include:

- provider;
- model;
- prompt version;
- schema version;
- execution timestamp;
- raw response;
- parsed result;
- validation status.

## FR-023 — Unknown and Ambiguous Values
**Priority: P0**

Unreadable or uncertain values shall be stored as unknown or as multiple candidates.

The system shall not silently select an uncertain model number.

## FR-024 — Image Storage
**Priority: P0**

Image storage behaviour:

- initially store source image URLs;
- save images for detailed-analysis products to Supabase Storage;
- retain final-candidate images long-term;
- support future cleanup of non-candidate images.

## FR-025 — OCR Strategy
**Priority: P1**

Phase 1 may use Gemini as the initial OCR-like image-text extraction method.

A dedicated OCR provider is not required for initial release.

The design shall permit future addition of a dedicated OCR adapter.

## FR-026 — AI Usage Logging
**Priority: P0**

Each run shall record:

- number of AI calls;
- selected model;
- successful and failed calls;
- approximate usage or cost when available.

---

# 9. Mercari Research Requirements

## FR-030 — Generate Mercari Search Queries
**Priority: P0**

Search queries shall be generated in stages.

Default stages:

1. exact model number;
2. manufacturer and model number;
3. series and product type;
4. manufacturer and product type;
5. similarity-oriented query.

The maximum number of stages and searches shall be configurable.

## FR-031 — Collect Sold and Active Results
**Priority: P0**

For each query, the system shall collect sold and active Mercari results.

Default maximum collection:

- up to 50 sold results;
- up to 50 active results.

Limits shall be configurable.

## FR-032 — Restrict Evidence Period
**Priority: P0**

Sold-price evidence shall primarily use results from the previous **three months**.

Older results may be stored but must not be used as normal Phase 1 pricing evidence unless explicitly configured.

## FR-033 — Minimum Sold Comparable Count
**Priority: P0**

Normal recommendation requires at least **three sufficiently comparable sold listings within three months**.

If fewer than three are available:

- confidence shall be reduced;
- the item may remain a candidate;
- it shall not be presented as having strong market evidence.

## FR-034 — Comparable Matching
**Priority: P0**

Comparable similarity shall use:

- model number;
- product title;
- manufacturer or brand;
- image similarity;
- condition;
- size;
- color;
- capacity;
- character;
- product-specific attributes.

The implementation shall:

1. use code to retrieve and rank candidates;
2. use Gemini only for final evaluation of selected high-ranking comparables.

## FR-035 — Category-Specific Similarity
**Priority: P0**

Similarity rules shall differ by category.

Examples:

- model-number products: emphasize model and manufacturer;
- character products: emphasize character, item type, size, design, and condition;
- clothing: emphasize brand, new condition, type, size, and season;
- craft kits: emphasize kit identity, contents, brand, and completeness.

## FR-036 — Manual Comparable Exclusion
**Priority: P0**

The product detail screen shall display comparables used in calculation.

The user shall be able to mark a comparable as irrelevant.

Exclusion shall trigger recalculation.

## FR-037 — Comparable Evidence Display
**Priority: P0**

Each comparable display shall include, when available:

- image;
- title;
- sold or active status;
- displayed price;
- condition;
- shipping method;
- shipping responsibility;
- sale date;
- similarity score;
- whether included in calculation;
- exclusion reason.

## FR-038 — Mercari Special Listing Rules
**Priority: P0**

- Shipping-included listings may be used normally.
- Cash-on-delivery listings may be used only when shipping can be corrected.
- Bundle listings may be used only when a defensible per-item price can be derived.
- Parts and junk listings may be used only when the source product has the same condition.
- Buyer-reserved or dedicated listings may be used with reduced confidence.

## FR-039 — Sold-Rate Heuristic
**Priority: P0**

Phase 1 may calculate a simplified sold-rate indicator:

```text
sold_count /
(sold_count + current_active_count)
```

The displayed label must make clear that this is a heuristic based on retrieved evidence.

---

# 10. Resale Price and Shipping Requirements

## FR-040 — Resale Price Estimate
**Priority: P0**

The Phase 1 estimated resale price shall use the **median sold price of condition-similar comparables** from the preceding three months.

## FR-041 — Conservative Evidence Handling
**Priority: P0**

The estimate shall not use a simple average when outliers are present.

The implementation shall retain:

- median;
- lower quartile;
- minimum;
- maximum;
- comparable count;
- price dispersion.

The normal Phase 1 profit calculation uses the condition-similar median, while lower-quartile information is displayed as risk evidence.

## FR-042 — Resale Shipping Estimate
**Priority: P0**

Shipping shall be estimated in this order:

1. median evidence from the same product;
2. median evidence from similar products;
3. standard shipping amount associated with identified shipping method.

## FR-043 — Shipping Uncertainty
**Priority: P0**

When shipping cannot be estimated responsibly:

- shipping status shall be unknown;
- confidence shall decrease;
- the item may be downgraded or require confirmation.

## FR-044 — Mercari Fee
**Priority: P0**

Mercari selling fee shall be calculated deterministically from a configurable rule.

The rule shall not be embedded in AI prompts.

---

# 11. Financial Calculation Requirements

## FR-050 — Expected Profit
**Priority: P0**

Phase 1 expected profit:

```text
expected_profit =
estimated_sale_price
- mercari_fee
- estimated_resale_shipping
- sourcing_cost
```

Phase 1 excludes:

- labour;
- packing materials;
- travel;
- storage;
- cleaning;
- repair;
- return-risk reserve.

## FR-051 — Sourcing Cost
**Priority: P0**

For EC products:

```text
sourcing_cost =
displayed_price
+ sourcing_shipping
- definitely_applicable_coupon
```

Points shall not reduce sourcing cost.

## FR-052 — Point Display
**Priority: P1**

Amazon or Rakuten points may be displayed as reference information only.

They shall not affect Phase 1 expected profit.

## FR-053 — Overseas Displayed Currency
**Priority: P0**

For AliExpress and SHEIN:

- site-displayed Japanese-yen price shall be preferred;
- original currency and amount shall be stored when available;
- actual charged amount may be recorded after purchase.

## FR-054 — Profit Margin
**Priority: P0**

The application shall calculate and store both:

```text
return_on_cost = profit / sourcing_cost
sales_margin = profit / estimated_sale_price
```

The primary displayed profit rate shall be return on sourcing cost.

## FR-055 — Multi-Quantity Evaluation
**Priority: P1**

The system may evaluate purchases of up to **four units**.

For each quantity from one to four, it may calculate:

- total sourcing cost;
- total expected profit;
- per-unit profit;
- inventory exposure.

Recommendations must not assume more than four units.

## FR-056 — EC Price Detail
**Priority: P0**

Store separately:

- displayed product price;
- sourcing shipping;
- definite coupon;
- point reference value;
- calculated sourcing cost;
- actual purchase amount.

## FR-057 — Rakuten Shop Comparison
**Priority: P1**

For the same product, Rakuten research shall:

- rank using price, shipping, shop review, and delivery date;
- select the practical lowest-cost offer;
- retain and display the top three offers.

---

# 12. Demand, Confidence, and Recommendation Requirements

## FR-060 — 90-Day Sales Prospect Score
**Priority: P0**

Phase 1 shall calculate a heuristic **90-day sales prospect score** using:

- sold count in the previous three months;
- active listing count;
- sold-rate heuristic;
- price competitiveness;
- product similarity;
- brand or character history;
- profit-hypothesis evidence;
- seasonality;
- EC delivery time.

The score shall not be described as a calibrated probability.

## FR-061 — Default Sales Prospect Threshold
**Priority: P0**

The default recommendation threshold is a 90-day sales prospect score of **70 or more**.

The threshold shall be configurable and may be lowered if practical operation produces too few useful recommendations.

## FR-062 — Confidence Score
**Priority: P0**

Confidence shall combine:

- product-identification confidence;
- model-number confidence;
- comparable count;
- comparable similarity;
- price dispersion;
- condition confidence;
- shipping confidence;
- authenticity confidence.

## FR-063 — Overall Sourcing Score
**Priority: P0**

The default ranking shall use an overall sourcing score combining:

- expected profit;
- return on sourcing cost;
- 90-day sales prospect score;
- confidence;
- research-priority score;
- risk deductions.

The exact formula shall be versioned and configurable.

## FR-064 — Four Recommendation Tiers
**Priority: P0**

The system shall classify each evaluated product into:

1. strongly recommended;
2. recommended;
3. candidate;
4. reject.

Default concepts:

### Strongly Recommended

- high expected profit;
- sales prospect score at least 70;
- high confidence;
- strong comparable evidence;
- no major unresolved risk.

### Recommended

- expected profit normally at least JPY 500;
- sales prospect score at least 70;
- sufficient confidence.

### Candidate

- expected profit at least JPY 300;
- uncertainty or incomplete evidence remains.

### Reject

- minimum conditions not met;
- prohibited product;
- expected loss;
- excessive uncertainty;
- unacceptable shipping or authenticity risk.

Exact thresholds shall be configurable.

## FR-065 — Recommendation Explanations
**Priority: P0**

Each recommendation shall display:

- positive reasons;
- negative reasons;
- evidence counts;
- important assumptions;
- unresolved uncertainties;
- user confirmation requests.

## FR-066 — Deterministic Reason Components
**Priority: P0**

Reason components shall be stored as structured data, for example:

```json
{
  "code": "POPULAR_CHARACTER",
  "label": "Popular character",
  "value": "Hello Kitty",
  "score_delta": 10,
  "source": "vision_analysis"
}
```

Explanations may be converted into natural language, but the underlying reasons must remain structured.

---

# 13. EC Exploration Requirements

## FR-070 — EC Search Priority
**Priority: P0**

EC search order:

1. Amazon;
2. Rakuten;
3. AliExpress;
4. SHEIN.

## FR-071 — EC Search Strategy
**Priority: P0**

EC search shall use this priority:

1. known profit patterns and successful historical keywords;
2. products with strong Mercari demand;
3. current sales, discounts, and clearance opportunities.

## FR-072 — EC Keyword Budget
**Priority: P0**

Default maximum EC search keywords per run: **20**.

The limit shall be configurable.

## FR-073 — Overseas Delivery Limit
**Priority: P0**

AliExpress and SHEIN products must indicate delivery within **seven days** to qualify for normal recommendation.

Products exceeding this period may be rejected or downgraded.

## FR-074 — Overseas Seller Quality
**Priority: P0**

AliExpress and SHEIN candidates shall require configurable minimum:

- product-review count;
- product rating;
- seller rating.

Exact threshold values shall be stored in configuration.

## FR-075 — Overseas Product Policy
**Priority: P0**

Phase 1 may consider new and unbranded overseas products when other requirements are satisfied.

Character or branded products must be excluded unless authenticity or authorization is sufficiently supported.

## FR-076 — Similar EC Products
**Priority: P1**

An EC product need not be an exact match to Mercari evidence.

Similar products may be evaluated, but:

- confidence shall decrease;
- the similarity basis shall be explained;
- exact-match evidence shall be distinguished from category-level evidence.

## FR-077 — Excluded Product Types
**Priority: P0**

Phase 1 shall exclude:

- food;
- medicine;
- cosmetics;
- supplements;
- batteries and rechargeable batteries;
- mains-connected electrical products;
- branded or character goods of uncertain authenticity.

---

# 14. User Interface Requirements

## FR-080 — Smartphone-Compatible Web UI
**Priority: P0**

The application shall be usable from a smartphone browser.

## FR-081 — Shared Password Gate
**Priority: P0**

Phase 1 shall use a simple shared-password access gate.

The password shall be stored as a server-side environment secret.

The UI shall use a secure session cookie after successful access.

## FR-082 — Start Exploration
**Priority: P0**

The user shall be able to start an exploration run through:

- GitHub Actions `workflow_dispatch`;
- optionally, the web application.

The web application shall trigger GitHub Actions through a server-side endpoint.

The GitHub token must never be exposed to browser code.

## FR-083 — Run Progress
**Priority: P0**

The UI shall display:

- overall progress percentage;
- current stage;
- completed and total item count;
- error count;
- start time;
- current run status.

Stages:

- product collection;
- initial filtering;
- Gemini analysis;
- Mercari research;
- EC exploration;
- calculation;
- report generation.

## FR-084 — Run History
**Priority: P0**

The user shall be able to view previous runs, statuses, summaries, and errors.

## FR-085 — Daily Summary
**Priority: P0**

The dashboard shall display:

- strongly recommended count;
- recommended count;
- candidate count;
- rejected count;
- research-unavailable count;
- total candidate sourcing cost;
- total expected profit;
- average sales prospect score;
- best candidate;
- Jimoty candidates;
- EC candidates;
- newly observed profit-pattern evidence;
- errors and incomplete research.

## FR-086 — Candidate List
**Priority: P0**

The concise list shall show:

- product image or summary;
- product name;
- sourcing price;
- estimated sale price;
- expected profit;
- 90-day sales prospect score;
- confidence;
- recommendation tier.

## FR-087 — Sorting
**Priority: P0**

Default sorting: overall sourcing score descending.

The user shall also be able to sort by:

- expected profit;
- confidence;
- 90-day sales prospect score;
- sourcing price;
- observed time.

## FR-088 — Product Detail
**Priority: P0**

The product detail page shall show:

- source data;
- source price history;
- AI-extracted data;
- corrected data;
- product images;
- Mercari search queries;
- comparables;
- price statistics;
- shipping estimate and evidence;
- profit calculation;
- score components;
- recommendation reasons;
- risks;
- user feedback;
- purchase and sale outcomes.

## FR-089 — Manual Corrections
**Priority: P0**

The user shall be able to correct:

- product name;
- manufacturer;
- brand;
- model number;
- category;
- new or used;
- condition;
- shipping estimate;
- estimated resale price;
- comparable relevance.

A correction shall trigger deterministic recalculation.

## FR-090 — Personal Appeal Feedback
**Priority: P1**

The user may record:

- want;
- slightly interested;
- do not want;
- cannot judge.

## FR-091 — Research Value Feedback
**Priority: P1**

The user may record:

- worth researching;
- not worth researching.

---

# 15. Purchase and Sales Outcome Requirements

## FR-100 — Record Purchase Decision
**Priority: P0**

The user shall be able to record:

- purchased or not purchased;
- purchase date;
- actual purchase quantity;
- actual purchase price;
- actual sourcing shipping;
- actual coupon;
- actual charged amount;
- notes.

## FR-101 — Record Listing
**Priority: P0**

The user shall be able to record:

- listing date;
- listing price;
- marketplace;
- listing URL;
- quantity listed.

## FR-102 — Record Sale
**Priority: P0**

The user shall be able to record:

- sold date;
- sold price;
- actual selling fee;
- actual shipping cost;
- quantity sold;
- realised profit.

## FR-103 — Record Negative Outcomes
**Priority: P0**

The user shall be able to record:

- return;
- cancellation;
- unsold after 90 days;
- damaged;
- lost;
- other failure reason.

## FR-104 — Preserve Prediction and Outcome
**Priority: P0**

Predicted and actual values shall both be retained for evaluation.

---

# 16. Profit Knowledge Requirements

## FR-110 — Initial Profit Patterns
**Priority: P0**

Initial hypotheses shall include:

### Replacement and maintenance items

- remote controls;
- replacement filters.

### Character goods

- Hello Kitty;
- keychains;
- plush toys;
- character goods with domestic or overseas demand.

### New clothing

- new shirts;
- new undershirts;
- branded new clothing.

### Craft products

- craft kits.

### Seasonal products

- folding fans.

## FR-111 — Hypothesis Data
**Priority: P1**

Each profit hypothesis shall support:

- statement;
- type;
- scope;
- applicable category;
- brand or character;
- source site;
- season;
- confidence;
- supporting evidence count;
- contradictory evidence count;
- origin;
- created timestamp;
- update history;
- active, narrowed, disproven, or archived state.

## FR-112 — Do Not Delete Hypothesis History
**Priority: P1**

A hypothesis shall not be silently deleted.

Confidence may be reduced, scope may be narrowed, or state may change.

## FR-113 — Learning Event Log
**Priority: P0**

The system shall record events including:

- collected;
- filtered;
- selected for detailed analysis;
- skipped;
- selected for Mercari research;
- user marked worth researching;
- user marked not worth researching;
- user appeal feedback;
- recommended;
- rejected;
- purchased;
- listed;
- sold;
- returned;
- cancelled;
- unsold after 90 days;
- manually corrected.

## FR-114 — Reflection Report
**Priority: P2**

The system may produce a daily reflection summarising:

- what was searched;
- what was found;
- what failed;
- which patterns appeared promising;
- which searches were unproductive;
- suggested focus for the next run.

Reflection is advisory and must not directly modify core scoring configuration without review.

---

# 17. Execution, Resilience, and Re-run Requirements

## FR-120 — Manual GitHub Actions Run
**Priority: P0**

The exploration workflow shall support `workflow_dispatch`.

## FR-121 — Re-run Modes
**Priority: P0**

The system shall support:

1. normal incremental run;
2. full run;
3. retry failed stages or items.

## FR-122 — Partial Failure
**Priority: P0**

Failure of one source, product, comparable, or AI call shall not stop independent work.

## FR-123 — Research-Unavailable Status
**Priority: P0**

When a product cannot be researched because of technical failure, it shall be marked `research_unavailable`, not rejected for business reasons.

## FR-124 — Retry Policy
**Priority: P1**

Transient failures shall use configurable bounded retries with backoff.

Permanent parsing or policy failures shall be recorded without uncontrolled retry loops.

## FR-125 — Idempotent Processing
**Priority: P0**

Reprocessing the same source item within a run or repeated workflow shall not create duplicate canonical products or duplicate history events beyond intended observations.

---

# 18. Product Lifecycle Status Requirements

## FR-130 — Product Statuses
**Priority: P0**

The system shall support statuses equivalent to:

- unanalysed;
- initially filtered;
- detailed analysis in progress;
- market research complete;
- strongly recommended;
- recommended;
- candidate;
- rejected;
- research unavailable;
- purchased;
- listed;
- sold;
- returned;
- cancelled.

Technical processing status and business recommendation status should be represented separately when practical.

---

# 19. Non-Functional Requirements

## NFR-001 Explainability
**Priority: P0**

Every recommendation and rejection must be explainable from stored evidence and structured reason components.

## NFR-002 Reproducibility
**Priority: P0**

A recommendation must be reproducible using:

- stored source observation;
- selected images;
- AI output;
- model and prompt versions;
- comparable set;
- exclusions;
- calculation configuration;
- scoring version.

## NFR-003 Security
**Priority: P0**

Secrets must not be exposed to browser code or committed to the repository.

## NFR-004 Maintainability
**Priority: P0**

External integrations shall be replaceable through adapters.

## NFR-005 Testability
**Priority: P0**

Core calculations shall be executable without live external services.

## NFR-006 Mobile Usability
**Priority: P0**

Core screens shall support typical smartphone widths.

## NFR-007 Performance
**Priority: P1**

No strict real-time SLA is required.

A daily run may take several minutes.

The system shall expose progress while processing.

## NFR-008 Observability
**Priority: P0**

Each run shall have:

- run ID;
- trigger;
- stage;
- progress;
- timestamps;
- source metrics;
- AI metrics;
- errors;
- final summary.

## NFR-009 Data Preservation
**Priority: P0**

Historical prices, observations, corrections, predictions, and outcomes shall be retained.

## NFR-010 Configurability
**Priority: P0**

The following shall be configurable:

- source locations;
- model names;
- prompt versions;
- analysis limits;
- comparable limits;
- minimum sold count;
- evidence period;
- score thresholds;
- fee rule;
- shipping mappings;
- EC review thresholds;
- delivery-time threshold;
- excluded categories.

## NFR-011 Source Courtesy
**Priority: P0**

Source adapters shall support caching, deduplication, bounded request rates, and graceful degradation.

## NFR-012 Documentation Consistency
**Priority: P0**

Changes to domain behaviour require documentation and test updates.

---

# 20. Phase 1 Exclusions

The following are explicitly out of scope for Phase 1:

- automatic purchasing;
- automated seller messaging;
- resale listing automation;
- statistically calibrated sales probability;
- computer-vision model training;
- portfolio optimization against the monthly budget;
- unrestricted crawling of all products on all sites;
- food, medical, cosmetic, supplement, battery, and mains-electrical sourcing;
- uncertain counterfeit or unlicensed character goods;
- real-time continuous monitoring;
- multi-user account management;
- native mobile application;
- complex multi-agent consensus;
- autonomous score-threshold modification.

---

# 21. Acceptance Criteria for Phase 1 Release

Phase 1 is acceptable when all P0 criteria below are satisfied.

## AC-001 Run

- A GitHub Actions manual run can be started.
- Two Jimoty Spot locations are processed.
- Source failures do not stop independent processing.
- Progress and result status are persisted.

## AC-002 Product Discovery

- New products are detected.
- Previously seen products are not duplicated.
- Price changes are preserved and reevaluated.

## AC-003 Analysis

- Up to the configured number of products receive structured Gemini analysis.
- Unknown values remain explicitly unknown.
- AI output is versioned.

## AC-004 Mercari Research

- Sold and active results are collected.
- Comparables are ranked.
- The user can exclude incorrect comparables.
- Normal recommendations require at least three comparable sold results in three months.

## AC-005 Calculation

- Fees, sourcing cost, shipping, profit, margins, sales-prospect score, confidence, and recommendation tier are calculated deterministically.
- Calculation tests pass.

## AC-006 EC Exploration

- Amazon, Rakuten, AliExpress, and SHEIN are represented by isolated adapters.
- Alternative EC exploration occurs when Jimoty results are insufficient.
- Overseas delivery and seller-quality rules are applied.

## AC-007 UI

- The user can view the dashboard and candidate list from a smartphone.
- The user can view details, evidence, reasons, and risks.
- The user can correct product data and comparables.
- The user can view run history and errors.

## AC-008 Outcome Logging

- Purchases, listings, sales, shipping, returns, cancellations, and actual profit can be recorded.
- Predictions and actual outcomes are both preserved.

## AC-009 Security

- Secrets remain server-side.
- The application is protected by a shared-password gate.
- The GitHub token is not exposed to browser code.

## AC-010 Documentation

- Requirements, architecture, database, API, frontend, AI, scraping, and test documents match implemented behaviour.

---

# Appendix A — Default Configuration

```yaml
business:
  monthly_profit_target_jpy: 30000
  monthly_sales_target: 60
  minimum_expected_profit_jpy: 300
  recommended_profit_jpy: 500
  strong_profit_jpy: 1000
  inventory_failure_days: 90

exploration:
  detailed_vision_limit: 30
  mercari_research_limit: 20
  ec_keyword_limit: 20
  final_candidate_limit: 10

mercari:
  evidence_days: 90
  minimum_sold_comparables: 3
  sold_result_limit: 50
  active_result_limit: 50

recommendation:
  sales_prospect_threshold: 70
  tiers:
    - strongly_recommended
    - recommended
    - candidate
    - reject

ec:
  source_order:
    - amazon
    - rakuten
    - aliexpress
    - shein
  overseas_delivery_days_max: 7
  maximum_purchase_quantity: 4
```

All values shall be overrideable through configuration.

---

# Appendix B — Initial User Intuition Signals

## Positive

- known manufacturer;
- low visible wear;
- appears recent;
- appears to have had a high original retail price;
- popular character;
- new or unused.

## Negative

- severe dirt;
- product is too large;
- likely high shipping cost.

## Personal Feedback

- want;
- slightly interested;
- do not want;
- cannot judge;
- worth researching;
- not worth researching.

---

# Appendix C — Traceability Rule

Future architecture, API, database, frontend, AI, scraping, and test documents shall reference requirement IDs from this document.

Example:

```text
FR-004 -> price_observations table
FR-036 -> comparable exclusion API
FR-083 -> run progress endpoint
FR-104 -> prediction_outcome evaluation model
```
