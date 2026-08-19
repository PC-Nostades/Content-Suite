-- =============================================================================
-- 0003 — Índice vectorial y funciones de recuperación
-- =============================================================================

-- HNSW sobre 1536 dims (el tipo `vector` de pgvector indexa hasta 2000).
-- `gemini-embedding-2` ya devuelve los vectores normalizados al truncar
-- dimensiones, así que coseno e inner product son equivalentes aquí.
--
-- Nota de ingeniería: con pocos miles de chunks, Postgres puede preferir un scan
-- exacto cuando el pre-filtro por brand_id es muy selectivo. Eso es CORRECTO y da
-- recall del 100%. El HNSW está para cuando el corpus crezca a muchas marcas.
create index if not exists manual_chunks_embedding_hnsw
  on public.manual_chunks
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);


-- -----------------------------------------------------------------------------
-- match_manual_chunks — búsqueda híbrida estructurada.
--
-- El filtro SQL da PRECISIÓN (nunca recupera del dominio equivocado) y el vector
-- da RECALL semántico dentro del dominio correcto. Es lo que permite que:
--   Módulo II  → p_modalities = {text, both}
--   Módulo III → p_modalities = {visual, both}
-- y que una pregunta sobre el tamaño del logo jamás devuelva reglas de léxico.
-- -----------------------------------------------------------------------------
create or replace function public.match_manual_chunks(
  p_brand_id        uuid,
  p_query_embedding vector(1536),
  p_modalities      public.chunk_modality[]  default null,
  p_rule_types      public.chunk_rule_type[] default null,
  p_severities      public.rule_severity[]   default null,
  p_match_threshold float default 0.30,
  p_match_count     int   default 8,
  p_manual_id       uuid  default null
)
returns table (
  id          uuid,
  manual_id   uuid,
  chunk_index int,
  section     text,
  rule_type   public.chunk_rule_type,
  modality    public.chunk_modality,
  severity    public.rule_severity,
  heading     text,
  content     text,
  rule_ids    text[],
  similarity  float
)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select
    c.id, c.manual_id, c.chunk_index, c.section,
    c.rule_type, c.modality, c.severity, c.heading, c.content, c.rule_ids,
    1 - (c.embedding <=> p_query_embedding) as similarity
  from public.manual_chunks c
  join public.brand_manuals m on m.id = c.manual_id
  where c.brand_id = p_brand_id
    -- Sin manual explícito se consulta el publicado: la fuente de verdad vigente.
    and (
      (p_manual_id is null and m.status = 'published')
      or (p_manual_id is not null and c.manual_id = p_manual_id)
    )
    and (p_modalities is null or c.modality  = any(p_modalities))
    and (p_rule_types is null or c.rule_type = any(p_rule_types))
    and (p_severities is null or c.severity  = any(p_severities))
    and 1 - (c.embedding <=> p_query_embedding) > p_match_threshold
  order by c.embedding <=> p_query_embedding
  limit p_match_count;
$$;


-- -----------------------------------------------------------------------------
-- get_hard_lexicon — reglas DURAS, sin RAG.
--
-- El léxico prohibido NO se verifica por similitud vectorial: necesita 100% de
-- recall y la búsqueda semántica no lo garantiza. El Módulo II carga esta lista
-- completa y la aplica como post-filtro determinista sobre lo que genere el LLM.
-- -----------------------------------------------------------------------------
create or replace function public.get_hard_lexicon(p_brand_id uuid)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  select coalesce(
    jsonb_build_object(
      'forbidden_terms',  coalesce(m.content -> 'verbal' -> 'forbidden_terms',  '[]'::jsonb),
      'forbidden_claims', coalesce(m.content -> 'verbal' -> 'forbidden_claims', '[]'::jsonb),
      'preferred_terms',  coalesce(m.content -> 'verbal' -> 'preferred_terms',  '[]'::jsonb)
    ),
    '{}'::jsonb
  )
  from public.brand_manuals m
  where m.brand_id = p_brand_id
    and m.status = 'published'
  limit 1;
$$;

-- Estas funciones tampoco deben ser invocables desde PostgREST con la anon key.
revoke all on function public.match_manual_chunks from anon, authenticated;
revoke all on function public.get_hard_lexicon   from anon, authenticated;
