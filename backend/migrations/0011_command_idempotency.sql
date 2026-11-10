-- Sprint 9 command identity protects retries across inventory and learning operations.
-- Forward-fix policy: do not edit after application; use a later migration.

create table audit.command_requests (
    idempotency_key text primary key,
    action text not null,
    target_id uuid not null,
    payload_hash text not null check (length(payload_hash) = 64),
    created_at timestamptz not null default now()
);

create index command_requests_target_idx
    on audit.command_requests (action, target_id, created_at desc);

create trigger command_requests_append_only
before update or delete on audit.command_requests
for each row execute function catalog.reject_history_mutation();

alter table audit.command_requests enable row level security;
