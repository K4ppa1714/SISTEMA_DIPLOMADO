# Tareas

Fuente de verdad del avance. Cada sesión de Claude actualiza **sus** filas en
el mismo PR que cierra la tarea. Estados: `pendiente` · `en curso` ·
`en revisión` (PR abierto) · `hecho` (merge en `main`).

Responsables: **E** = Emilio · **A** = Andrés · **C-E** = Claude-E ·
**C-A** = Claude-A. "Valida" = persona que debe dar el visto bueno antes del merge.

## Fase 0 — Martes 22, noche

| ID | Tarea | Resp. | Depende de | Valida | Estado |
|---|---|---|---|---|---|
| T-00 | Publicar el repo `operaguas-analitica` en GitHub, invitar a Andrés como colaborador, conectar Vercel, exponer `analitica` en la Data API, revisar política de IA | E | — | — | en curso |
| T-00b | ~~Diagnóstico en Odoo.sh y autorización de Operaguas~~ — no aplica: se usa simulación (Plan B) | A | — | — | cancelada |
| T-00c | Portar por PR el código del repo anterior (`src/analisis_datos/`) a `pipeline/src/data/` y agregar `generar_datos.py` con su cabecera de supuestos | A / C-A | T-01 | E | pendiente |
| T-01 | Estructura del repo, `CLAUDE.md`, contratos, `TAREAS.md`, `.gitignore`, `.vercelignore`, migraciones de `coordinacion` y `analitica` (aplicadas) | C-E | — | E, A | hecho (commit inicial) |
| T-02 | ~~Script de exportación de Odoo.sh e IZARNET~~ — no aplica (Plan B) | C-E | — | — | cancelada |

## Fase 1 — Miércoles 23, 08:00–12:00

| ID | Tarea | Bloques | Resp. | Depende de | Valida | Estado |
|---|---|---|---|---|---|---|
| T-02b | ~~Correr la exportación~~ — no aplica (Plan B) | — | A | — | — | cancelada |
| T-03 | Tarifas CEA de los XML a CSV; `calcular_importe`; pruebas | Arquitectura, N | C-E | T-01 | E | en revisión (rama e/T-03-tarifas) |
| T-04 | Pipeline sobre `data/simulados/`: revisar y extender el de Andrés, migración `raw`, carga a Supabase, reglas de censura y columnas prohibidas | A | C-E | T-01 | E (reglas de limpieza) | en revisión (rama e/T-04-pipeline) |
| T-10 | Esqueleto Next.js + FastAPI con `/api/salud` desplegado en Vercel; comprobar tamaño de la función | Despliegue | C-A | T-01 | A | pendiente |
| — | ~~Decisión Plan A o B~~ — se adoptó Plan B (simulación declarada, propuesta #5) | | E, A | — | — | hecho |

## Fase 2 — Miércoles 23, 12:00–20:00

| ID | Tarea | Bloques | Resp. | Depende de | Valida | Estado |
|---|---|---|---|---|---|---|
| T-05 | EDA (distribuciones, segmentos, cartera, quejas) y estadística (H1 Kruskal-Wallis, H2 chi², IC 95 %, correlación) | B, C | C-E | T-04 | E | pendiente |
| T-06 | Serie diaria, tendencia, estacionalidad, rolling, rezagos, cambio de régimen; FFT; DWT (db4) con energía por nivel y reconstrucción; anomalías vs. quejas | D, O, P | C-E | T-04 | E | pendiente |
| T-11 | Migraciones `rag`/`agente`/`eval`; corpus, chunking, embeddings, pgvector; `/api/rag` con fuentes y respuesta sin evidencia | M | C-A | T-10, decisión LLM | A | pendiente |
| T-12 | `/api/triage`: resumen, categoría y prioridad en JSON validado con Pydantic | L | C-A | T-10 | A | pendiente |
| T-13 | Componente único que dibuja `payload`; páginas Inicio, Datos/EDA y Temporal/Espectral | B, UI | C-A | T-10 | A | pendiente |

## Fase 3 — Miércoles 23, 20:00–24:00 → versión 1 completa

| ID | Tarea | Bloques | Resp. | Depende de | Valida | Estado |
|---|---|---|---|---|---|---|
| T-07 | Features justificadas; baseline; regresión logística, Random Forest y Gradient Boosting en `Pipeline` + `TimeSeriesSplit`; predicción por lotes a Supabase | E, F, H | C-E | T-04 | E | pendiente |
| T-08 | K-means (silhouette) + PCA; MLP en PyTorch comparado con Gradient Boosting | G, I | C-E | T-07 | E | pendiente |
| T-14 | TF-IDF + regresión logística para la categoría de queja; embeddings para quejas similares; comparación precision@5 | J, K | C-A | T-04 | A | en revisión (a/T-14-nlp-quejas; Sentence-Transformers pendiente de correr con acceso a Hugging Face) |
| T-15 | Agente: 5 herramientas, dispatcher con validación, registro en `agente.log`, límite de 5 pasos, tarea de varios pasos | N | C-A | T-03, T-07, T-11 | A | pendiente |
| T-16a | Borrador de 30–50 preguntas de RAG con documento esperado | M | C-E borrador · **E valida** | T-11 | E | pendiente |
| T-16b | Borrador de 30–50 consultas del agente con herramientas esperadas | N | C-A borrador · **A valida** | T-15 | A | pendiente |

## Fase 4 — Jueves 24, 08:00–16:00

| ID | Tarea | Bloques | Resp. | Depende de | Valida | Estado |
|---|---|---|---|---|---|---|
| T-09 | Análisis de errores, interpretación y profundidad de los bloques de C-E | F, G, I | C-E | T-07, T-08 | E | pendiente |
| T-16 | Recall@k y MRR del RAG; Tool Selection Accuracy y éxito de tareas del agente (solo casos validados) | M, N | C-A | T-16a, T-16b | E, A | pendiente |
| T-17 | Páginas Modelos (con prueba de predicción), Asistente IA (RAG, triage, agente con sus pasos) y Resultados | UI | C-A | T-13 | A | pendiente |

## Fase 5 — Jueves 24, 16:00–23:59

| ID | Tarea | Bloques | Resp. | Depende de | Valida | Estado |
|---|---|---|---|---|---|---|
| T-20 | Reporte técnico (24 secciones) y tabla de trazabilidad | Doc. | C-E | todas | E | pendiente |
| T-21 | README de 18 puntos con sección "Uso de IA", diagrama de arquitectura, mensajes de error claros | Doc., Arq. | C-A | todas | A | pendiente |
| T-19 | Prueba completa desde otra computadora e incógnito | Despliegue | A | T-17 | — | pendiente |
| — | **23:59 congelar código, tag `v1.0`** | | E | T-19 | — | pendiente |

## Fase 6 — Viernes 25

| ID | Tarea | Resp. | Estado |
|---|---|---|---|
| T-22 | Reporte técnico en PDF | C-E · E valida | pendiente |
| T-23 | Capturas para README y presentación | C-A | pendiente |
| T-24 | Video demo (5–7 min) sobre la URL | A | pendiente |
| T-25 | Presentación y checklist de entrega (11 elementos) | E, A | pendiente |

## Bloque → tarea (para la tabla de trazabilidad)

| Bloque | Tarea | Bloque | Tarea |
|---|---|---|---|
| A Datos/Pandas | T-04 | I Deep Learning | T-08 |
| B EDA | T-05, T-13 | J NLP clásico | T-14 |
| C Estadística | T-05 | K Embeddings | T-14 |
| D Series | T-06 | L LLM | T-12 |
| E Features | T-07 | M RAG | T-11, T-16 |
| F ML supervisado | T-07, T-09 | N Agente | T-15, T-16 |
| G No supervisado | T-08 | O Fourier | T-06 |
| H Pipelines/ensembles | T-07 | P Wavelets | T-06 |
