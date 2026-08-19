-- =============================================================================
-- 0004 — Terreno preparado para los Módulos II y III
--
-- Estas tablas se crean HOY y no se usan todavía. El motivo es deliberado:
-- documentan la arquitectura completa y garantizan que los módulos siguientes
-- no obliguen a migrar datos ya existentes.
-- =============================================================================

do $$
begin
  if not exists (select 1 from pg_type where typname = 'content_type') then
    create type public.content_type as enum
      ('product_description', 'video_script', 'image_prompt', 'social_post');
  end if;

  if not exists (select 1 from pg_type where typname = 'content_status') then
    create type public.content_status as enum
      ('draft', 'pending_a', 'pending_b', 'approved', 'rejected');
  end if;

  if not exists (select 1 from pg_type where typname = 'audit_verdict') then
    create type public.audit_verdict as enum ('pass', 'warn', 'fail');
  end if;
end $$;


-- ------------------------------------------------- MÓDULO II — Creative Engine
create table if not exists public.content_pieces (
  id          uuid primary key default gen_random_uuid(),
  brand_id    uuid not null references public.brands(id) on delete cascade,
  manual_id   uuid not null references public.brand_manuals(id) on delete restrict,
  type        public.content_type not null,
  channel     text not null default '',
  input_brief jsonb not null default '{}'::jsonb,
  output      jsonb,
  status      public.content_status not null default 'draft',

  -- ⭐ Trazabilidad del RAG: qué reglas concretas se recuperaron y se aplicaron.
  -- Es lo que permite responder "¿por qué el texto dice esto?" con evidencia.
  retrieved_rule_ids text[] not null default '{}',
  langfuse_trace_id  text,

  created_by  uuid not null references public.users(id) on delete restrict,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists content_pieces_brand_idx  on public.content_pieces (brand_id);
create index if not exists content_pieces_status_idx on public.content_pieces (status, created_at desc);


-- ------------------------------------------------- MÓDULO III — Governance
create table if not exists public.approvals (
  id               uuid primary key default gen_random_uuid(),
  content_piece_id uuid not null references public.content_pieces(id) on delete cascade,
  stage            text not null check (stage in ('a', 'b')),
  approver_id      uuid not null references public.users(id) on delete restrict,
  decision         text not null check (decision in ('approved', 'rejected')),
  comment          text not null default '',
  created_at       timestamptz not null default now()
);

create index if not exists approvals_piece_idx on public.approvals (content_piece_id, created_at desc);


create table if not exists public.visual_audits (
  id               uuid primary key default gen_random_uuid(),
  content_piece_id uuid references public.content_pieces(id) on delete cascade,
  brand_id         uuid not null references public.brands(id) on delete cascade,
  image_url        text not null,
  verdict          public.audit_verdict not null,

  -- [{rule_id, verdict, evidence, confidence}] — cada hallazgo CITA la regla del
  -- manual que evaluó. Sin rule_id, la auditoría sería una opinión sin respaldo.
  findings         jsonb not null default '[]'::jsonb,
  checked_rule_ids text[] not null default '{}',

  model             text not null,
  langfuse_trace_id text,
  latency_ms        integer,

  created_by uuid not null references public.users(id) on delete restrict,
  created_at timestamptz not null default now()
);

create index if not exists visual_audits_brand_idx on public.visual_audits (brand_id, created_at desc);


alter table public.content_pieces enable row level security;
alter table public.approvals      enable row level security;
alter table public.visual_audits  enable row level security;

revoke all on all tables in schema public from anon, authenticated;
