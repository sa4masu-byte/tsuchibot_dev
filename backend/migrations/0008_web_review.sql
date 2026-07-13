-- Sprint 6 web review corrections and command idempotency.
-- Forward-fix policy: do not edit after application; use a later migration.

create table catalog.product_corrections (
    id uuid primary key default gen_random_uuid(),
    canonical_product_id uuid not null references catalog.canonical_products(id),
    field_name text not null check (
        field_name in (
            'display_name', 'category', 'manufacturer', 'brand', 'model_number',
            'character_name', 'size_text', 'color', 'condition', 'is_new',
            'estimated_shipping_jpy', 'estimated_sale_price_jpy'
        )
    ),
    old_effective_value jsonb,
    corrected_value jsonb not null,
    reason text,
    is_active boolean not null default true,
    created_by text not null,
    idempotency_key text not null unique,
    created_at timestamptz not null default now(),
    superseded_at timestamptz,
    check (is_active = (superseded_at is null))
);

create unique index one_active_product_correction
    on catalog.product_corrections (canonical_product_id, field_name)
    where is_active;
create index product_corrections_product_time_idx
    on catalog.product_corrections (canonical_product_id, created_at desc);

alter table research.comparable_decisions
    add column idempotency_key text;
create unique index comparable_decisions_idempotency_idx
    on research.comparable_decisions (idempotency_key)
    where idempotency_key is not null;

alter table catalog.product_corrections enable row level security;
