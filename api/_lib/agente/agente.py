"""Agente con tool calling (T-15, bloque N).

Diseño (router ReAct con salida JSON validada, sin SDK):
1. En cada paso el LLM recibe el catálogo de herramientas (esquemas JSON), la
   consulta y las observaciones previas, y responde SOLO un JSON:
     {"accion": "herramienta", "herramienta": "<nombre>", "argumentos": {...}}
   o {"accion": "responder", "respuesta": "<texto>"}.
2. El dispatcher valida la decisión (Pydantic), valida los argumentos con el
   esquema de la herramienta, la ejecuta y mide el tiempo. Un error (argumentos
   inválidos, dato inexistente, fuente caída) NO rompe el agente: vuelve al
   LLM como observación para que corrija o explique.
3. Límite duro de 5 pasos (CONTRATOS §4 y CHECK de agente.log). Si se agota,
   se responde con lo obtenido y se dice que se alcanzó el límite.
4. Cada paso se registra en agente.log (best effort: si la bitácora falla, se
   informa en el detalle, no se interrumpe la respuesta).

Éxito HTTP ≠ éxito de negocio: una salida del LLM que no es JSON válido o que
nombra una herramienta inexistente cuenta como paso fallido y se reintenta
dentro del mismo límite.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..llm import ErrorLLM
from ..triage import ocultar_datos_personales
from .herramientas import HERRAMIENTAS, Contexto, ErrorHerramienta

MAX_PASOS = 5
LARGO_OBSERVACION = 1800


class EntradaAgente(BaseModel):
    mensaje: str = Field(min_length=3, max_length=1000)
    sesion: uuid.UUID | None = None

    @field_validator("mensaje")
    @classmethod
    def _limpio(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("el mensaje es demasiado corto")
        return v


class Paso(BaseModel):
    herramienta: str
    argumentos: dict
    resultado: dict
    ms: int


class SalidaAgente(BaseModel):
    """Contrato §3."""
    respuesta: str
    pasos: list[Paso]
    sesion: uuid.UUID


class Decision(BaseModel):
    accion: Literal["herramienta", "responder"]
    herramienta: str | None = None
    argumentos: dict = Field(default_factory=dict)
    respuesta: str | None = Field(default=None, max_length=2000)


def _sistema() -> str:
    catalogo = json.dumps([h.esquema() for h in HERRAMIENTAS.values()], ensure_ascii=False)
    return (
        "Eres el asistente de operación de un organismo operador de agua (datos SIMULADOS). "
        "Decides UNA acción por turno usando SOLO estas herramientas:\n"
        f"{catalogo}\n\n"
        "Responde SOLO un objeto JSON, sin texto extra, con una de estas formas:\n"
        '{"accion": "herramienta", "herramienta": "<nombre>", "argumentos": {...}}\n'
        '{"accion": "responder", "respuesta": "<texto breve en español>"}\n'
        "Reglas: usa herramientas cuando la pregunta dependa de datos, tarifas, documentos o análisis; "
        "si la consulta necesita varias herramientas, llámalas una por turno; "
        "no inventes cifras: usa solo lo que devuelvan las herramientas; "
        "si una herramienta devuelve error, corrige los argumentos o explica el problema; "
        "si la pregunta no tiene relación con el servicio de agua, responde sin herramientas diciendo que no puedes ayudar con eso; "
        f"tienes como máximo {MAX_PASOS} turnos."
    )


def _usuario(mensaje: str, historial: list[dict]) -> str:
    partes = [f"CONSULTA: {mensaje}"]
    for i, h in enumerate(historial, 1):
        obs = json.dumps(h["observacion"], ensure_ascii=False, default=str)
        if len(obs) > LARGO_OBSERVACION:
            obs = obs[:LARGO_OBSERVACION] + "…(recortado)"
        partes.append(f"PASO {i}: {h['herramienta']}({json.dumps(h['argumentos'], ensure_ascii=False)}) → {obs}")
    partes.append("Decide la siguiente acción (JSON).")
    return "\n".join(partes)


def ejecutar_agente(mensaje: str, sesion: uuid.UUID | None, llm, contexto: Contexto,
                    registrar: Callable[[dict], None] | None = None) -> tuple[SalidaAgente, dict]:
    """Devuelve (salida del contrato, detalle para evaluación). Nunca lanza por fallas del LLM o de herramientas."""
    entrada = EntradaAgente(mensaje=mensaje, sesion=sesion)
    sesion_id = entrada.sesion or uuid.uuid4()
    seguro = ocultar_datos_personales(entrada.mensaje)  # regla 2: nada personal al LLM
    detalle = {"decisiones_invalidas": 0, "errores_herramienta": 0, "errores_bitacora": 0, "proveedor": None,
               "herramientas_usadas": [], "limite_alcanzado": False}
    pasos: list[Paso] = []
    historial: list[dict] = []

    if llm is None:
        return SalidaAgente(respuesta="El agente no está disponible: falta configurar el LLM (LLM_PROVIDER y LLM_API_KEY).",
                            pasos=[], sesion=sesion_id), detalle

    for n in range(1, MAX_PASOS + 1):
        try:
            crudo = llm.generar_json(_sistema(), _usuario(seguro, historial))
            detalle["proveedor"] = getattr(llm, "nombre", None)
            decision = Decision.model_validate(json.loads(crudo))
        except ErrorLLM as exc:
            detalle["error_llm"] = str(exc)
            texto = "No pude consultar el modelo de lenguaje en este momento."
            if pasos:
                texto += " Resultados obtenidos hasta ahora: " + "; ".join(p.herramienta for p in pasos) + "."
            return SalidaAgente(respuesta=texto, pasos=pasos, sesion=sesion_id), detalle
        except (json.JSONDecodeError, ValidationError, TypeError):
            detalle["decisiones_invalidas"] += 1
            historial.append({"herramienta": "(ninguna)", "argumentos": {},
                              "observacion": {"error": "Tu salida no fue un JSON válido con la forma pedida."}})
            continue

        if decision.accion == "responder":
            if not decision.respuesta:
                detalle["decisiones_invalidas"] += 1
                historial.append({"herramienta": "(ninguna)", "argumentos": {}, "observacion": {"error": "Falta «respuesta»."}})
                continue
            return SalidaAgente(respuesta=decision.respuesta, pasos=pasos, sesion=sesion_id), detalle

        herramienta = HERRAMIENTAS.get(decision.herramienta or "")
        t0 = time.perf_counter()
        error = None
        if herramienta is None:
            detalle["decisiones_invalidas"] += 1
            resultado = {"error": f"La herramienta «{decision.herramienta}» no existe. Opciones: {', '.join(HERRAMIENTAS)}."}
            error = "herramienta inexistente"
        else:
            try:
                args = herramienta.argumentos.model_validate(decision.argumentos)
                resultado = herramienta.funcion(args, contexto)
            except ValidationError as exc:
                error = "argumentos inválidos"
                resultado = {"error": "Argumentos inválidos: " + "; ".join(
                    f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()[:3])}
            except ErrorHerramienta as exc:
                error = "dato no disponible"
                resultado = {"error": str(exc)}
            except Exception as exc:  # fuente externa caída: se informa sin detalles internos
                error = f"falla de la fuente: {type(exc).__name__}"
                resultado = {"error": "La fuente de datos no respondió."}
        ms = round((time.perf_counter() - t0) * 1000)
        if error:
            detalle["errores_herramienta"] += 1
        nombre = decision.herramienta or "(vacía)"
        detalle["herramientas_usadas"].append(nombre)
        paso = Paso(herramienta=nombre, argumentos=decision.argumentos, resultado=resultado, ms=ms)
        pasos.append(paso)
        historial.append({"herramienta": nombre, "argumentos": decision.argumentos, "observacion": resultado})
        if registrar:
            try:
                registrar({"sesion": str(sesion_id), "paso": n, "herramienta": nombre[:80],
                           "argumentos": decision.argumentos, "resultado": None if error else resultado,
                           "error": error, "ms": ms})
            except Exception:
                detalle["errores_bitacora"] += 1

    detalle["limite_alcanzado"] = True
    usadas = ", ".join(dict.fromkeys(p.herramienta for p in pasos)) or "ninguna"
    return SalidaAgente(
        respuesta=f"Alcancé el límite de {MAX_PASOS} pasos sin una respuesta final. Herramientas consultadas: {usadas}. "
                  "Revisa los resultados de cada paso o reformula la pregunta.",
        pasos=pasos, sesion=sesion_id), detalle


def registrador_supabase(cliente) -> Callable[[dict], None]:
    def registrar(fila: dict) -> None:
        cliente.schema("agente").table("log").insert(fila).execute()
    return registrar
