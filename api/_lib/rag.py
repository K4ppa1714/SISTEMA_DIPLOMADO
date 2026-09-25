"""Consulta RAG (bloque M): pregunta → embedding → Top-k en pgvector → respuesta con fuentes.

Contrato §3: POST /api/rag {"pregunta", "k"} → {"respuesta", "evidencia", "fuentes": [{"titulo", "fragmento", "similitud"}]}.

Control de alucinaciones:
1. Umbral de similitud: si ningún fragmento supera UMBRAL_SIMILITUD, evidencia=false y la
   respuesta es fija (no se llama al LLM, no se inventa). El umbral se calibra en T-16
   con las preguntas validadas (0.63 por exactitud balanceada); en producción se usa 0.55
   por decisión de producto de Emilio (D-14): menos «no encontré» a cambio de que el
   prompt SIN_EVIDENCIA filtre casi todas las preguntas fuera del corpus.
2. El LLM solo recibe los fragmentos y debe responder "SIN_EVIDENCIA" si no bastan.
3. La salida del LLM se valida (Pydantic); debe citar al menos una fuente existente.
4. Si el LLM falla, se responde con los fragmentos encontrados (extractivo) y se dice.
"""
from __future__ import annotations

import json
import os

from pydantic import BaseModel, Field, ValidationError, field_validator

from .llm import ErrorLLM

UMBRAL_SIMILITUD = float(os.environ.get("RAG_UMBRAL", "0.55"))
K_MAX = 10
SIN_EVIDENCIA = ("No encontré información sobre eso en los documentos disponibles "
                 "(tarifario CEA, reglas del recibo y documentación del proyecto).")


class EntradaRag(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)
    k: int = Field(default=5, ge=1, le=K_MAX)

    @field_validator("pregunta")
    @classmethod
    def _limpia(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("la pregunta es demasiado corta")
        return v


class Fuente(BaseModel):
    titulo: str
    fragmento: str
    similitud: float


class SalidaRag(BaseModel):
    respuesta: str
    evidencia: bool
    fuentes: list[Fuente]


class RespuestaLLM(BaseModel):
    respuesta: str = Field(min_length=1, max_length=1500)
    fuentes_usadas: list[int] = Field(default_factory=list)


def _prompt(fragmentos: list[dict]) -> str:
    contexto = "\n\n".join(f"[{i + 1}] ({f['titulo']})\n{f['contenido']}" for i, f in enumerate(fragmentos))
    return (
        "Respondes preguntas sobre el servicio de agua usando EXCLUSIVAMENTE los fragmentos numerados. "
        "Si los fragmentos no contienen la respuesta, responde exactamente SIN_EVIDENCIA. "
        "No uses conocimiento externo ni inventes cifras. Cita los números de los fragmentos que usaste. "
        'Responde SOLO un objeto JSON: {"respuesta": "texto en español, breve", "fuentes_usadas": [1, 2]}.\n\n'
        f"FRAGMENTOS:\n{contexto}"
    )


def responder(pregunta: str, k: int, embeddings, buscar, llm) -> tuple[SalidaRag, dict]:
    """`embeddings.embeber([texto])`, `buscar(vector, k) -> list[dict]` y `llm.generar_json` se inyectan."""
    entrada = EntradaRag(pregunta=pregunta, k=k)
    detalle = {"umbral": UMBRAL_SIMILITUD, "recuperados": 0, "sobre_umbral": 0, "llm": None}
    vector = embeddings.embeber([entrada.pregunta])[0]
    recuperados = buscar(vector, entrada.k)
    detalle["recuperados"] = len(recuperados)
    utiles = [f for f in recuperados if f["similitud"] >= UMBRAL_SIMILITUD]
    detalle["sobre_umbral"] = len(utiles)
    detalle["top"] = [{"fragmento_id": str(f.get("fragmento_id")), "documento_id": str(f.get("documento_id")),
                       "similitud": round(f["similitud"], 4)} for f in recuperados]
    if not utiles:
        return SalidaRag(respuesta=SIN_EVIDENCIA, evidencia=False, fuentes=[]), detalle

    fuentes = [Fuente(titulo=f["titulo"], fragmento=f["contenido"], similitud=round(f["similitud"], 4)) for f in utiles]
    if llm is None:
        detalle["llm"] = "sin proveedor configurado"
        return SalidaRag(respuesta=_extractiva(utiles), evidencia=True, fuentes=fuentes), detalle
    try:
        crudo = llm.generar_json(_prompt(utiles), entrada.pregunta)
        datos = json.loads(crudo)
        if isinstance(datos, dict) and str(datos.get("respuesta", "")).strip() == "SIN_EVIDENCIA":
            detalle["llm"] = "el LLM indicó que los fragmentos no bastan"
            return SalidaRag(respuesta=SIN_EVIDENCIA, evidencia=False, fuentes=fuentes), detalle
        r = RespuestaLLM.model_validate(datos)
        citadas = [i for i in r.fuentes_usadas if 1 <= i <= len(utiles)]
        if not citadas:
            raise ValueError("la respuesta no cita ninguna fuente válida")
        detalle["llm"] = {"proveedor": getattr(llm, "nombre", None), "citadas": citadas}
        return SalidaRag(respuesta=r.respuesta, evidencia=True, fuentes=[fuentes[i - 1] for i in citadas]), detalle
    except (ErrorLLM, json.JSONDecodeError, ValidationError, ValueError) as exc:
        detalle["llm"] = f"falló: {type(exc).__name__}: {str(exc)[:120]}"
        return SalidaRag(respuesta=_extractiva(utiles), evidencia=True, fuentes=fuentes), detalle


def _extractiva(fragmentos: list[dict]) -> str:
    titulos = "; ".join(dict.fromkeys(f["titulo"] for f in fragmentos))
    return ("No pude generar una respuesta redactada en este momento. "
            f"Estos documentos contienen información relacionada: {titulos}. Revisa los fragmentos citados.")


def buscar_en_supabase(cliente_supabase):
    """Adaptador: rag.buscar_fragmentos vía PostgREST. Requiere el esquema rag en Exposed schemas."""
    def buscar(vector: list[float], k: int) -> list[dict]:
        r = cliente_supabase.schema("rag").rpc("buscar_fragmentos", {"consulta": vector, "k": k}).execute()
        return r.data or []
    return buscar
