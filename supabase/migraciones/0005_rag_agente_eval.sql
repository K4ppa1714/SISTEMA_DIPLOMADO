-- 0005_rag_agente_eval: índice RAG (pgvector), bitácora del agente y casos de evaluación.
-- Dueño: Claude-A (CONTRATOS §2.3). NO APLICAR antes del merge a main (regla 4 de CLAUDE.md).
-- EMBEDDINGS_DIM = 768 (decisión #49: Gemini Embedding 2 con outputDimensionality 768;
-- pgvector solo indexa con HNSW hasta 2000 dimensiones en el tipo vector).
-- Sin datos personales: el corpus son documentos públicos o del proyecto.

create extension if not exists vector with schema extensions;

create schema if not exists rag;
create schema if not exists agente;
create schema if not exists eval;

-- ── rag ──────────────────────────────────────────────────────────────────────
create table rag.documentos (
  documento_id uuid primary key,              -- uuid5 determinista: reindexar no duplica
  titulo       text not null check (length(trim(titulo)) > 0),
  tipo         text not null check (tipo in ('tarifa', 'regla', 'norma', 'contrato', 'faq', 'datos')),
  fuente       text not null,                  -- archivo del repo o institución emisora
  url          text,                           -- null solo si el documento vive en el repo
  creado_en    timestamptz not null default now()
);

create table rag.fragmentos (
  fragmento_id uuid primary key,
  documento_id uuid not null references rag.documentos (documento_id) on delete cascade,
  orden        int  not null check (orden >= 0),
  contenido    text not null check (length(trim(contenido)) > 0),
  embedding    extensions.vector(768) not null,
  metadata     jsonb not null default '{}'::jsonb,
  creado_en    timestamptz not null default now(),
  unique (documento_id, orden)
);

-- Similitud coseno (los embeddings llegan normalizados).
create index fragmentos_embedding_hnsw on rag.fragmentos
  using hnsw (embedding extensions.vector_cosine_ops);

create or replace function rag.buscar_fragmentos(consulta extensions.vector(768), k int default 5)
returns table (fragmento_id uuid, documento_id uuid, titulo text, contenido text, similitud double precision)
language sql stable
set search_path = rag, extensions, public
as $$
  select f.fragmento_id, f.documento_id, d.titulo, f.contenido,
         1 - (f.embedding <=> consulta) as similitud
  from rag.fragmentos f
  join rag.documentos d using (documento_id)
  order by f.embedding <=> consulta
  limit greatest(1, least(coalesce(k, 5), 20));
$$;

-- ── agente ───────────────────────────────────────────────────────────────────
create table agente.log (
  id          bigint generated always as identity primary key,
  sesion      uuid not null,
  paso        int  not null check (paso between 1 and 5),   -- límite de 5 pasos (CONTRATOS §4)
  herramienta text not null,
  argumentos  jsonb not null default '{}'::jsonb,
  resultado   jsonb,
  error       text,
  ms          int check (ms >= 0),
  creado_en   timestamptz not null default now(),
  constraint resultado_o_error check (resultado is not null or error is not null)
);
create index log_sesion on agente.log (sesion, paso);

-- ── eval ─────────────────────────────────────────────────────────────────────
-- Un caso sin validado_por NO entra al cálculo de la métrica (CONTRATOS §2.3).
create table eval.rag_preguntas (
  id                    bigint generated always as identity primary key,
  pregunta              text not null unique,
  documento_esperado_id uuid references rag.documentos (documento_id),
  validado_por          text check (validado_por in ('emilio', 'andres')),
  validado_en           timestamptz,
  constraint validacion_completa check ((validado_por is null) = (validado_en is null))
);

create table eval.agente_casos (
  id                     bigint generated always as identity primary key,
  consulta               text not null unique,
  herramientas_esperadas text[] not null check (cardinality(herramientas_esperadas) between 1 and 5),
  multipaso              bool not null default false,
  validado_por           text check (validado_por in ('emilio', 'andres')),
  validado_en            timestamptz,
  constraint validacion_completa check ((validado_por is null) = (validado_en is null))
);

-- ── permisos ─────────────────────────────────────────────────────────────────
-- rag: lectura pública (documentos no personales); escritura solo service_role.
-- agente y eval: solo service_role (la API escribe la bitácora; la web no la lee directo).
grant usage on schema rag to anon, authenticated, service_role;
grant select on all tables in schema rag to anon, authenticated;
grant all on all tables in schema rag to service_role;
grant execute on function rag.buscar_fragmentos(extensions.vector, int) to anon, authenticated, service_role;

grant usage on schema agente, eval to service_role;
grant all on all tables in schema agente, eval to service_role;
grant usage, select on all sequences in schema agente, eval to service_role;

alter table rag.documentos     enable row level security;
alter table rag.fragmentos     enable row level security;
alter table agente.log         enable row level security;
alter table eval.rag_preguntas enable row level security;
alter table eval.agente_casos  enable row level security;

create policy lectura_publica on rag.documentos for select to anon, authenticated using (true);
create policy lectura_publica on rag.fragmentos for select to anon, authenticated using (true);
-- agente.log y eval.*: sin políticas para anon/authenticated → solo service_role (que omite RLS).
