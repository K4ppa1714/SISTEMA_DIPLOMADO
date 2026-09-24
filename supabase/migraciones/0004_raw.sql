-- 0004_raw: datos de la simulación declarada ya limpios (T-04). Dueño: Claude-E.
-- Contrato: docs/CONTRATOS.md §2.1. Sin datos personales: IDs cifrados de la simulación.
-- Diferencias con §2.1 (documentadas en el PR de T-04):
--   * raw.tomas no incluye consumo_base ni propension_mora (parámetros ocultos del generador).
--   * raw.recibos trae los importes recalculados con el tarifario CEA real (decisión de Andrés, #32-5)
--     y tres columnas extra: consumo_facturado, iva y en_entrenamiento (censura por FECHA_CORTE).
-- Solo lectura con service_role (api/ y pipeline/); anon no tiene acceso.

create schema if not exists raw;

create table if not exists raw.tomas (
  id_toma                text primary key,
  privada                text,
  tipo_ocupante          text,
  tipo_tarifa            text not null,
  domiciliado            boolean,
  incluye_alcantarillado boolean,
  incluye_saneamiento    boolean,
  fecha_alta             date
);

create table if not exists raw.recibos (
  id_toma                text not null references raw.tomas (id_toma),
  periodo                text not null,
  fecha_emision          date,
  fecha_vencimiento      date,
  fecha_pago             date,
  pagado                 boolean,
  consumo_m3             double precision,
  consumo_facturado      integer,
  importe_agua           numeric(12,2),
  importe_alcantarillado numeric(12,2),
  importe_saneamiento    numeric(12,2),
  iva                    numeric(12,2),
  total_pagar            numeric(12,2),
  domiciliado            boolean,
  tipo_tarifa            text,
  pago_tardio            boolean,
  en_entrenamiento       boolean not null,
  primary key (id_toma, periodo)
);

create table if not exists raw.lecturas (
  id_toma               text not null,
  periodo               text not null,
  fecha_lectura         date,
  lectura_inicial       double precision,
  lectura_final         double precision,
  consumo_m3            double precision,
  medidor_mudo          boolean,
  lectura_inconsistente boolean,
  tiene_fuga            boolean,          -- solo validación
  primary key (id_toma, periodo)
);

create table if not exists raw.quejas (
  id_queja      text primary key,
  id_toma       text,
  categoria     text,
  descripcion   text,
  canal         text,
  prioridad     text,
  fecha_reporte timestamp
);

create table if not exists raw.telemetria (
  id_toma      text not null,
  marca_tiempo timestamp not null,
  volumen_m3   double precision,
  tiene_fuga   boolean,                   -- solo validación
  primary key (id_toma, marca_tiempo)
);

grant usage on schema raw to service_role;
grant all on all tables in schema raw to service_role;

alter table raw.tomas      enable row level security;
alter table raw.recibos    enable row level security;
alter table raw.lecturas   enable row level security;
alter table raw.quejas     enable row level security;
alter table raw.telemetria enable row level security;
-- Sin políticas para anon/authenticated: solo service_role (que omite RLS) puede leer.
