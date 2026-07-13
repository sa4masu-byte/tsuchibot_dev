-- Browser-assisted visual identity evidence for low-confidence product identification.
-- Forward-fix policy: do not edit after application; use a later migration.

create table research.visual_search_evidence (
    id uuid primary key default gen_random_uuid(),
    source_product_id uuid not null references catalog.source_products(id),
    run_id uuid not null references runs.exploration_runs(id),
    provider text not null,
    image_url_hash text not null,
    status text not null check (status in ('completed', 'failed')),
    result_titles jsonb not null default '[]'::jsonb,
    resolved_candidates jsonb not null default '[]'::jsonb,
    failure_type text,
    failure_message text,
    created_at timestamptz not null default now(),
    check ((status = 'failed') = (failure_type is not null))
);

create index visual_search_evidence_product_time_idx
    on research.visual_search_evidence (source_product_id, created_at desc);

create trigger visual_search_evidence_append_only
before update or delete on research.visual_search_evidence
for each row execute function catalog.reject_history_mutation();

alter table research.visual_search_evidence enable row level security;
