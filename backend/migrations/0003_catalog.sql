-- Sprint 2 catalog schema (FR-001 through FR-007).
-- Forward-fix policy: do not edit after application; use a later migration.

create schema if not exists catalog;

create table catalog.source_products (
    id uuid primary key default gen_random_uuid(),
    source_type text not null,
    source_location_id text,
    source_item_id text not null,
    canonical_url text not null,
    parser_version text not null,
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    current_availability text not null check (
        current_availability in ('available', 'unavailable', 'unknown')
    ),
    current_price_jpy integer check (current_price_jpy is null or current_price_jpy >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (source_type, source_item_id)
);

create index source_products_canonical_url_idx on catalog.source_products (canonical_url);
create index source_products_location_seen_idx
    on catalog.source_products (source_type, source_location_id, last_seen_at desc);

create table catalog.source_observations (
    id uuid primary key default gen_random_uuid(),
    source_product_id uuid not null references catalog.source_products(id),
    run_id uuid not null references runs.exploration_runs(id),
    observed_at timestamptz not null,
    title text,
    displayed_category text,
    displayed_price_jpy integer check (displayed_price_jpy is null or displayed_price_jpy >= 0),
    availability text not null check (availability in ('available', 'unavailable', 'unknown')),
    listing_timestamp timestamptz,
    raw_metadata jsonb not null default '{}'::jsonb,
    raw_snapshot_ref text,
    parser_version text not null,
    idempotency_key text not null unique,
    created_at timestamptz not null default now()
);

create index source_observations_product_time_idx
    on catalog.source_observations (source_product_id, observed_at desc);
create index source_observations_run_idx on catalog.source_observations (run_id);

create table catalog.price_observations (
    id uuid primary key default gen_random_uuid(),
    source_product_id uuid not null references catalog.source_products(id),
    run_id uuid not null references runs.exploration_runs(id),
    amount_jpy integer not null check (amount_jpy >= 0),
    price_type text not null default 'displayed',
    observed_at timestamptz not null,
    change_from_previous_jpy integer,
    change_rate numeric,
    created_at timestamptz not null default now()
);

create index price_observations_product_time_idx
    on catalog.price_observations (source_product_id, observed_at desc);

create table catalog.availability_observations (
    id uuid primary key default gen_random_uuid(),
    source_product_id uuid not null references catalog.source_products(id),
    run_id uuid not null references runs.exploration_runs(id),
    availability text not null check (availability in ('available', 'unavailable', 'unknown')),
    observed_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index availability_observations_product_time_idx
    on catalog.availability_observations (source_product_id, observed_at desc);

create table catalog.product_images (
    id uuid primary key default gen_random_uuid(),
    source_product_id uuid not null references catalog.source_products(id),
    source_url text not null,
    storage_path text,
    content_hash text,
    width integer check (width is null or width > 0),
    height integer check (height is null or height > 0),
    image_order integer not null check (image_order >= 0),
    retention_class text not null default 'source_reference',
    first_seen_at timestamptz not null,
    created_at timestamptz not null default now(),
    unique (source_product_id, source_url)
);

create index product_images_hash_idx on catalog.product_images (content_hash)
    where content_hash is not null;

create or replace function catalog.reject_history_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception '% is append-only', tg_table_name;
end;
$$;

create trigger source_observations_append_only
before update or delete on catalog.source_observations
for each row execute function catalog.reject_history_mutation();

create trigger price_observations_append_only
before update or delete on catalog.price_observations
for each row execute function catalog.reject_history_mutation();

create trigger availability_observations_append_only
before update or delete on catalog.availability_observations
for each row execute function catalog.reject_history_mutation();

alter table catalog.source_products enable row level security;
alter table catalog.source_observations enable row level security;
alter table catalog.price_observations enable row level security;
alter table catalog.availability_observations enable row level security;
alter table catalog.product_images enable row level security;

create view catalog.current_source_product_state as
select
    source_products.id,
    source_products.source_type,
    source_products.source_location_id,
    source_products.source_item_id,
    source_products.canonical_url,
    source_products.current_price_jpy,
    source_products.current_availability,
    source_products.first_seen_at,
    source_products.last_seen_at,
    source_products.parser_version
from catalog.source_products;
