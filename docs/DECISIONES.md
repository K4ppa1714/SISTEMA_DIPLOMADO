# Decisiones

Registro de lo que ya se aprobó y cambia el plan, un contrato o una regla.
Las propuestas se discuten en `coordinacion.mensajes` (tipo
`propuesta_cambio`); aquí solo entra lo aprobado por Emilio o Andrés. La más
reciente va primero.

| # | Fecha | Decisión | Motivo | Aprobó |
|---|---|---|---|---|
| D-14 | 2026-09-24 | `RAG_UMBRAL` = 0.55 en producción (Vercel) y como valor por omisión en `api/_lib/rag.py`. No es el valor calibrado: la calibración por exactitud balanceada da 0.63 (LOO 72.5 %), pero con 30 % de falsa abstención. Medido sobre las 40 preguntas validadas: con 0.55, falsa abstención 6 % y abstención correcta por umbral 14 %; las preguntas fuera del corpus las filtra sobre todo el prompt SIN_EVIDENCIA, que no está medido por separado | Las similitudes de preguntas con y sin evidencia se enciman (0.50–0.62 contra 0.54–0.79); se prefiere contestar las preguntas que sí tienen respuesta. Mejora futura: embeddings con taskType de consulta y de documento | Emilio (#94) |
| D-13 | 2026-09-24 | T-16a: las 40 preguntas del RAG las valida Andrés (no Emilio), por decisión de Emilio (#85). Andrés también valida los 30 casos del agente (T-16b). Ambos CSV llevan `validado_por` = Andrés tras la pre-revisión de Claude-A contra el corpus y los datos cargados. Andrés corre con su `.env` local el indexado y los tres evaluadores (#84, #87) | Emilio delegó la parte que requiere llaves para cerrar antes del congelamiento | Emilio (#84, #85) y Andrés |
| D-12 | 2026-09-23 | Plan de choque: prioridad a un mínimo defendible en la URL (Datos/EDA, Temporal, Modelos, Quejas, Asistente, README y reporte); el agente va al final. Codex (app de escritorio en el equipo de Emilio) es ejecutor local de Claude-E: instala, ejecuta, prueba y empuja; no decide, no hace merge por su cuenta ni toca llaves. Emilio delegó en el chat los merge de T-01b, T-03 y T-04 (merge commit con su autor) | Falta de avance visible a un día del congelamiento | Emilio |
| D-11 | 2026-09-23 | LLM y embeddings sin costo: Gemini (Flash) para el LLM y Gemini Embedding 2 con `output_dimensionality` = 768 (`EMBEDDINGS_DIM` = 768); Groq `openai/gpt-oss-120b` como respaldo solo del LLM. Ollama queda como comparativo opcional fuera de línea (la rúbrica exige Ollama en la nube si se usa en la app y el plan gratuito de Ollama Cloud de Emilio está agotado). Reemplaza Anthropic + Voyage (#32) | Emilio pidió opciones sin costo; plan gratuito de Gemini con datos simulados sin datos personales (se declara en el README) | Andrés (#49) y Emilio |
| D-10 | 2026-09-23 | El repo en GitHub es `K4ppa1714/SISTEMA_DIPLOMADO`, público (reemplaza el nombre y la visibilidad de D-09). La carpeta local conserva el nombre `operaguas-analitica` | Es el repo que Emilio creó; público para que el evaluador lo revise sin invitación. No contiene llaves ni datos personales | Emilio |
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
