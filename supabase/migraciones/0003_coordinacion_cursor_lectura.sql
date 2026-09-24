-- 0003: cursor de lectura por lector del buzón.
-- Creada en la base el 2026-09-23 por la sesión de Andrés (Claude-A);
-- versionada aquí por Claude-E para que el buzón sea reproducible.
-- Cada lector guarda el último id de coordinacion.mensajes que ya procesó,
-- sin tocar mensajes.estado (que es compartido).

create table if not exists coordinacion.cursor_lectura (
  lector          text primary key,
  ultimo_id       bigint not null default 0 check (ultimo_id >= 0),
  actualizado_en  timestamptz not null default now()
);

comment on table coordinacion.cursor_lectura is
  'Cursor por lector: último id de coordinacion.mensajes ya procesado. Independiente de mensajes.estado (que es compartido).';

alter table coordinacion.cursor_lectura enable row level security;
-- Sin políticas: anon y authenticated no ven nada.
