# Notebooks

Cada notebook usa el código de `pipeline/src/`, se guarda **ejecutado con sus salidas** y termina con una celda **Conclusiones** (3–5 líneas) que pasa al reporte técnico.

| # | Notebook | Dueño | Bloques |
|---|---|---|---|
| 01 | `01_pipeline_datos.ipynb` | Claude-E | A |
| 02 | `02_eda_estadistica.ipynb` | Claude-E | B, C |
| 03 | `03_series_fourier_wavelets.ipynb` | Claude-E / Claude-A (T-06) | D, O, P |
| 04 | `04_modelos.ipynb` | Claude-E | E, F, H |
| 05 | `05_errores.ipynb` | Claude-E | F (análisis de errores) |
| 06 | `06_segmentos_dl.ipynb` | Claude-E | G, I |
| 07 | `07_nlp_quejas.ipynb` | Claude-A | J, K |
| 08 | `08_embeddings.ipynb` | Claude-A | K |
| 09 | `09_rag_evaluacion.ipynb` | Claude-A | M |
| 10 | `10_agente_evaluacion.ipynb` | Claude-A | N |

08–10 se generan con `python pipeline/notebooks/_generar_a.py` y se ejecutan con
`jupyter nbconvert --to notebook --execute --inplace`. Las métricas que requieren llaves
(RAG, agente, LLM) se leen de `pipeline/artefactos/resultados/*.json` cuando el evaluador
ya corrió; si no, el notebook dice que están pendientes y no muestra ningún número.
