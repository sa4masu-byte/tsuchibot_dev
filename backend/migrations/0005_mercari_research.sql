-- Sprint 4 Mercari research sessions, normalized evidence, and market statistics.
-- Forward-fix policy: do not edit after application; use a later migration.

create schema if not exists research;

create table research.sessions (
    id uuid primary key,
    canonical_product_id uuid not null references catalog.canonical_products(id),
    run_id uuid not null references runs.exploration_runs(id),
    provider text not null,
    evidence_period_start date not null,
    evidence_period_end date not null,
    config_version text not null,
    status text not null check (
        status in ('completed', 'partial_failure', 'research_unavailable', 'failed')
    ),
    started_at timestamptz not null,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    check (evidence_period_start <= evidence_period_end)
);

create index research_sessions_product_time_idx
    on research.sessions (canonical_product_id, created_at desc);
create index research_sessions_run_idx on research.sessions (run_id, status);

create table research.search_queries (
    id uuid primary key default gen_random_uuid(),
    research_session_id uuid not null references research.sessions(id),
    query_order integer not null check (query_order > 0),
    query_text text not null,
    query_stage text not null check (
        query_stage in (
            'exact_model', 'manufacturer_model', 'series_product_type',
            'manufacturer_product_type', 'similar_product'
        )
    ),
    normalized_query text not null,
    generated_by text not null,
    created_at timestamptz not null default now(),
    unique (research_session_id, query_order),
    unique (research_session_id, normalized_query)
);

create table research.query_executions (
    id uuid primary key,
    search_query_id uuid not null references research.search_queries(id),
    status text not null check (status in ('completed', 'failed')),
    sold_result_count integer not null default 0 check (sold_result_count >= 0),
    active_result_count integer not null default 0 check (active_result_count >= 0),
    raw_result_ref text,
    parser_version text not null,
    error_id uuid references runs.errors(id),
    started_at timestamptz not null,
    completed_at timestamptz,
    check ((status = 'failed') = (error_id is not null))
);

create table research.marketplace_listings (
    id uuid primary key default gen_random_uuid(),
    marketplace text not null,
    external_listing_id text not null,
    canonical_url text not null,
    title text not null,
    status text not null check (status in ('sold', 'active')),
    displayed_price_jpy integer not null check (displayed_price_jpy >= 0),
    sold_at timestamptz,
    listed_at timestamptz,
    condition text,
    shipping_method text,
    shipping_responsibility text check (
        shipping_responsibility in ('seller', 'buyer', 'unknown')
    ),
    estimated_shipping_jpy integer check (
        estimated_shipping_jpy is null or estimated_shipping_jpy >= 0
    ),
    image_url text,
    normalized_attributes jsonb not null default '{}'::jsonb,
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (marketplace, external_listing_id)
);

create index marketplace_listings_status_sold_idx
    on research.marketplace_listings (marketplace, status, sold_at desc);

create table research.query_listing_links (
    id uuid primary key default gen_random_uuid(),
    query_execution_id uuid not null references research.query_executions(id),
    marketplace_listing_id uuid not null references research.marketplace_listings(id),
    result_rank integer not null check (result_rank > 0),
    created_at timestamptz not null default now(),
    unique (query_execution_id, marketplace_listing_id)
);

create table research.comparable_evidence (
    id uuid primary key default gen_random_uuid(),
    research_session_id uuid not null references research.sessions(id),
    marketplace_listing_id uuid not null references research.marketplace_listings(id),
    model_similarity numeric check (model_similarity is null or model_similarity between 0 and 1),
    title_similarity numeric not null check (title_similarity between 0 and 1),
    image_similarity numeric check (image_similarity is null or image_similarity between 0 and 1),
    condition_similarity numeric not null check (condition_similarity between 0 and 1),
    attribute_similarity numeric not null check (attribute_similarity between 0 and 1),
    total_similarity numeric not null check (total_similarity between 0 and 1),
    ai_review jsonb,
    default_decision text not null check (default_decision in ('include', 'exclude', 'review')),
    current_decision text not null check (current_decision in ('include', 'exclude', 'review')),
    decision_reason text,
    included_in_price boolean not null,
    included_in_shipping boolean not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (research_session_id, marketplace_listing_id)
);

create index comparable_evidence_session_rank_idx
    on research.comparable_evidence (research_session_id, total_similarity desc);

create table research.comparable_decisions (
    id uuid primary key default gen_random_uuid(),
    comparable_evidence_id uuid not null references research.comparable_evidence(id),
    decision text not null check (decision in ('include', 'exclude', 'review')),
    reason text,
    decided_by text not null,
    created_at timestamptz not null default now()
);

create table research.price_statistics (
    id uuid primary key default gen_random_uuid(),
    research_session_id uuid not null references research.sessions(id),
    evidence_snapshot_hash text not null,
    included_count integer not null check (included_count >= 0),
    median_price_jpy integer check (median_price_jpy is null or median_price_jpy >= 0),
    lower_quartile_price_jpy integer check (
        lower_quartile_price_jpy is null or lower_quartile_price_jpy >= 0
    ),
    minimum_price_jpy integer check (minimum_price_jpy is null or minimum_price_jpy >= 0),
    maximum_price_jpy integer check (maximum_price_jpy is null or maximum_price_jpy >= 0),
    dispersion numeric check (dispersion is null or dispersion >= 0),
    sufficient_evidence boolean not null,
    created_at timestamptz not null default now()
);

create table research.shipping_statistics (
    id uuid primary key default gen_random_uuid(),
    research_session_id uuid not null references research.sessions(id),
    source_type text not null,
    evidence_count integer not null check (evidence_count >= 0),
    median_shipping_jpy integer check (
        median_shipping_jpy is null or median_shipping_jpy >= 0
    ),
    shipping_method text,
    confidence numeric not null check (confidence between 0 and 1),
    reason text not null,
    created_at timestamptz not null default now()
);

create trigger research_search_queries_append_only
before update or delete on research.search_queries
for each row execute function catalog.reject_history_mutation();

create trigger research_query_executions_append_only
before update or delete on research.query_executions
for each row execute function catalog.reject_history_mutation();

create trigger research_query_listing_links_append_only
before update or delete on research.query_listing_links
for each row execute function catalog.reject_history_mutation();

create trigger research_comparable_decisions_append_only
before update or delete on research.comparable_decisions
for each row execute function catalog.reject_history_mutation();

create trigger research_price_statistics_append_only
before update or delete on research.price_statistics
for each row execute function catalog.reject_history_mutation();

create trigger research_shipping_statistics_append_only
before update or delete on research.shipping_statistics
for each row execute function catalog.reject_history_mutation();

alter table research.sessions enable row level security;
alter table research.search_queries enable row level security;
alter table research.query_executions enable row level security;
alter table research.marketplace_listings enable row level security;
alter table research.query_listing_links enable row level security;
alter table research.comparable_evidence enable row level security;
alter table research.comparable_decisions enable row level security;
alter table research.price_statistics enable row level security;
alter table research.shipping_statistics enable row level security;
