# Tsuchibot

## 1. Project Name

**仕入れ判断エージェント Tsuchibot**

Tsuchibot is a product-pricing and profit-opportunity discovery agent. It supports fair-price
decisions for products managed by Jimoty Spot and sourcing decisions for a separately operated
retail business.

## 2. Background

The user manages Jimoty operations and uses product and market evidence to set appropriate store
prices, including as one measure to discourage purchases made primarily for resale. Separately,
the user operates a retail business and identifies promising EC products by reviewing product
images and making an intuitive judgement based on experience.

Typical signals include:

- manufacturer or brand
- visible wear and condition
- whether the product appears recent
- whether the original retail price appears high
- whether it features a popular character
- whether it is new or unused
- whether the product is heavily soiled
- whether the product is large and likely to incur high shipping costs
- seasonality
- personal appeal: whether the user would want the product

After a product is selected for investigation, the user checks comparable sold listings on Mercari and calculates potential profit.

Tsuchibot shall support and gradually formalize this workflow.

## 3. Mission

Tsuchibot does not merely predict resale prices.

Its mission is to:

1. discover products worth investigating;
2. research Mercari sales evidence;
3. support appropriate Jimoty Spot price setting without treating those products as sourcing
   opportunities;
4. estimate conservative profit and sales prospects for separately operated retail sourcing;
5. explain why a price or sourcing decision is supported;
6. continue looking for alternatives when no good retail opportunity is found;
7. accumulate knowledge from successes, failures, corrections, and user feedback.

## 4. Desired Agent Behaviour

A desirable daily response is:

> No profitable products were found at the two nearby Jimoty Spot locations today.
> Instead, Amazon is currently discounting Product X. Based on recent Mercari evidence, the estimated profit margin is 35%, the 90-day sales prospect score is 82, and the estimated profit is ¥720.

Tsuchibot must not force recommendations. However, when the first search path produces no useful candidates, it should attempt other reasonable search strategies within the configured exploration budget.

## 5. Phase 1 Business Targets

- Monthly profit target: **¥30,000**
- Target sales volume: **60 items per month**
- Minimum expected profit per item: **¥300**
- Initial monthly purchasing budget: **¥50,000**
- A product remaining unsold for 90 days is treated as a failed sourcing decision
- Precision is prioritized over recall
- Missing some profitable products is acceptable
- Recommending loss-making products should be minimized

## 6. Phase 1 Sourcing Priority

1. Nearby Jimoty Spot location 1
2. Nearby Jimoty Spot location 2
3. Amazon
4. Rakuten
5. AliExpress
6. SHEIN

## 7. Primary Product Categories

- baby products
- hobby products
- branded new clothing
- small appliances

Products aimed primarily at specialist or enthusiast markets, such as cameras, should not be prioritized during Phase 1.

## 8. Initial Profit Patterns

The following user experiences shall be registered as initial hypotheses rather than permanent truths:

### Replacement and maintenance products

Examples:

- remote controls
- replacement filters

Observed pattern:

- niche but explicit demand
- low sourcing price
- relatively low competition
- low shipping cost
- potentially attractive margin

### Character goods

Examples:

- Hello Kitty
- keychains
- plush toys
- other character goods

Observed pattern:

- domestic and overseas demand
- gift and collection demand
- lightweight products often have favorable shipping economics

### New clothing

Examples:

- new shirts
- new undershirts

Observed pattern:

- easier condition assessment
- easier listing
- lower hygiene concerns than used clothing

### Craft kits

Observed pattern:

- clear target buyer
- hobby demand
- product contents are usually easy to identify

### Seasonal products

Example:

- folding fans

Observed pattern:

- demand may rise before and during warm seasons

## 9. Phase 1 Operating Model

- Manual execution approximately once per day
- GitHub Actions `workflow_dispatch` is the primary execution method
- A web button may trigger the same workflow through a secure server-side GitHub API call
- Results must be viewable from a smartphone
- Next.js is deployed to Vercel
- FastAPI and Python implement scraping, AI integration, market research, and domain logic
- Supabase PostgreSQL stores persistent data
- Supabase Storage stores selected product images
- A simple shared-password gate may be used in Phase 1
- Purchasing remains a human decision
- Tsuchibot does not automatically buy products

## 10. Success Metrics

Tsuchibot shall be evaluated primarily by business outcomes:

- monthly realized profit
- recommendation precision
- rate of loss-making purchases
- 90-day sell-through rate
- average realized profit
- inventory age
- accuracy of shipping estimates
- usefulness of explanations
- improvement of profit hypotheses over time

Price-prediction accuracy alone is not the primary success criterion.

## 11. Non-Goals for Phase 1

Phase 1 does not aim to:

- automate purchasing
- guarantee profit
- provide a statistically calibrated sales probability
- cover every product category
- perform unrestricted full-site crawling
- replace user judgement
- build a fully autonomous multi-agent organization
- use a complex machine-learning model before sufficient data exists

## 12. Long-Term Vision

Over time, Tsuchibot should become a personalized sourcing knowledge system that understands:

- which products deserve investigation
- which sourcing sites work best for each product pattern
- which seasonal opportunities are emerging
- which recommendations were correct or incorrect
- which products the user personally finds attractive
- how sourcing price, shipping, condition, and demand interact

The long-term asset is not only the software. It is the accumulated, traceable sourcing knowledge.
