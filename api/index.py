"""API de Operaguas Analítica (FastAPI en Vercel, Python). Dueño: Claude-A (T-10).

Contrato: docs/CONTRATOS.md §3. Esta capa solo recibe, valida, delega y responde:
la lógica vive en api/_lib (las carpetas con "_" no se publican como funciones en Vercel).

Rutas:
- GET  /api/salud    → {"ok", "supabase", "llm", "version"}
- POST /api/triage   → T-12 (api/_lib/triage.py)
- POST /api/rag      → T-11 (api/_lib/rag.py)
- GET  /api/importe  → T-03 (api/_lib/tarifas.py, dueño Claude-E)
- POST /api/agente   → T-15 (api/_lib/agente/)

Errores: siempre {"error": {"codigo", "mensaje"}} en español, con el HTTP adecuado.
Éxito HTTP ≠ éxito de negocio: /api/triage responde 200 aunque el LLM falle, pero
con `valido: false`; /api/rag responde `evidencia: false` cuando no hay fuentes.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# En Vercel el archivo se carga como módulo suelto: se agrega la raíz del proyecto
# para que `api._lib` se importe igual que en las pruebas (pipeline/tests).
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fastapi import FastAPI, Query, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from api._lib import dependencias  # noqa: E402
from api._lib.errores import ErrorApi, cuerpo_error, mensaje_validacion  # noqa: E402
from api._lib.agente.agente import EntradaAgente  # noqa: E402
from api._lib.rag import EntradaRag  # noqa: E402
from api._lib.salud import VERSION, revisar_salud  # noqa: E402
from api._lib.triage import EntradaTriage  # noqa: E402

log = logging.getLogger("operaguas.api")

app = FastAPI(
    title="Operaguas Analítica — API",
    version=VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


# ---------------------------------------------------------------- errores
@app.exception_handler(ErrorApi)
async def _error_api(_: Request, exc: ErrorApi):
    return JSONResponse(status_code=exc.http, content=cuerpo_error(exc.codigo, exc.mensaje))


@app.exception_handler(RequestValidationError)
async def _error_validacion(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=cuerpo_error("entrada_invalida", mensaje_validacion(exc.errors())))


@app.exception_handler(ValidationError)
async def _error_pydantic(_: Request, exc: ValidationError):
    # Validaciones hechas dentro de api/_lib (EntradaTriage, EntradaRag).
    return JSONResponse(status_code=422, content=cuerpo_error("entrada_invalida", mensaje_validacion(exc.errors())))


@app.exception_handler(StarletteHTTPException)
async def _error_http(_: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content=cuerpo_error("no_encontrado", "La ruta solicitada no existe en la API."))
    if exc.status_code == 405:
        return JSONResponse(status_code=405, content=cuerpo_error("metodo_no_permitido", "Método HTTP no permitido para esta ruta."))
    return JSONResponse(status_code=exc.status_code, content=cuerpo_error("error_http", str(exc.detail)))


@app.exception_handler(Exception)
async def _error_inesperado(_: Request, exc: Exception):
    # Nunca se devuelve el detalle interno (podría incluir configuración); se registra en el log de Vercel.
    log.exception("error no controlado: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content=cuerpo_error("error_interno", "Ocurrió un error inesperado. Intenta de nuevo en unos minutos."))


# ---------------------------------------------------------------- rutas
@app.get("/api/salud")
def salud() -> dict:
    """HTTP 200 mientras la función viva; los campos dicen qué dependencias responden (#38/#40)."""
    return revisar_salud()


@app.post("/api/triage")
def api_triage(entrada: EntradaTriage) -> dict:
    from api._lib.triage import triage

    salida, detalle = triage(entrada.texto, dependencias.cliente_llm())
    log.info("triage ms=%s valido=%s llm=%s", detalle.get("ms"), salida.valido, detalle.get("llm", {}).get("proveedor"))
    return salida.model_dump()


@app.post("/api/rag")
def api_rag(entrada: EntradaRag) -> dict:
    from api._lib.rag import buscar_en_supabase, responder

    embeddings = dependencias.cliente_embeddings()
    if embeddings is None:
        raise ErrorApi(503, "rag_no_configurado",
                       "El asistente de documentos no está disponible: falta configurar el modelo de embeddings "
                       "(LLM_PROVIDER=gemini, LLM_API_KEY y EMBEDDINGS_MODEL en Vercel).")
    supa = dependencias.cliente_supabase()
    if supa is None:
        raise ErrorApi(503, "supabase_no_configurado",
                       "El asistente de documentos no está disponible: faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en Vercel.")
    try:
        salida, detalle = responder(entrada.pregunta, entrada.k, embeddings, buscar_en_supabase(supa), dependencias.cliente_llm())
    except (ErrorApi, ValidationError):
        raise
    except Exception as exc:  # red, PostgREST o proveedor de embeddings
        log.warning("rag falló: %s", type(exc).__name__)
        raise ErrorApi(502, "rag_no_disponible",
                       "No pude consultar los documentos en este momento. Intenta de nuevo en unos minutos.") from None
    log.info("rag evidencia=%s recuperados=%s sobre_umbral=%s", salida.evidencia, detalle.get("recuperados"), detalle.get("sobre_umbral"))
    return salida.model_dump()


@app.get("/api/importe")
def api_importe(
    tipo_tarifa: str = Query(..., min_length=3, max_length=40),
    consumo_m3: float = Query(..., ge=0, le=100000),
    alcantarillado: bool = Query(False),
    saneamiento: bool = Query(False),
) -> dict:
    from api._lib.tarifas import calcular_importe

    try:
        r = calcular_importe(tipo_tarifa, consumo_m3, alcantarillado, saneamiento)
    except ValueError as exc:
        raise ErrorApi(422, "entrada_invalida", str(exc)) from None
    # Contrato §3: {consumo_facturado, agua, alcantarillado, saneamiento, iva, total}; se agregan periodo y subtotal.
    return {k: r[k] for k in ("periodo", "tipo_tarifa", "consumo_facturado", "agua", "alcantarillado",
                               "saneamiento", "subtotal", "iva", "total")}


@app.post("/api/agente")
def api_agente(entrada: EntradaAgente) -> dict:
    from api._lib.agente.agente import ejecutar_agente, registrador_supabase
    from api._lib.agente.herramientas import Contexto, DatosSupabase
    from api._lib.rag import buscar_en_supabase, responder

    supa = dependencias.cliente_supabase()
    if supa is None:
        raise ErrorApi(503, "supabase_no_configurado",
                       "El agente no está disponible: faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en Vercel.")
    llm, emb = dependencias.cliente_llm(), dependencias.cliente_embeddings()

    def buscar_documentos(pregunta: str, k: int) -> dict:
        if emb is None:
            raise RuntimeError("embeddings no configurados")
        salida, _ = responder(pregunta, k, emb, buscar_en_supabase(supa), llm)
        return salida.model_dump()

    ctx = Contexto(datos=DatosSupabase(supa), buscar_documentos=buscar_documentos if emb else None)
    salida, detalle = ejecutar_agente(entrada.mensaje, entrada.sesion, llm, ctx, registrador_supabase(supa))
    log.info("agente pasos=%s herramientas=%s invalidas=%s errores=%s limite=%s", len(salida.pasos),
             detalle["herramientas_usadas"], detalle["decisiones_invalidas"], detalle["errores_herramienta"],
             detalle["limite_alcanzado"])
    return salida.model_dump(mode="json")
