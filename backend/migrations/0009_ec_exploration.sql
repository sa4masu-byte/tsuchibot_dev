-- Sprint 7 alternative EC exploration evidence and deterministic policy results.
-- Forward-fix policy: do not edit after application; use a later migration.

create schema if not exists ec;

create table ec.exploration_sessions (
    id uuid primary key,
    run_id uuid not null references runs.exploration_runs(id),
    trigger_reason text not null,
    useful_jimoty_candidates integer not null check (useful_jimoty_candidates >= 0),
    keyword_limit integer not null check (keyword_limit > 0),
    keyword_count integer not null check (keyword_count between 0 and keyword_limit),
    policy_version text not null,
    status text not null check (status in ('not_required', 'completed', 'partial_failure')),
    observed_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index ec_sessions_run_time_idx on ec.exploration_sessions (run_id, created_at desc);

create table ec.search_attempts (
    id uuid primary key default gen_random_uuid(),
    exploration_session_id uuid not null references ec.exploration_sessions(id),
    source text not null check (source in ('amazon', 'rakuten', 'aliexpress', 'shein')),
    source_order integer not null check (source_order between 1 and 4),
    query_order integer not null check (query_order > 0),
    keyword text not null,
    strategy text not null check (
        strategy in ('profit_pattern', 'mercari_demand', 'sale_discount')
    ),
    status text not null check (status in ('completed', 'failed', 'unavailable')),
    parser_version text not null,
    collected_count integer not null default 0 check (collected_count >= 0),
    error_category text,
    error_message text,
    created_at timestamptz not null default now(),
    unique (exploration_session_id, source, query_order)
);

create table ec.offers (
    id uuid primary key default gen_random_uuid(),
    exploration_session_id uuid not null references ec.exploration_sessions(id),
    source text not null check (source in ('amazon', 'rakuten', 'aliexpress', 'shein')),
    source_item_id text not null,
    canonical_url text not null,
    title text not null,
    displayed_price_jpy integer not null check (displayed_price_jpy >= 0),
    sourcing_shipping_jpy integer not null check (sourcing_shipping_jpy >= 0),
    definite_coupon_jpy integer not null check (definite_coupon_jpy >= 0),
    points_reference_jpy integer not null check (points_reference_jpy >= 0),
    available boolean not null,
    category text,
    product_type text not null,
    selected_variant text,
    variant_price_confirmed boolean not null,
    delivery_days integer check (delivery_days is null or delivery_days >= 0),
    product_rating numeric check (product_rating is null or product_rating between 0 and 5),
    review_count integer check (review_count is null or review_count >= 0),
    seller_rating numeric check (seller_rating is null or seller_rating between 0 and 5),
    seller_name text,
    shop_id text,
    shop_rating numeric check (shop_rating is null or shop_rating between 0 and 5),
    brand text,
    character_name text,
    authenticity_supported boolean not null,
    original_currency text,
    original_amount text,
    matched_keyword text,
    image_urls jsonb not null default '[]'::jsonb,
    raw_metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (exploration_session_id, source, source_item_id)
);

create index ec_offers_source_item_idx on ec.offers (source, source_item_id, created_at desc);

create table ec.offer_evaluations (
    id uuid primary key default gen_random_uuid(),
    offer_id uuid not null unique references ec.offers(id),
    eligibility text not null check (
        eligibility in ('eligible', 'confirmation_required', 'rejected')
    ),
    sourcing_cost_jpy integer not null check (sourcing_cost_jpy >= 0),
    reason_codes jsonb not null,
    policy_version text not null,
    created_at timestamptz not null default now()
);

create trigger ec_sessions_append_only before update or delete on ec.exploration_sessions
for each row execute function catalog.reject_history_mutation();
create trigger ec_attempts_append_only before update or delete on ec.search_attempts
for each row execute function catalog.reject_history_mutation();
create trigger ec_offers_append_only before update or delete on ec.offers
for each row execute function catalog.reject_history_mutation();
create trigger ec_evaluations_append_only before update or delete on ec.offer_evaluations
for each row execute function catalog.reject_history_mutation();

alter table ec.exploration_sessions enable row level security;
alter table ec.search_attempts enable row level security;
alter table ec.offers enable row level security;
alter table ec.offer_evaluations enable row level security;

insert into config.versions (config_type, version, payload, active, created_by)
values (
    'ec',
    'ec-phase1-v1',
    '{
      "source_order": ["amazon", "rakuten", "aliexpress", "shein"],
      "keyword_limit": 20,
      "minimum_useful_candidates": 3,
      "overseas_delivery_days_max": 7,
      "overseas_minimum_review_count": 20,
      "overseas_minimum_product_rating": 4.5,
      "overseas_minimum_seller_rating": 4.5,
      "maximum_purchase_quantity": 4
    }'::jsonb,
    true,
    'migration-0009'
);
