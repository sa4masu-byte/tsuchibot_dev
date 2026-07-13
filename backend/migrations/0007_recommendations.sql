-- Sprint 5 deterministic recommendation snapshots, reasons, and quantity evaluations.
-- Forward-fix policy: do not edit after application; use a later migration.
-- Development rollback: drop schema recommendation cascade, then remove its config version.

create schema if not exists recommendation;

create table recommendation.recommendations (
    id uuid primary key,
    canonical_product_id uuid not null references catalog.canonical_products(id),
    source_product_id uuid not null references catalog.source_products(id),
    research_session_id uuid not null references research.sessions(id),
    run_id uuid not null references runs.exploration_runs(id),
    input_snapshot jsonb not null,
    estimated_sale_price_jpy integer check (
        estimated_sale_price_jpy is null or estimated_sale_price_jpy >= 0
    ),
    estimated_shipping_jpy integer check (
        estimated_shipping_jpy is null or estimated_shipping_jpy >= 0
    ),
    mercari_fee_jpy integer check (mercari_fee_jpy is null or mercari_fee_jpy >= 0),
    sourcing_cost_jpy integer check (sourcing_cost_jpy is null or sourcing_cost_jpy >= 0),
    expected_profit_jpy integer,
    return_on_cost numeric,
    sales_margin numeric,
    sales_prospect_score integer not null check (sales_prospect_score between 0 and 100),
    confidence_score integer not null check (confidence_score between 0 and 100),
    overall_sourcing_score integer check (
        overall_sourcing_score is null or overall_sourcing_score between 0 and 100
    ),
    recommendation_tier text not null check (
        recommendation_tier in ('strongly_recommended', 'recommended', 'candidate', 'reject')
    ),
    config_version text not null,
    fee_rule_version text not null,
    shipping_rule_version text not null,
    scoring_version text not null,
    threshold_version text not null,
    evidence_snapshot_hash text not null,
    created_at timestamptz not null,
    unique (source_product_id, evidence_snapshot_hash, scoring_version)
);

create index recommendations_run_score_idx
    on recommendation.recommendations (run_id, overall_sourcing_score desc nulls last);
create index recommendations_product_time_idx
    on recommendation.recommendations (canonical_product_id, created_at desc);

create table recommendation.reason_components (
    id uuid primary key default gen_random_uuid(),
    recommendation_id uuid not null references recommendation.recommendations(id),
    code text not null,
    label text not null,
    component_type text not null check (
        component_type in ('positive', 'negative', 'risk', 'assumption', 'confirmation_required')
    ),
    value jsonb,
    score_delta numeric,
    source text not null,
    display_order integer not null check (display_order > 0),
    created_at timestamptz not null default now(),
    unique (recommendation_id, display_order)
);

create table recommendation.quantity_evaluations (
    id uuid primary key default gen_random_uuid(),
    recommendation_id uuid not null references recommendation.recommendations(id),
    quantity integer not null check (quantity between 1 and 4),
    total_sourcing_cost_jpy integer not null check (total_sourcing_cost_jpy >= 0),
    total_expected_profit_jpy integer,
    per_unit_profit_jpy integer,
    created_at timestamptz not null default now(),
    unique (recommendation_id, quantity)
);

create trigger recommendations_append_only
before update or delete on recommendation.recommendations
for each row execute function catalog.reject_history_mutation();

create trigger recommendation_reasons_append_only
before update or delete on recommendation.reason_components
for each row execute function catalog.reject_history_mutation();

create trigger recommendation_quantities_append_only
before update or delete on recommendation.quantity_evaluations
for each row execute function catalog.reject_history_mutation();

alter table recommendation.recommendations enable row level security;
alter table recommendation.reason_components enable row level security;
alter table recommendation.quantity_evaluations enable row level security;

insert into config.versions (config_type, version, payload, active, created_by)
values (
    'recommendation',
    'phase1-v1',
    '{
      "fee": {
        "version": "mercari-standard-2026-07",
        "rate_basis_points": 1000,
        "rounding": "floor"
      },
      "shipping": {
        "version": "mercari-shipping-2026-07",
        "standard_by_method": {
          "ネコポス": 210,
          "宅急便コンパクト": 520,
          "宅急便60": 750,
          "宅急便80": 850,
          "宅急便100": 1050,
          "宅急便120": 1200,
          "宅急便140": 1450,
          "宅急便160": 1700,
          "宅急便180": 2100,
          "宅急便200": 2500
        }
      },
      "scoring": {
        "version": "phase1-scores-v1",
        "maximum_sold_volume": 10
      },
      "thresholds": {
        "version": "phase1-thresholds-v1",
        "minimum_candidate_profit_jpy": 300,
        "recommended_profit_jpy": 500,
        "strong_profit_jpy": 1000,
        "sales_prospect_threshold": 70,
        "recommended_confidence_threshold": 65,
        "strong_confidence_threshold": 80,
        "strong_return_on_cost": 0.5
      }
    }'::jsonb,
    true,
    'migration-0007'
);
