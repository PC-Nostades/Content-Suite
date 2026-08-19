-- =============================================================================
-- 0002 — Tablas del Módulo I
-- =============================================================================

-- ---------------------------------------------------------------------- users
create table if not exists public.users (
  id            uuid primary key default gen_random_uuid(),
  email         text        not null,
  password_hash text        not null,
  full_name     text        not null default '',
  role          public.user_role not null default 'creator',
  is_active     boolean     not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Único case-insensitive: el login busca por lower(email).
create unique index if not exists users_email_lower_uidx
  on public.users (lower(email));

drop trigger if exists users_set_updated_at on public.users;
create trigger users_set_updated_at
  before update on public.users
  for each row execute function public.set_updated_at();


-- --------------------------------------------------------------------- brands
create table if not exists public.brands (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  slug       text not null unique,
  category   text not null default '',
  market     text not null default 'PE',
  -- Los "parámetros cortos" que escribió el usuario. Se conservan para poder
  -- regenerar versiones y para mostrar en la UI de qué semilla salió el manual.
  brief      jsonb not null default '{}'::jsonb,
  owner_id   uuid not null references public.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists brands_owner_idx on public.brands (owner_id);
create index if not exists brands_created_idx on public.brands (created_at desc);

drop trigger if exists brands_set_updated_at on public.brands;
create trigger brands_set_updated_at
  before update on public.brands
  for each row execute function public.set_updated_at();


-- -------------------------------------------------------------- brand_manuals
create table if not exists public.brand_manuals (
  id                uuid primary key default gen_random_uuid(),
  brand_id          uuid not null references public.brands(id) on delete cascade,
  version           integer not null,
  status            public.manual_status not null default 'generating',
  stage             public.generation_stage not null default 'queued',

  -- BrandManual (Pydantic) serializado. Se guarda entero ADEMÁS de chunkeado
  -- porque las reglas duras (léxico prohibido, claims) se consultan por SQL
  -- directo: un check de palabra prohibida necesita 100% de recall y la
  -- búsqueda vectorial no lo garantiza.
  content           jsonb,
  input_params      jsonb not null default '{}'::jsonb,
  schema_version    text not null default '1.0',

  -- Trazabilidad
  model             text,
  prompt_version    text,
  langfuse_trace_id text,
  generation_ms     integer,
  error             text,

  created_by        uuid not null references public.users(id) on delete restrict,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  published_at      timestamptz,

  constraint brand_manuals_version_uq unique (brand_id, version)
);

-- Un solo manual publicado por marca: es el que consumen los Módulos II y III.
create unique index if not exists brand_manuals_one_published_uidx
  on public.brand_manuals (brand_id)
  where status = 'published';

create index if not exists brand_manuals_brand_idx
  on public.brand_manuals (brand_id, version desc);

-- Acceso rápido a las reglas duras dentro del JSONB, sin pasar por RAG.
create index if not exists brand_manuals_content_gin
  on public.brand_manuals using gin (content jsonb_path_ops);

drop trigger if exists brand_manuals_set_updated_at on public.brand_manuals;
create trigger brand_manuals_set_updated_at
  before update on public.brand_manuals
  for each row execute function public.set_updated_at();


-- -------------------------------------------------------------- manual_chunks
create table if not exists public.manual_chunks (
  id              uuid primary key default gen_random_uuid(),
  manual_id       uuid not null references public.brand_manuals(id) on delete cascade,
  brand_id        uuid not null references public.brands(id) on delete cascade,

  chunk_index     integer not null,
  section         text    not null,          -- jerárquico y punteado: identidad_visual.logo
  rule_type       public.chunk_rule_type not null,
  modality        public.chunk_modality  not null,
  severity        public.rule_severity   not null default 'soft',

  rule_ids        text[] not null default '{}',
  channel_scope   text[] not null default '{}',
  heading         text   not null default '',
  content         text   not null,
  token_count     integer not null default 0,

  -- 1536 dims: por debajo del límite de 2000 que pgvector puede indexar con el
  -- tipo `vector`. Con las 3072 por defecto de Gemini, el índice HNSW no se crea
  -- y el fallo aparecería recién al usar el RAG en el Módulo II.
  embedding       vector(1536) not null,
  embedding_model text not null,

  metadata        jsonb not null default '{}'::jsonb,

  -- Deja lista la búsqueda híbrida (BM25 + vector) para el Módulo II.
  content_tsv     tsvector generated always as
                    (to_tsvector('spanish', coalesce(heading, '') || ' ' || content)) stored,

  created_at      timestamptz not null default now(),

  constraint manual_chunks_idx_uq unique (manual_id, chunk_index)
);

create index if not exists manual_chunks_manual_idx
  on public.manual_chunks (manual_id);

-- ⭐ El índice que hace posible el pre-filtrado por dominio antes del vector.
create index if not exists manual_chunks_filter_idx
  on public.manual_chunks (brand_id, modality, rule_type);

create index if not exists manual_chunks_rule_ids_gin
  on public.manual_chunks using gin (rule_ids);

create index if not exists manual_chunks_tsv_gin
  on public.manual_chunks using gin (content_tsv);


-- =============================================================================
-- Seguridad: cerrar la puerta de PostgREST
--
-- Usamos JWT propio, no Supabase Auth, y el backend se conecta con un rol que
-- bypassa RLS: la autorización real vive en FastAPI (require_role). Pero la API
-- REST automática de Supabase sigue expuesta — sin esto, cualquiera con la
-- `anon key` (que es pública por diseño) podría leer users.password_hash.
--
-- RLS activado SIN políticas = anon/authenticated no ven absolutamente nada.
-- =============================================================================
alter table public.users         enable row level security;
alter table public.brands        enable row level security;
alter table public.brand_manuals enable row level security;
alter table public.manual_chunks enable row level security;

revoke all on all tables    in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
