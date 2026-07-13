-- Sprint 3 canonical product and versioned AI analysis history.
-- Forward-fix policy: do not edit after application; use a later migration.

create table catalog.canonical_products (
    id uuid primary key default gen_random_uuid(),
    display_name text,
    category text,
    manufacturer text,
    brand text,
    model_number text,
    character_name text,
    size_text text,
    color text,
    condition text not null default 'unknown',
    is_new boolean,
    estimated_original_price_min_jpy integer check (
        estimated_original_price_min_jpy is null or estimated_original_price_min_jpy >= 0
    ),
    estimated_original_price_max_jpy integer check (
        estimated_original_price_max_jpy is null or estimated_original_price_max_jpy >= 0
    ),
    effective_version integer not null default 1 check (effective_version > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (
        estimated_original_price_min_jpy is null
        or estimated_original_price_max_jpy is null
        or estimated_original_price_min_jpy <= estimated_original_price_max_jpy
    )
);

create table catalog.source_product_links (
    id uuid primary key default gen_random_uuid(),
    source_product_id uuid not null references catalog.source_products(id),
    canonical_product_id uuid not null references catalog.canonical_products(id),
    link_type text not null,
    confidence numeric not null check (confidence between 0 and 1),
    created_by text not null,
    created_at timestamptz not null default now(),
    unique (source_product_id, canonical_product_id)
);

create index source_product_links_canonical_idx
    on catalog.source_product_links (canonical_product_id);

create table catalog.ai_product_analyses (
    id uuid primary key default gen_random_uuid(),
    canonical_product_id uuid references catalog.canonical_products(id),
    source_product_id uuid not null references catalog.source_products(id),
    run_id uuid not null references runs.exploration_runs(id),
    provider text not null,
    model text not null,
    prompt_version text not null,
    schema_version text not null,
    image_set_hash text not null,
    request_hash text not null,
    raw_response jsonb not null,
    parsed_result jsonb,
    validation_status text not null,
    analysis_status text not null,
    input_tokens integer check (input_tokens is null or input_tokens >= 0),
    output_tokens integer check (output_tokens is null or output_tokens >= 0),
    latency_ms integer check (latency_ms is null or latency_ms >= 0),
    failure_type text,
    created_at timestamptz not null default now(),
    unique (
        source_product_id,
        image_set_hash,
        prompt_version,
        model,
        schema_version
    )
);

create index ai_product_analyses_run_status_idx
    on catalog.ai_product_analyses (run_id, analysis_status, created_at desc);
create index ai_product_analyses_product_idx
    on catalog.ai_product_analyses (source_product_id, created_at desc);

create trigger ai_product_analyses_append_only
before update or delete on catalog.ai_product_analyses
for each row execute function catalog.reject_history_mutation();

alter table catalog.canonical_products enable row level security;
alter table catalog.source_product_links enable row level security;
alter table catalog.ai_product_analyses enable row level security;
