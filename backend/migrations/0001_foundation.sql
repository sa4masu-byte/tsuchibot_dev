-- Tsuchibot foundation schema.
-- Forward-fix policy: this migration is immutable once applied; corrections use a new migration.
-- Rollback (development only): drop schemas audit, config, runs with CASCADE.

create extension if not exists pgcrypto;

create schema if not exists runs;
create schema if not exists config;
create schema if not exists audit;

create table runs.exploration_runs (
    id uuid primary key default gen_random_uuid(),
    mode text not null check (mode in ('incremental', 'full', 'retry_failed')),
    trigger_source text not null,
    requested_by text not null,
    status text not null check (
        status in ('pending', 'running', 'partial_failure', 'completed', 'failed', 'cancelled')
    ),
    current_stage text not null default 'queued',
    progress_numerator integer not null default 0 check (progress_numerator >= 0),
    progress_denominator integer not null default 0 check (progress_denominator >= 0),
    target_run_id uuid references runs.exploration_runs(id),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    constraint retry_target_required check (
        (mode = 'retry_failed' and target_run_id is not null)
        or (mode <> 'retry_failed' and target_run_id is null)
    ),
    constraint progress_within_total check (
        progress_denominator = 0 or progress_numerator <= progress_denominator
    )
);

create unique index one_active_exploration_run
    on runs.exploration_runs ((true))
    where status in ('pending', 'running');

create index exploration_runs_created_at_idx
    on runs.exploration_runs (created_at desc);

create table runs.stage_checkpoints (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs.exploration_runs(id),
    stage text not null,
    attempt integer not null default 1 check (attempt > 0),
    status text not null,
    progress_numerator integer not null default 0,
    progress_denominator integer not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    unique (run_id, stage, attempt)
);

create table runs.source_statuses (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs.exploration_runs(id),
    source_code text not null,
    status text not null,
    collected_count integer not null default 0 check (collected_count >= 0),
    error_count integer not null default 0 check (error_count >= 0),
    metadata jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    unique (run_id, source_code)
);

create table runs.errors (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs.exploration_runs(id),
    stage text not null,
    source text,
    item_id text,
    category text not null,
    retryable boolean not null,
    user_message text not null,
    technical_detail text,
    retry_count integer not null default 0 check (retry_count >= 0),
    resolution_status text not null default 'open',
    occurred_at timestamptz not null default now()
);

create index run_errors_lookup_idx on runs.errors (run_id, retryable, occurred_at desc);

create table runs.metrics (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs.exploration_runs(id),
    metric_code text not null,
    value numeric not null,
    dimensions jsonb not null default '{}'::jsonb,
    recorded_at timestamptz not null default now()
);

create table runs.summaries (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null unique references runs.exploration_runs(id),
    recommendation_counts jsonb not null default '{}'::jsonb,
    total_candidate_cost_jpy integer not null default 0,
    total_expected_profit_jpy integer not null default 0,
    average_sales_prospect numeric,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table config.versions (
    id uuid primary key default gen_random_uuid(),
    config_type text not null,
    version text not null,
    payload jsonb not null,
    active boolean not null default false,
    created_by text not null,
    created_at timestamptz not null default now(),
    unique (config_type, version)
);

create unique index one_active_config_version
    on config.versions (config_type)
    where active;

create table config.source_definitions (
    id uuid primary key default gen_random_uuid(),
    source_code text not null,
    location_id text,
    display_name text not null,
    priority integer not null check (priority > 0),
    enabled boolean not null default true,
    public_config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique nulls not distinct (source_code, location_id)
);

create table audit.events (
    id uuid primary key default gen_random_uuid(),
    actor text not null,
    action text not null,
    entity_type text not null,
    entity_id text not null,
    before_value jsonb,
    after_value jsonb,
    metadata jsonb not null default '{}'::jsonb,
    occurred_at timestamptz not null default now()
);

create index audit_events_entity_idx
    on audit.events (entity_type, entity_id, occurred_at desc);

alter table runs.exploration_runs enable row level security;
alter table runs.stage_checkpoints enable row level security;
alter table runs.source_statuses enable row level security;
alter table runs.errors enable row level security;
alter table runs.metrics enable row level security;
alter table runs.summaries enable row level security;
alter table config.versions enable row level security;
alter table config.source_definitions enable row level security;
alter table audit.events enable row level security;

-- No browser-facing policies are created. Server-side service credentials mediate access.
