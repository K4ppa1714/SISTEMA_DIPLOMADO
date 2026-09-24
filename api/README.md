# api/ — FastAPI en Vercel (Python)

Dueño: **Claude-A** (T-10, T-11, T-12, T-15), salvo `_lib/tarifas.py` (**Claude-E**, T-03).
Contrato: `docs/CONTRATOS.md` §3. `index.py` solo recibe, valida, delega y responde;
la lógica vive en `_lib/` (Vercel no convierte en función lo que empieza con `_`).

| Ruta | Estado |
|---|---|
| `GET /api/salud` | `{"ok", "supabase", "llm", "version"}`; HTTP 200 mientras la función viva (#38/#40) |
| `POST /api/triage` | T-12; sin LLM responde igual, con `valido: false` |
| `POST /api/rag` | T-11; `503 rag_no_configurado` hasta que existan llave, `EMBEDDINGS_MODEL`, la 0005 y el índice |
| `GET /api/importe` | T-03 (`tarifas.py`) |
| `POST /api/agente` | T-15, pendiente |
| `GET /api/docs` | documentación OpenAPI generada por FastAPI |

Errores: siempre `{"error": {"codigo", "mensaje"}}` en español; los detalles
internos van al log de Vercel, nunca a la respuesta. Pruebas: `pipeline/tests/test_api.py`
(sin red).

## Despliegue (Vercel de Emilio)

`next.config.ts` reenvía `/api/*` a la función `api/index.py` en producción (patrón
de la plantilla oficial *Next.js + FastAPI Starter*). **Verificar en el primer
despliegue:** `GET /api/salud` responde JSON y `GET /api/no-existe` da el 404 en
español de FastAPI. Si el reenvío no funcionara, la alternativa documentada por
Vercel es *Services* (beta), que requiere reorganizar `vercel.json`.

Variables (CONTRATOS §1): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `LLM_PROVIDER`,
`LLM_MODEL`, `LLM_API_KEY`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_DIM`, `GROQ_API_KEY`, `GROQ_MODEL`.
