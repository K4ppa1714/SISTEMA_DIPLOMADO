-- 0002_analitica: resultados del pipeline que la app lee.
-- Aplicada el 2026-09-23 por Claude-E (antes de existir el repo, a petición de Claude-A para T-13).
-- Datos simulados (sin datos personales): lectura pública de solo consulta.

create schema if not exists analitica;

create table analitica.resultados (
  id           bigint generated always as identity primary key,
  modulo       text not null check (modulo in ('pipeline','eda','estadistica','series','fourier','wavelets','ml','clustering','dl','nlp','embeddings','llm','rag_eval','agente_eval')),
  clave        text not null,
  payload      jsonb not null,
  version      text not null default 'v1',
  validado_por text check (validado_por in ('emilio','andres')),
  creado_en    timestamptz not null default now(),
  unique (modulo, clave, version),
  constraint payload_minimo check (payload ? 'tipo' and payload ? 'titulo' and payload ? 'conclusion' and payload ? 'fuente')
);

-- Series de tiempo en formato largo (horaria de telemetría, diaria de pagos, etc.)
create table analitica.series (
  serie  text not null,
  ts     timestamptz not null,
  valor  double precision,
  primary key (serie, ts)
);

create table analitica.predicciones_pago (
  id_toma           text not null,
  periodo           text not null,
  prob_pago_tardio  double precision not null check (prob_pago_tardio between 0 and 1),
  clase_predicha    boolean not null,
  modelo            text not null,
  version           text not null default 'v1',
  creado_en         timestamptz not null default now(),
  primary key (id_toma, periodo, version)
);

create table analitica.segmentos (
  id_toma          text not null,
  segmento         int not null,
  nombre_segmento  text,
  pc1              double precision,
  pc2              double precision,
  version          text not null default 'v1',
  primary key (id_toma, version)
);

create table analitica.anomalias (
  id            bigint generated always as identity primary key,
  id_toma       text,
  ts            timestamptz not null,
  nivel_wavelet int,
  score         double precision,
  tipo          text,
  fuga_real     boolean,
  version       text not null default 'v1'
);

-- Versión más reciente de cada resultado (la que muestra la app).
create view analitica.resultados_vigentes with (security_invoker = true) as
  select distinct on (modulo, clave) *
  from analitica.resultados
  order by modulo, clave, creado_en desc;

grant usage on schema analitica to anon, authenticated, service_role;
grant select on all tables in schema analitica to anon, authenticated;
grant all on all tables in schema analitica to service_role;
grant usage, select on all sequences in schema analitica to service_role;

alter table analitica.resultados        enable row level security;
alter table analitica.series            enable row level security;
alter table analitica.predicciones_pago enable row level security;
alter table analitica.segmentos         enable row level security;
alter table analitica.anomalias         enable row level security;

create policy lectura_publica on analitica.resultados        for select to anon, authenticated using (true);
create policy lectura_publica on analitica.series            for select to anon, authenticated using (true);
create policy lectura_publica on analitica.predicciones_pago for select to anon, authenticated using (true);
create policy lectura_publica on analitica.segmentos         for select to anon, authenticated using (true);
create policy lectura_publica on analitica.anomalias         for select to anon, authenticated using (true);
