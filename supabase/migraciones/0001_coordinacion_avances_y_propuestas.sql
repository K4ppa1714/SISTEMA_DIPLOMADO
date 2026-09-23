-- 0001: reportes de avance y atribución de propuestas a la persona que las
-- originó. Aplicada el 2026-09-22 por Claude-E. Ver docs/COMUNICACION.md.

alter table coordinacion.mensajes drop constraint mensajes_tipo_check;
alter table coordinacion.mensajes add constraint mensajes_tipo_check
  check (tipo in ('aviso','avance','pregunta','respuesta','bloqueo','propuesta_cambio','decision','entrega'));

alter table coordinacion.mensajes
  add column propuesto_por text check (propuesto_por in ('emilio','andres'));

comment on column coordinacion.mensajes.propuesto_por is
  'Persona que originó la idea cuando la sesión la retransmite (p. ej. una mejora que Andrés le pidió a Claude-A).';

drop view coordinacion.pendientes;
create view coordinacion.pendientes as
  select id, creado_en, de, para, tipo, tarea, asunto, cuerpo, responde_a,
         estado, requiere_humano, propuesto_por, aprobado_por
  from coordinacion.mensajes
  where estado in ('abierto','leido')
  order by creado_en;

-- Propuestas que esperan decisión de una persona.
create view coordinacion.por_decidir as
  select id, creado_en, de, propuesto_por, tarea, asunto, cuerpo
  from coordinacion.mensajes
  where tipo = 'propuesta_cambio' and aprobado_por is null and estado <> 'descartado'
  order by creado_en;
