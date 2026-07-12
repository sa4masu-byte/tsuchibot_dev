# Tsuchibot Development Principles

## 1. Mission First

Tsuchibot is not a generic price-prediction tool.

Tsuchibot is a **profit opportunity discovery agent**.

Every implementation decision must support reliable sourcing decisions, conservative profit estimation, continuous exploration, and explainable recommendations.

## 2. Precision Over Recall

Phase 1 prioritizes precision.

It is acceptable to miss some profitable products.

It is not acceptable to recommend many products that later become losses or long-term inventory.

Recommendation thresholds shall therefore be conservative and configurable.

## 3. Human Decision, Machine Assistance

Tsuchibot assists the user.

It does not replace the user.

The system may:

- discover candidates
- extract product information
- research comparable sales
- estimate profit
- calculate scores
- identify risks
- explain recommendations
- propose alternative searches

The system must not automatically purchase products during Phase 1.

## 4. LLMs Extract; Deterministic Code Calculates

LLMs may be used for:

- image understanding
- OCR-like text extraction
- product categorization
- manufacturer and model candidates
- condition interpretation
- character identification
- search-term generation
- qualitative reasoning
- explanation drafting

Deterministic Python code shall calculate:

- fees
- shipping estimates
- expected profit
- profit margin
- 90-day sales prospect score
- confidence score
- recommendation tier
- ranking score

LLM output must never be accepted as the authoritative result of a financial calculation.

## 5. Explain Every Decision

Every important score must have reasons.

Every recommendation must have reasons.

Every rejection must have reasons.

Examples:

- `manufacturer_match: +15`
- `new_item: +20`
- `popular_character: +10`
- `heavy_soiling: -30`
- `large_shipping_risk: -25`
- `insufficient_comparables: confidence -20`

A user must be able to understand how a recommendation was produced.

## 6. Preserve History

History is knowledge.

Do not overwrite important historical facts.

Preserve:

- source prices over time
- availability over time
- AI-extracted values
- user-corrected values
- score versions
- recommendation versions
- Mercari comparable sets
- profit hypothesis updates
- purchase and sales outcomes
- execution logs
- errors

Current values may be materialized for convenience, but the underlying history must remain traceable.

## 7. Manual Corrections Override AI Values

AI-extracted values and user-corrected values shall both be stored.

When a user corrects:

- product name
- manufacturer
- model number
- condition
- shipping cost
- comparable-product relevance
- resale-price assumption

the corrected value becomes authoritative for subsequent calculations.

The original AI output must remain available for audit and future model evaluation.

## 8. Reproducible Decisions

Every recommendation must be reproducible from stored inputs and a versioned scoring configuration.

Store at least:

- source data
- selected images
- AI model and prompt version
- comparable listings
- calculation inputs
- rule and score version
- resulting explanation
- execution timestamp

A recommendation without traceable inputs is invalid.

## 9. Fail Softly

Failure of one source, listing, image, or analysis step must not stop the entire exploration run.

Examples:

- if one Jimoty Spot fails, continue with the other;
- if Amazon fails, continue with Rakuten and other sources;
- if one Gemini analysis fails, mark only that product as failed;
- if Mercari research fails, record the product as `research_unavailable`.

Partial results are better than no results.

## 10. Do Not Invent Certainty

Unknown values must remain unknown.

Examples:

- unreadable model number
- unclear product condition
- unknown shipping method
- questionable authenticity
- insufficient sold evidence

The system must lower confidence, request user confirmation, or classify the item as not sufficiently researched.

It must not fill missing facts with plausible guesses.

## 11. Search Broadly, Analyse Selectively

Use inexpensive filters before expensive analysis.

Default Phase 1 limits:

- fetch all new Jimoty products
- perform lightweight filtering on all fetched products
- perform detailed Gemini analysis on up to 30 products
- perform detailed Mercari research on up to 20 products
- use up to 20 EC search keywords
- present up to 10 final candidates

These limits must be configurable.

## 12. Price Changes Are Opportunities

The same source product must not be treated as irrelevant merely because it has already been seen.

When the price changes:

- append a price-history record;
- recalculate profitability;
- update recommendation status;
- surface the product again if it newly meets recommendation criteria.

A price reduction that creates a profitable opportunity must not be missed.

## 13. Conservative Market Evidence

Phase 1 resale estimates use:

- Mercari only
- sold evidence from the previous three months
- at least three sufficiently comparable sold listings
- the median price of condition-similar items

Comparable listings must be reviewable and manually excludable.

## 14. Shipping Evidence Hierarchy

Estimate resale shipping cost in this order:

1. median shipping evidence from the same product;
2. median shipping evidence from similar products;
3. standard shipping amount associated with the identified shipping method.

If shipping cannot be estimated responsibly, confidence must decrease.

## 15. Recommendation Tiers

Phase 1 uses four recommendation tiers:

1. Strongly Recommended
2. Recommended
3. Candidate
4. Reject

Thresholds must be configurable.

The default minimum conditions include:

- expected profit of at least ¥300
- use of both profit amount and return on cost
- 90-day sales prospect score of at least 70 for normal recommendations
- sufficient confidence and comparable evidence

## 16. Learning Starts With Logging

Do not begin with an unnecessarily complex model.

First collect high-quality events:

- viewed
- selected for research
- skipped
- user says “want”
- user says “slightly interested”
- user says “do not want”
- user says “worth researching”
- purchased
- listed
- sold
- returned
- cancelled
- realized price
- realized shipping cost
- realized profit

Reliable logs are the foundation for future ranking and learning.

## 17. Hypotheses Are Versioned Beliefs

Initial knowledge such as “Hello Kitty sells” or “replacement remote controls can be profitable” must be stored as hypotheses.

A hypothesis has:

- scope
- statement
- confidence
- supporting evidence
- contradicting evidence
- source
- created time
- update history

Do not silently delete failed hypotheses.

Reduce confidence, mark them disproven, or narrow their scope.

## 18. Security by Default

Secrets must never be exposed to the browser or committed to the repository.

Examples:

- GitHub token
- Supabase service-role key
- Gemini API key
- scraper credentials
- shared access password

Use environment variables and server-side API routes.

## 19. Respect Source Constraints

Scraping implementations must:

- minimize request volume;
- use caching and deduplication;
- support rate limiting;
- stop or degrade gracefully when blocked;
- isolate source-specific adapters;
- avoid coupling domain logic to page markup.

Source terms, technical restrictions, and permitted access methods may change. Each adapter must be replaceable.

## 20. Prefer Replaceable Integrations

External services must be accessed through interfaces.

Examples:

- `VisionProvider`
- `MarketplaceResearchProvider`
- `SourceCatalogProvider`
- `ImageStorage`
- `ProductRepository`
- `RunRepository`

Gemini, Supabase, GitHub Actions, or a specific scraper implementation must not leak into core domain logic.

## 21. Documentation Before Behavioural Change

A change affecting domain behaviour must update the relevant documentation before or with the implementation.

At minimum, update:

- requirements
- architecture
- domain rules
- API contract
- database design
- tests

Code and documentation must not knowingly contradict each other.

## 22. Phase 1 Simplicity

Use the simplest design that preserves future replaceability and traceability.

Avoid:

- premature microservices
- premature event sourcing everywhere
- premature machine learning
- unnecessary multi-agent orchestration
- speculative abstractions with no Phase 1 use

A modular monolith with clear boundaries is preferred.
