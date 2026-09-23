# Contratos entre las dos mitades

Estas interfaces permiten que Claude-E y Claude-A trabajen en paralelo sin
leer el código del otro. **Solo se cambian por PR aprobado por Emilio y
Andrés.** Si un contrato no alcanza, abre un PR que modifique solo este
archivo y espera antes de implementar.

Valores marcados `PENDIENTE` se fijan en cuanto se tome la decisión
correspondiente (ver `docs/TAREAS.md`).

---

## 1. Variables de entorno

Las capturan las personas. Nunca van en el repo.

| Variable | Dónde | Quién la usa |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Vercel | `app/` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Vercel | `app/` (solo lectura, RLS) |
| `SUPABASE_URL` | Vercel y entorno del pipeline | `api/`, `pipeline/` |
| `SUPABASE_SERVICE_ROLE_KEY` | Vercel y entorno del pipeline | `api/`, `pipeline/` (nunca en `app/`) |
| `LLM_PROVIDER` | Vercel y entorno del pipeline | `openai`, `gemini` o `anthropic` — PENDIENTE |
| `LLM_API_KEY` | Vercel y entorno del pipeline | `api/`, `pipeline/src/{nlp,rag,agents}` |
| `LLM_MODEL` | Vercel | modelo económico del proveedor — PENDIENTE |
| `EMBEDDINGS_MODEL` / `EMBEDDINGS_DIM` | Vercel y entorno del pipeline | mismo modelo para indexar y para consultar — PENDIENTE |

---

## 2. Supabase

Proyecto: **operaguas-analitica** (organización "Log-IA"). No es la
producción de Operaguas.

Esquemas expuestos en la API: `analitica` (lectura para `anon` con RLS).
`raw`, `rag`, `agente` y `eval` solo se leen con `service_role` desde
`api/` o `pipeline/`.

Todos los IDs de personas, contratos, medidores y recibos son **texto
cifrado** (hash SHA-256 con sal, primeros 16 caracteres). La sal nunca se
sube al repo.

### 2.1 `raw` — datos simulados tal como llegan (dueño: Claude-E) — PENDIENTE de la propuesta #5

Se carga desde `data/simulados/` con las mismas columnas que los CSV. Llave de
toma: `id_toma`; periodo mensual: `periodo` (`AAAA-MM`).

| Tabla | Columnas |
|---|---|
| `raw.tomas` | `id_toma`, `privada`, `tipo_ocupante`, `tipo_tarifa`, `domiciliado`, `incluye_alcantarillado`, `incluye_saneamiento`, `fecha_alta` (sin `consumo_base` ni `propension_mora`) |
| `raw.lecturas` | `id_toma`, `periodo`, `fecha_lectura`, `lectura_inicial`, `lectura_final`, `consumo_m3`, `medidor_mudo`, `tiene_fuga` (solo validación) |
| `raw.recibos` | `id_toma`, `periodo`, `fecha_emision`, `fecha_vencimiento`, `fecha_pago`, `pagado`, `consumo_m3`, `importe_agua`, `importe_alcantarillado`, `importe_saneamiento`, `total_pagar`, `domiciliado`, `tipo_tarifa`, `pago_tardio` |
| `raw.telemetria` | `id_toma`, `marca_tiempo`, `volumen_m3`, `tiene_fuga` (solo validación) |
| `raw.quejas` | `id_queja`, `id_toma`, `categoria`, `descripcion`, `canal`, `prioridad`, `fecha_reporte` |

Reglas de uso: `data/README.md` y `pipeline/src/config.py`.

### 2.2 `analitica` — APLICADA (migración 0002). Dueño: Claude-E; Claude-A escribe solo los módulos `nlp`, `embeddings`, `llm`, `rag_eval` y `agente_eval`

**`analitica.resultados`**: alimenta todas las gráficas de la app. La app lee
la vista **`analitica.resultados_vigentes`** (la versión más reciente por
`modulo` + `clave`).

| Columna | Tipo | Nota |
|---|---|---|
| `id` | bigint identity | |
| `modulo` | text | `pipeline`, `eda`, `estadistica`, `series`, `fourier`, `wavelets`, `ml`, `clustering`, `dl`, `nlp`, `embeddings`, `llm`, `rag_eval`, `agente_eval` |
| `clave` | text | identificador de la pieza, p. ej. `consumo_por_tarifa` |
| `payload` | jsonb | formato de §2.4; la base exige `tipo`, `titulo`, `conclusion` y `fuente` |
| `version` | text | `v0` preliminar, `v1`, `v2`… |
| `validado_por` | text null | `emilio` o `andres` cuando una persona valida la conclusión |
| `creado_en` | timestamptz | `default now()` |

Clave única: `(modulo, clave, version)`.

| Tabla | Columnas |
|---|---|
| `analitica.series` | `serie`, `ts`, `valor` — formato largo (p. ej. `consumo_horario_total`, `pagos_diarios`) |
| `analitica.predicciones_pago` | `id_toma`, `periodo`, `prob_pago_tardio` (0–1, probabilidad de pagar **tarde**), `clase_predicha`, `modelo`, `version`, `creado_en` |
| `analitica.segmentos` | `id_toma`, `segmento`, `nombre_segmento`, `pc1`, `pc2`, `version` |
| `analitica.anomalias` | `id`, `id_toma`, `ts`, `nivel_wavelet`, `score`, `tipo`, `fuga_real` (validación), `version` |

Permisos: RLS activo; `anon` y `authenticated` solo `SELECT`; escritura con
`service_role`. Para que el front lea con la llave `anon`, el esquema
`analitica` debe estar en *Exposed schemas* de la Data API (Emilio).

### 2.3 `rag`, `agente`, `eval` (dueño: Claude-A)

| Tabla / función | Columnas |
|---|---|
| `rag.documentos` | `documento_id` uuid, `titulo`, `tipo`, `fuente`, `url` |
| `rag.fragmentos` | `fragmento_id` uuid, `documento_id`, `orden`, `contenido`, `embedding vector(EMBEDDINGS_DIM)`, `metadata` jsonb |
| `rag.buscar_fragmentos(consulta vector, k int)` | devuelve `fragmento_id`, `documento_id`, `titulo`, `contenido`, `similitud` |
| `agente.log` | `id`, `sesion` uuid, `paso`, `herramienta`, `argumentos` jsonb, `resultado` jsonb, `error`, `ms`, `creado_en` |
| `eval.rag_preguntas` | `id`, `pregunta`, `documento_esperado_id`, `validado_por`, `validado_en` |
| `eval.agente_casos` | `id`, `consulta`, `herramientas_esperadas` text[], `multipaso` bool, `validado_por`, `validado_en` |

Un caso de evaluación sin `validado_por` **no entra al cálculo de la métrica**.

### 2.4 Formato de `payload`

```json
{
  "tipo": "linea | barras | dispersion | histograma | caja | tabla | texto | metrica",
  "titulo": "Consumo mensual por tipo de tarifa",
  "x": {"etiqueta": "Mes", "valores": ["2026-01", "2026-02"]},
  "y": {"etiqueta": "Consumo (m³)"},
  "series": [{"nombre": "Doméstica Media", "valores": [18.2, 17.9]}],
  "filas": [{"columna": "valor"}],
  "conclusion": "Texto de 1–3 líneas que explica qué muestra y qué significa.",
  "fuente": "pipeline/notebooks/02_eda.ipynb"
}
```

`series` se usa en gráficas, `filas` en tablas. `conclusion` y `fuente` son
obligatorios. La app tiene **un solo componente** que dibuja cualquier
`payload` según `tipo`.

---

## 3. API (`api/index.py`, FastAPI en Vercel) — dueño: Claude-A

Todas las respuestas son JSON. Errores: HTTP 4xx/5xx con
`{"error": {"codigo": "texto_corto", "mensaje": "explicación para el usuario"}}`.

| Método y ruta | Entrada | Salida |
|---|---|---|
| `GET /api/salud` | — | `{"ok": true, "supabase": true, "llm": true, "version": "v1"}` |
| `POST /api/rag` | `{"pregunta": str, "k": int = 5}` | `{"respuesta": str, "evidencia": bool, "fuentes": [{"titulo", "fragmento", "similitud"}]}` |
| `POST /api/triage` | `{"texto": str}` | `{"resumen": str, "categoria": str, "prioridad": "0-3", "valido": bool}` |
| `POST /api/agente` | `{"mensaje": str, "sesion": uuid?}` | `{"respuesta": str, "pasos": [{"herramienta", "argumentos", "resultado", "ms"}], "sesion": uuid}` |
| `GET /api/importe` | `tipo_tarifa`, `consumo_m3`, `alcantarillado`, `saneamiento` | `{"consumo_facturado", "agua", "alcantarillado", "saneamiento", "iva", "total"}` |

`evidencia: false` → la respuesta dice que no encontró información en los
documentos y **no inventa**.

---

## 4. Herramientas del agente

Esquema JSON por herramienta en `api/agente/herramientas.py`. Límite: 5 pasos
por consulta. Cada paso se registra en `agente.log`.

| Herramienta | Argumentos | Fuente |
|---|---|---|
| `estado_cuenta` | `id_toma` | `raw.recibos` |
| `calcular_importe` | `tipo_tarifa`, `consumo_m3`, `alcantarillado`, `saneamiento` | `api/_lib/tarifas.py` |
| `predecir_pago` | `id_toma`, `periodo` opcional | `analitica.predicciones_pago` |
| `buscar_documentos` | `pregunta`, `k` | `rag.buscar_fragmentos` |
| `analizar_serie` | `analisis`: `tendencia`, `fourier` o `wavelets` | `analitica.resultados` |

---

## 5. Reglas de tarifa (`api/_lib/tarifas.py`) — dueño: Claude-E

Portadas de `recibo/models/recibo.py` y `recibo/models/tarifa.py` de
Operaguas; validadas con pruebas contra recibos reales exportados.

```python
def calcular_importe(tipo_tarifa: str, consumo_m3: float,
                     alcantarillado: bool, saneamiento: bool,
                     periodo: str = "2026-T3") -> dict: ...
```

- Consumo facturado = consumo redondeado al entero (medio hacia arriba).
- Importe de agua = tabla CEA por `tipo_tarifa` y m³ del periodo.
- \+10 % del importe de agua si hay alcantarillado; +12 % si hay saneamiento.
- IVA solo para tarifas no domésticas (la tasa se confirma en T-03).
- Función pura: sin red y sin dependencias pesadas.

---

## 6. Artefactos del pipeline

| Archivo | Dueño | Uso |
|---|---|---|
| `pipeline/artefactos/modelo_pago.joblib` | Claude-E | reentrenable con `run_all.py` |
| `pipeline/artefactos/metricas.json` | Claude-E y Claude-A | espejo de `analitica.resultados` para el reporte |
| `data/simulados/*.csv` | Andrés (generador) · Claude-E (pipeline) | entrada única del pipeline |
