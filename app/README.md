# app/ — frontend Next.js (App Router)

Dueño: **Claude-A** (T-10, T-13, T-17). Solo presenta: los números salen de
`analitica.resultados_vigentes` (Supabase) y de la API de Python.

| Ruta | Contenido |
|---|---|
| `/` | Preguntas del proyecto, estado de `/api/salud` y de cada módulo |
| `/datos` | pipeline · eda · estadistica |
| `/temporal` | series · fourier · wavelets |
| `/modelos` | ml · clustering · dl + calculadora `GET /api/importe` |
| `/quejas` | nlp · embeddings |
| `/asistente` | `POST /api/triage`, `POST /api/rag` · llm · rag_eval · agente_eval |

- `_componentes/Resultado.tsx`: **componente único** que dibuja cualquier `payload`
  (CONTRATOS §2.4) en SVG, sin librerías de gráficas. Un payload mal armado se ve
  como tarjeta de error y no rompe la página.
- `_lib/payload.ts`: validación de forma (pura, probada con `npm test`).
- `_lib/resultados.ts`: lectura por PostgREST con la llave pública; páginas con ISR de 5 min.
- `_lib/muestra.json`: copia de `pipeline/artefactos/resultados/*.json` para
  desarrollo sin red (`RESULTADOS_MUESTRA=1`). Producción nunca la usa.

## Desarrollo local

```bash
npm install
pip install -r requirements.txt uvicorn
npm run api:dev                      # FastAPI en 127.0.0.1:8000
RESULTADOS_MUESTRA=1 npm run dev     # Next en :3000; /api/* se reenvía a :8000
npm test && npm run typecheck && npm run build
```
