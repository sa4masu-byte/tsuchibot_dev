-- Sprint 8 inventory outcomes, feedback, and learning evidence.
-- Forward-fix policy: do not edit after application; use a later migration.

create schema if not exists inventory;
create schema if not exists learning;

create table inventory.purchase_decisions (
    id uuid primary key default gen_random_uuid(),
    canonical_product_id uuid not null references catalog.canonical_products(id),
    recommendation_id uuid references recommendation.recommendations(id),
    purchased boolean not null,
    note text,
    decided_by text not null,
    idempotency_key text not null unique,
    decided_at timestamptz not null,
    created_at timestamptz not null default now()
);

create table inventory.positions (
    id uuid primary key default gen_random_uuid(),
    canonical_product_id uuid not null references catalog.canonical_products(id),
    source_product_id uuid references catalog.source_products(id),
    recommendation_id uuid references recommendation.recommendations(id),
    prediction_snapshot jsonb not null,
    status text not null check (
        status in (
            'purchased', 'listed', 'partially_sold', 'sold', 'returned',
            'cancelled', 'unsold_90_days', 'damaged', 'lost', 'other_failure'
        )
    ),
    purchased_quantity integer not null check (purchased_quantity between 1 and 4),
    sold_quantity integer not null default 0 check (sold_quantity >= 0),
    failed_quantity integer not null default 0 check (failed_quantity >= 0),
    actual_charged_amount_jpy integer not null check (actual_charged_amount_jpy >= 0),
    realised_profit_jpy integer not null default 0,
    purchase_date date not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (sold_quantity + failed_quantity <= purchased_quantity)
);

create index inventory_positions_status_time_idx
    on inventory.positions (status, updated_at desc);
create index inventory_positions_product_idx
    on inventory.positions (canonical_product_id, created_at desc);

create table inventory.purchase_events (
    id uuid primary key default gen_random_uuid(),
    inventory_position_id uuid not null references inventory.positions(id),
    quantity integer not null check (quantity between 1 and 4),
    product_amount_jpy integer not null check (product_amount_jpy >= 0),
    sourcing_shipping_jpy integer not null check (sourcing_shipping_jpy >= 0),
    coupon_jpy integer not null check (coupon_jpy >= 0),
    point_reference_jpy integer not null default 0 check (point_reference_jpy >= 0),
    actual_charged_amount_jpy integer not null check (actual_charged_amount_jpy >= 0),
    purchased_at timestamptz not null,
    note text,
    idempotency_key text not null unique,
    created_at timestamptz not null default now()
);

create table inventory.listing_events (
    id uuid primary key default gen_random_uuid(),
    inventory_position_id uuid not null references inventory.positions(id),
    marketplace text not null,
    quantity integer not null check (quantity > 0),
    listing_price_jpy integer not null check (listing_price_jpy >= 0),
    listing_url text,
    listed_at timestamptz not null,
    idempotency_key text not null unique,
    created_at timestamptz not null default now()
);

create table inventory.sale_events (
    id uuid primary key default gen_random_uuid(),
    inventory_position_id uuid not null references inventory.positions(id),
    quantity integer not null check (quantity > 0),
    sold_price_jpy integer not null check (sold_price_jpy >= 0),
    actual_fee_jpy integer not null check (actual_fee_jpy >= 0),
    actual_shipping_jpy integer not null check (actual_shipping_jpy >= 0),
    allocated_purchase_cost_jpy integer not null check (allocated_purchase_cost_jpy >= 0),
    realised_profit_jpy integer not null,
    sold_at timestamptz not null,
    idempotency_key text not null unique,
    created_at timestamptz not null default now()
);

create table inventory.negative_outcomes (
    id uuid primary key default gen_random_uuid(),
    inventory_position_id uuid not null references inventory.positions(id),
    outcome_type text not null check (
        outcome_type in ('returned', 'cancelled', 'unsold_90_days', 'damaged', 'lost', 'other')
    ),
    quantity integer not null check (quantity > 0),
    occurred_at timestamptz not null,
    note text,
    idempotency_key text not null unique,
    created_at timestamptz not null default now()
);

create table learning.profit_patterns (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    description text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table learning.profit_hypotheses (
    id uuid primary key default gen_random_uuid(),
    pattern_id uuid references learning.profit_patterns(id),
    statement text not null,
    hypothesis_type text not null,
    scope jsonb not null default '{}'::jsonb,
    confidence numeric not null check (confidence between 0 and 1),
    state text not null check (state in ('active', 'narrowed', 'disproven', 'archived')),
    created_from text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table learning.hypothesis_evidence (
    id uuid primary key default gen_random_uuid(),
    hypothesis_id uuid not null references learning.profit_hypotheses(id),
    evidence_type text not null,
    direction text not null check (direction in ('supporting', 'contradictory', 'neutral')),
    strength numeric not null check (strength between 0 and 1),
    source_reference_type text not null,
    source_reference_id uuid,
    summary text not null,
    idempotency_key text unique,
    created_at timestamptz not null default now()
);

create table learning.hypothesis_history (
    id uuid primary key default gen_random_uuid(),
    hypothesis_id uuid not null references learning.profit_hypotheses(id),
    previous_confidence numeric,
    new_confidence numeric not null,
    previous_state text,
    new_state text not null,
    reason text not null,
    created_at timestamptz not null default now()
);

create table learning.user_preference_signals (
    id uuid primary key default gen_random_uuid(),
    canonical_product_id uuid not null references catalog.canonical_products(id),
    signal text not null check (
        signal in ('want', 'slightly_interested', 'do_not_want', 'cannot_judge')
    ),
    note text,
    recorded_by text not null,
    idempotency_key text not null unique,
    created_at timestamptz not null default now()
);

create table learning.research_value_signals (
    id uuid primary key default gen_random_uuid(),
    canonical_product_id uuid not null references catalog.canonical_products(id),
    signal text not null check (signal in ('worth_researching', 'not_worth_researching')),
    note text,
    recorded_by text not null,
    idempotency_key text not null unique,
    created_at timestamptz not null default now()
);

create table learning.events (
    id uuid primary key default gen_random_uuid(),
    event_type text not null,
    canonical_product_id uuid references catalog.canonical_products(id),
    inventory_position_id uuid references inventory.positions(id),
    actor text not null,
    payload jsonb not null default '{}'::jsonb,
    source_reference_type text,
    source_reference_id uuid,
    created_at timestamptz not null default now()
);

create index learning_events_product_time_idx
    on learning.events (canonical_product_id, created_at desc);
create index hypothesis_evidence_hypothesis_idx
    on learning.hypothesis_evidence (hypothesis_id, created_at desc);

create trigger purchase_decisions_append_only before update or delete on inventory.purchase_decisions
for each row execute function catalog.reject_history_mutation();
create trigger purchase_events_append_only before update or delete on inventory.purchase_events
for each row execute function catalog.reject_history_mutation();
create trigger listing_events_append_only before update or delete on inventory.listing_events
for each row execute function catalog.reject_history_mutation();
create trigger sale_events_append_only before update or delete on inventory.sale_events
for each row execute function catalog.reject_history_mutation();
create trigger negative_outcomes_append_only before update or delete on inventory.negative_outcomes
for each row execute function catalog.reject_history_mutation();
create trigger hypothesis_evidence_append_only before update or delete on learning.hypothesis_evidence
for each row execute function catalog.reject_history_mutation();
create trigger hypothesis_history_append_only before update or delete on learning.hypothesis_history
for each row execute function catalog.reject_history_mutation();
create trigger preference_signals_append_only before update or delete on learning.user_preference_signals
for each row execute function catalog.reject_history_mutation();
create trigger research_value_signals_append_only before update or delete on learning.research_value_signals
for each row execute function catalog.reject_history_mutation();
create trigger learning_events_append_only before update or delete on learning.events
for each row execute function catalog.reject_history_mutation();

alter table inventory.purchase_decisions enable row level security;
alter table inventory.positions enable row level security;
alter table inventory.purchase_events enable row level security;
alter table inventory.listing_events enable row level security;
alter table inventory.sale_events enable row level security;
alter table inventory.negative_outcomes enable row level security;
alter table learning.profit_patterns enable row level security;
alter table learning.profit_hypotheses enable row level security;
alter table learning.hypothesis_evidence enable row level security;
alter table learning.hypothesis_history enable row level security;
alter table learning.user_preference_signals enable row level security;
alter table learning.research_value_signals enable row level security;
alter table learning.events enable row level security;

insert into learning.profit_patterns (code, name, description) values
    ('replacement_product', '交換・保守用品', 'リモコンや交換フィルターなどの交換需要'),
    ('character_goods', 'キャラクター商品', 'キーホルダー、ぬいぐるみ等の国内外需要'),
    ('new_clothing', '新品衣料', '新品シャツ、肌着、ブランド新品衣料'),
    ('craft_kit', 'クラフト商品', 'クラフトキットの需要'),
    ('seasonal_goods', '季節商品', '扇子など季節性のある需要');

insert into learning.profit_hypotheses (
    pattern_id, statement, hypothesis_type, scope, confidence, state, created_from
)
select id, description || 'は適正価格で利益機会になり得る', 'initial_pattern',
       jsonb_build_object('pattern_code', code), 0.5, 'active', 'FR-110'
from learning.profit_patterns;
