# 仕入れ判断エージェント Tsuchibot
## 05_Database.md — Phase 1 Database Design

- Document version: 0.1
- Database: Supabase PostgreSQL
- Storage: Supabase Storage
- Related domain: `04_Domain.md`

---

# 1. Database Principles

1. PostgreSQL is the system of record.
2. Historical observations are append-only.
3. Current state is derived from history and active overrides.
4. AI output and user correction are stored separately.
5. Prediction and outcome are stored separately.
6. Business calculations reference versioned configuration.
7. Financial amounts use integer yen.
8. UUID primary keys are preferred.
9. All timestamps are timezone-aware UTC.
10. Secrets are never stored in business tables.

---

# 2. Logical Schemas

```text
catalog
research
recommendation
inventory
learning
runs
config
audit
```

If multiple schemas complicate Supabase tooling, equivalent prefixed tables may be used in `public`.

---

# 3. Catalog Tables

## `catalog.source_products`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| source_type | text | controlled value |
| source_location_id | text nullable | |
| source_item_id | text | source business ID |
| canonical_url | text | |
| parser_version | text | |
| first_seen_at | timestamptz | |
| last_seen_at | timestamptz | |
| current_availability | text | projection |
| current_price_jpy | integer nullable | projection |
| created_at | timestamptz | |
| updated_at | timestamptz | |

Unique:

```text
(source_type, source_item_id)
```

## `catalog.source_observations`

| Column | Type |
|---|---|
| id | uuid PK |
| source_product_id | uuid FK |
| run_id | uuid FK |
| observed_at | timestamptz |
| title | text nullable |
| displayed_category | text nullable |
| displayed_price_jpy | integer nullable |
| availability | text |
| raw_metadata | jsonb |
| raw_snapshot_ref | text nullable |
| parser_version | text |
| idempotency_key | text unique |
| created_at | timestamptz |

Append-only.

## `catalog.price_observations`

| Column | Type |
|---|---|
| id | uuid PK |
| source_product_id | uuid FK |
| run_id | uuid FK |
| amount_jpy | integer |
| price_type | text |
| observed_at | timestamptz |
| change_from_previous_jpy | integer nullable |
| change_rate | numeric nullable |
| created_at | timestamptz |

## `catalog.availability_observations`

| Column | Type |
|---|---|
| id | uuid PK |
| source_product_id | uuid FK |
| run_id | uuid FK |
| availability | text |
| observed_at | timestamptz |
| created_at | timestamptz |

## `catalog.product_images`

| Column | Type |
|---|---|
| id | uuid PK |
| source_product_id | uuid FK |
| source_url | text |
| storage_path | text nullable |
| content_hash | text nullable |
| width | integer nullable |
| height | integer nullable |
| image_order | integer |
| retention_class | text |
| first_seen_at | timestamptz |
| created_at | timestamptz |

## `catalog.canonical_products`

| Column | Type |
|---|---|
| id | uuid PK |
| display_name | text nullable |
| category | text nullable |
| manufacturer | text nullable |
| brand | text nullable |
| model_number | text nullable |
| character_name | text nullable |
| size_text | text nullable |
| color | text nullable |
| condition | text |
| is_new | boolean nullable |
| estimated_original_price_min_jpy | integer nullable |
| estimated_original_price_max_jpy | integer nullable |
| effective_version | integer |
| created_at | timestamptz |
| updated_at | timestamptz |

## `catalog.source_product_links`

| Column | Type |
|---|---|
| id | uuid PK |
| source_product_id | uuid FK |
| canonical_product_id | uuid FK |
| link_type | text |
| confidence | numeric |
| created_by | text |
| created_at | timestamptz |

## `catalog.ai_product_analyses`

| Column | Type |
|---|---|
| id | uuid PK |
| canonical_product_id | uuid FK |
| source_product_id | uuid FK |
| run_id | uuid FK |
| provider | text |
| model | text |
| prompt_version | text |
| schema_version | text |
| image_set_hash | text |
| raw_response | jsonb |
| parsed_result | jsonb nullable |
| validation_status | text |
| analysis_status | text |
| created_at | timestamptz |

## `catalog.product_corrections`

| Column | Type |
|---|---|
| id | uuid PK |
| canonical_product_id | uuid FK |
| field_name | text |
| old_effective_value | jsonb nullable |
| corrected_value | jsonb |
| reason | text nullable |
| is_active | boolean |
| created_by | text |
| created_at | timestamptz |
| superseded_at | timestamptz nullable |

One active correction per product and field.

---

# 4. Research Tables

## `research.sessions`

| Column | Type |
|---|---|
| id | uuid PK |
| canonical_product_id | uuid FK |
| run_id | uuid FK |
| provider | text |
| evidence_period_start | date |
| evidence_period_end | date |
| config_version | text |
| status | text |
| started_at | timestamptz |
| completed_at | timestamptz nullable |
| created_at | timestamptz |

## `research.search_queries`

| Column | Type |
|---|---|
| id | uuid PK |
| research_session_id | uuid FK |
| query_order | integer |
| query_text | text |
| query_stage | text |
| normalized_query | text |
| generated_by | text |
| created_at | timestamptz |

## `research.query_executions`

| Column | Type |
|---|---|
| id | uuid PK |
| search_query_id | uuid FK |
| status | text |
| sold_result_count | integer |
| active_result_count | integer |
| raw_result_ref | text nullable |
| parser_version | text |
| error_id | uuid nullable |
| started_at | timestamptz |
| completed_at | timestamptz nullable |

## `research.marketplace_listings`

| Column | Type |
|---|---|
| id | uuid PK |
| marketplace | text |
| external_listing_id | text |
| canonical_url | text |
| title | text |
| status | text |
| displayed_price_jpy | integer |
| sold_at | timestamptz nullable |
| listed_at | timestamptz nullable |
| condition | text nullable |
| shipping_method | text nullable |
| shipping_responsibility | text nullable |
| estimated_shipping_jpy | integer nullable |
| image_url | text nullable |
| normalized_attributes | jsonb |
| first_seen_at | timestamptz |
| last_seen_at | timestamptz |
| created_at | timestamptz |
| updated_at | timestamptz |

Unique:

```text
(marketplace, external_listing_id)
```

## `research.query_listing_links`

| Column | Type |
|---|---|
| id | uuid PK |
| query_execution_id | uuid FK |
| marketplace_listing_id | uuid FK |
| result_rank | integer |
| created_at | timestamptz |

## `research.comparable_evidence`

| Column | Type |
|---|---|
| id | uuid PK |
| research_session_id | uuid FK |
| marketplace_listing_id | uuid FK |
| model_similarity | numeric nullable |
| title_similarity | numeric nullable |
| image_similarity | numeric nullable |
| condition_similarity | numeric nullable |
| attribute_similarity | numeric nullable |
| total_similarity | numeric |
| ai_review | jsonb nullable |
| default_decision | text |
| current_decision | text |
| decision_reason | text nullable |
| included_in_price | boolean |
| included_in_shipping | boolean |
| created_at | timestamptz |
| updated_at | timestamptz |

## `research.comparable_decisions`

Append-only.

| Column | Type |
|---|---|
| id | uuid PK |
| comparable_evidence_id | uuid FK |
| decision | text |
| reason | text nullable |
| decided_by | text |
| created_at | timestamptz |

## `research.price_statistics`

| Column | Type |
|---|---|
| id | uuid PK |
| research_session_id | uuid FK |
| evidence_snapshot_hash | text |
| included_count | integer |
| median_price_jpy | integer nullable |
| lower_quartile_price_jpy | integer nullable |
| minimum_price_jpy | integer nullable |
| maximum_price_jpy | integer nullable |
| dispersion | numeric nullable |
| created_at | timestamptz |

## `research.shipping_statistics`

| Column | Type |
|---|---|
| id | uuid PK |
| research_session_id | uuid FK |
| source_type | text |
| evidence_count | integer |
| median_shipping_jpy | integer nullable |
| shipping_method | text nullable |
| confidence | numeric |
| reason | text |
| created_at | timestamptz |

---

# 5. Recommendation Tables

## `recommendation.recommendations`

| Column | Type |
|---|---|
| id | uuid PK |
| canonical_product_id | uuid FK |
| source_product_id | uuid FK |
| research_session_id | uuid FK nullable |
| run_id | uuid FK |
| input_snapshot | jsonb |
| estimated_sale_price_jpy | integer nullable |
| estimated_shipping_jpy | integer nullable |
| mercari_fee_jpy | integer nullable |
| sourcing_cost_jpy | integer nullable | unknown is never stored as zero |
| expected_profit_jpy | integer nullable |
| return_on_cost | numeric nullable |
| sales_margin | numeric nullable |
| sales_prospect_score | integer nullable |
| confidence_score | integer |
| overall_sourcing_score | integer nullable |
| recommendation_tier | text |
| fee_rule_version | text |
| shipping_rule_version | text |
| scoring_version | text |
| threshold_version | text |
| evidence_snapshot_hash | text |
| created_at | timestamptz |

Append-only.

The implemented unique key `(source_product_id, evidence_snapshot_hash, scoring_version)` makes
same-input recalculation idempotent while allowing new versions after evidence, price, correction,
or configuration changes.

## `recommendation.reason_components`

| Column | Type |
|---|---|
| id | uuid PK |
| recommendation_id | uuid FK |
| code | text |
| label | text |
| component_type | text |
| value | jsonb nullable |
| score_delta | numeric nullable |
| source | text |
| display_order | integer |
| created_at | timestamptz |

Component types:

- positive
- negative
- risk
- assumption
- confirmation_required

## `recommendation.quantity_evaluations`

| Column | Type |
|---|---|
| id | uuid PK |
| recommendation_id | uuid FK |
| quantity | integer |
| total_sourcing_cost_jpy | integer |
| total_expected_profit_jpy | integer nullable |
| per_unit_profit_jpy | integer nullable |
| created_at | timestamptz |

Constraint: quantity 1–4.

---

# 6. Inventory Tables

## `inventory.positions`

| Column | Type |
|---|---|
| id | uuid PK |
| canonical_product_id | uuid FK |
| source_product_id | uuid FK nullable |
| recommendation_id | uuid FK nullable |
| status | text |
| purchased_quantity | integer |
| sold_quantity | integer |
| purchase_date | date nullable |
| created_at | timestamptz |
| updated_at | timestamptz |

## `inventory.purchase_events`

| Column | Type |
|---|---|
| id | uuid PK |
| inventory_position_id | uuid FK |
| quantity | integer |
| product_amount_jpy | integer |
| sourcing_shipping_jpy | integer |
| coupon_jpy | integer |
| point_reference_jpy | integer |
| actual_charged_amount_jpy | integer |
| purchased_at | timestamptz |
| note | text nullable |
| created_at | timestamptz |

## `inventory.listing_events`

| Column | Type |
|---|---|
| id | uuid PK |
| inventory_position_id | uuid FK |
| marketplace | text |
| quantity | integer |
| listing_price_jpy | integer |
| listing_url | text nullable |
| listed_at | timestamptz |
| created_at | timestamptz |

## `inventory.sale_events`

| Column | Type |
|---|---|
| id | uuid PK |
| inventory_position_id | uuid FK |
| quantity | integer |
| sold_price_jpy | integer |
| actual_fee_jpy | integer |
| actual_shipping_jpy | integer |
| realised_profit_jpy | integer |
| sold_at | timestamptz |
| created_at | timestamptz |

## `inventory.negative_outcomes`

| Column | Type |
|---|---|
| id | uuid PK |
| inventory_position_id | uuid FK |
| outcome_type | text |
| quantity | integer nullable |
| occurred_at | timestamptz |
| note | text nullable |
| created_at | timestamptz |

---

# 7. Learning Tables

## `learning.profit_patterns`

| Column | Type |
|---|---|
| id | uuid PK |
| code | text unique |
| name | text |
| description | text |
| active | boolean |
| created_at | timestamptz |
| updated_at | timestamptz |

Initial codes:

- replacement_product
- character_goods
- new_clothing
- craft_kit
- seasonal_goods

## `learning.profit_hypotheses`

| Column | Type |
|---|---|
| id | uuid PK |
| statement | text |
| hypothesis_type | text |
| scope | jsonb |
| confidence | numeric |
| state | text |
| created_from | text |
| created_at | timestamptz |
| updated_at | timestamptz |

## `learning.hypothesis_evidence`

| Column | Type |
|---|---|
| id | uuid PK |
| hypothesis_id | uuid FK |
| evidence_type | text |
| direction | text |
| strength | numeric |
| source_reference_type | text |
| source_reference_id | uuid nullable |
| summary | text |
| created_at | timestamptz |

## `learning.hypothesis_history`

| Column | Type |
|---|---|
| id | uuid PK |
| hypothesis_id | uuid FK |
| previous_confidence | numeric |
| new_confidence | numeric |
| previous_state | text |
| new_state | text |
| reason | text |
| created_at | timestamptz |

## `learning.user_preference_signals`

Signals:

- want
- slightly_interested
- do_not_want
- cannot_judge

## `learning.research_value_signals`

Signals:

- worth_researching
- not_worth_researching

## `learning.events`

Stores collected, filtered, analysed, researched, corrected, purchased, listed, sold, returned, cancelled, and failed events.

## `learning.reflection_reports`

Stores model, prompt version, report JSON, and run reference.

---

# 8. Run Tables

## `runs.exploration_runs`

Stores mode, trigger, requested by, status, current stage, progress, start, finish, and creation timestamps.

## `runs.stage_checkpoints`

Stores one record per stage attempt and progress checkpoint.

## `runs.source_statuses`

Stores per-source status, collected count, error count, and metadata.

## `runs.errors`

Stores run, stage, source, item, category, retryability, message, technical detail, retry count, and resolution.

## `runs.metrics`

Stores metric code, value, and dimensions.

## `runs.summaries`

Stores recommendation counts, total candidate cost, total expected profit, average prospect score, and summary payload.

---

# 9. Configuration Tables

## `config.versions`

Stores versioned JSON configuration for:

- business thresholds
- fee rules
- shipping mappings
- scoring
- recommendation thresholds
- source limits
- AI provider
- exclusions
- overseas seller quality

## `config.source_definitions`

Stores enabled sources, location IDs, display names, priority, and non-secret public configuration.

---

# 10. Audit

## `audit.events`

Stores actor, action, entity, before and after values, metadata, and timestamp.

Audit events include:

- correction
- comparable exclusion or restoration
- recommendation recalculation
- purchase
- sale
- workflow dispatch
- configuration change

---

# 11. Views

Recommended views:

- current source product state
- current canonical product state
- latest recommendations
- current inventory positions
- current run progress
- current comparable decisions
- daily candidate summary

Views are projections only. History tables remain authoritative.

---

# 12. Indexes

Prioritize:

1. source identity
2. latest observation by source product
3. recommendations by run and score
4. comparables by research session
5. marketplace external ID
6. inventory status and age
7. errors by run and retryability
8. learning events by product and type
9. title trigram or full-text search
10. vector index only if embeddings are introduced

---

# 13. Security

- no anonymous direct table access
- no service-role key in browser
- private storage buckets
- signed image URLs or backend proxy
- application APIs mediate user access

---

# 14. Migration Rules

Every migration includes:

- forward migration
- documentation update
- repository changes
- tests
- backfill note
- rollback or forward-fix strategy

Never rewrite an applied migration.

---

# 15. Retention

- final candidate images: long-term
- detailed-analysis images: retained until cleanup policy
- source image URLs: retained
- recommendation and outcome history: long-term
- raw snapshots: limited by source policy
- logs: configurable

---

# 16. Database Acceptance Criteria

1. Price history is append-only.
2. AI and user values are separate.
3. Recommendation versions are append-only.
4. Comparable exclusions preserve original evidence.
5. Outcomes preserve prediction references.
6. Progress supports polling.
7. Financial values use integer yen.
8. Secrets are absent.
9. Foreign keys and indexes support the core workflow.
10. Current-state views preserve historical traceability.
