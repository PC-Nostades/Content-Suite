-- =============================================================================
-- 0001 — Extensiones, tipos ENUM y utilidades
-- Ejecutar en el SQL Editor de Supabase, en orden (0001 → 0002 → 0003 → 0004).
-- Es idempotente: se puede volver a correr sin romper nada.
-- =============================================================================

-- pgvector. Se deja sin calificar el esquema a propósito: Supabase incluye tanto
-- `public` como `extensions` en el search_path por defecto, así que el tipo
-- `vector` resuelve viva donde viva la extensión.
create extension if not exists vector;

-- -----------------------------------------------------------------------------
-- Tipos ENUM
-- Los valores DEBEN coincidir exactamente con los de app/core/enums.py.
-- -----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'user_role') then
    create type public.user_role as enum ('creator', 'approver_a', 'approver_b', 'admin');
  end if;

  if not exists (select 1 from pg_type where typname = 'manual_status') then
    create type public.manual_status as enum
      ('generating', 'ready', 'failed', 'published', 'archived');
  end if;

  if not exists (select 1 from pg_type where typname = 'generation_stage') then
    create type public.generation_stage as enum (
      'queued',
      'drafting_strategy',
      'drafting_verbal',
      'drafting_visual',
      'drafting_compliance',
      'postprocessing',
      'chunking',
      'embedding',
      'done'
    );
  end if;

  if not exists (select 1 from pg_type where typname = 'chunk_modality') then
    create type public.chunk_modality as enum ('text', 'visual', 'both');
  end if;

  if not exists (select 1 from pg_type where typname = 'chunk_rule_type') then
    create type public.chunk_rule_type as enum (
      -- dominio textual (Módulo II)
      'strategy', 'audience', 'tone', 'lexicon', 'grammar', 'messaging', 'channel',
      -- dominio visual (Módulo III)
      'color', 'typography', 'logo', 'photography', 'composition', 'iconography', 'packaging',
      -- transversal
      'compliance'
    );
  end if;

  if not exists (select 1 from pg_type where typname = 'rule_severity') then
    create type public.rule_severity as enum ('hard', 'soft');
  end if;
end $$;

-- -----------------------------------------------------------------------------
-- Trigger genérico de updated_at
-- -----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
