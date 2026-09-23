# Decisiones

Registro de lo que ya se aprobó y cambia el plan, un contrato o una regla.
Las propuestas se discuten en `coordinacion.mensajes` (tipo
`propuesta_cambio`); aquí solo entra lo aprobado por Emilio o Andrés. La más
reciente va primero.

| # | Fecha | Decisión | Motivo | Aprobó |
|---|---|---|---|---|
| D-09 | 2026-09-23 | Repo nuevo `operaguas-analitica` en la cuenta de GitHub de Emilio (K4ppa1714), privado, con Andrés como colaborador. El repo anterior `andresoperguas/proyecto-final-analisis-de-datos` se archiva; su código se porta por PR | Que el repo y Vercel estén en la misma cuenta para desplegar en automático | Emilio |
| D-08 | 2026-09-23 | Vercel en la cuenta gratuita de Emilio. El repo nunca se conecta a la Vercel de Andrés. Se restablece D-04: Emilio hace los merge con "Create a merge commit" (no squash) | La cuenta de Vercel de Andrés es empresarial y genera cobros | Emilio |
| D-07 | 2026-09-23 | ~~Repo y Vercel en la cuenta de Andrés~~ — reemplazada por D-08 y D-09 | — | — |
| D-06 | 2026-09-22 | Trabajamos como un solo equipo: cada IA reporta en el buzón avances, propuestas de su persona, pendientes y bloqueos. Una propuesta la aprueba la persona que no la originó | Que las dos personas y las dos IAs sepan en todo momento qué se hizo, qué falta y qué cambió | Emilio (falta confirmación de Andrés) |
| D-05 | 2026-09-22 | Comunicación entre sesiones por el esquema privado `coordinacion` de Supabase; decisiones duraderas en este archivo | Un mensaje en una rama no lo ve la otra sesión hasta el merge; el buzón es inmediato y no genera conflictos | Emilio |
| D-04 | 2026-09-22 | Solo Emilio hace merge a `main` | Vercel en plan gratuito, cuenta personal de Emilio: el autor del commit desplegado debe ser el dueño | Emilio |
| D-03 | 2026-09-22 | Un solo proyecto de Vercel: Next.js (`app/`) + FastAPI en Python (`api/`); trabajo pesado en `pipeline/` fuera de Vercel | Una sola URL; la lógica de datos e IA queda en Python | Emilio |
| D-02 | 2026-09-22 | Supabase: proyecto `dxpcmmxlwlfbodncxhtz` de la organización "Log-IA"; nunca la producción de Operaguas | Aislar el proyecto académico de un sistema en producción | Emilio |
| D-01 | 2026-09-22 | Base del proyecto: datos de Operaguas de Huimilpan, exportados y anonimizados | Único sistema con datos reales y con serie de tiempo, texto etiquetado y documentos para RAG | Emilio y Andrés |

## Pendientes de decidir

- Proveedor del LLM y de embeddings (fija `EMBEDDINGS_DIM` del esquema `rag`).
- Propuesta #5: adoptar la simulación de Andrés (`data/simulados/`) como fuente oficial con 4 condiciones (ver `data/README.md`). Se trabaja con ella mientras se aprueba formalmente.
- Confirmación de Andrés sobre D-06 (modelo de trabajo por el buzón).
