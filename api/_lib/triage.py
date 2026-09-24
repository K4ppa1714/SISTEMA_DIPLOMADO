"""Triage de quejas (T-12, bloque L): resumen, categoría y prioridad con salida validada.

Diseño acordado en #43/#44 (sin cambiar CONTRATOS §3):
- categoria: clasificador de T-14 exportado (Python puro). Métrica propia: F1 macro 0.926.
- resumen: LLM con salida JSON validada por Pydantic; 1 reintento; si falla, resumen
  de respaldo y valido = False (nunca se inventa un resumen).
- prioridad: reglas declaradas (api/_lib/prioridad.py); el LLM solo puede subir 1 nivel.
- valido: True solo si el LLM respondió JSON válido, su categoría coincide con la del
  modelo y el texto tuvo vocabulario conocido.
El LLM SIEMPRE devuelve también su categoría (#44) para medir el acuerdo en T-16.

Control de datos personales (regla 2): antes de enviar el texto al LLM se ocultan
correos y secuencias largas de dígitos (teléfonos, cuentas, CURP/RFC numéricos).
"""
from __future__ import annotations

import json
import re
import time

from pydantic import BaseModel, Field, ValidationError, field_validator

from .clasificador_quejas import cargar_modelo
from .llm import ErrorLLM
from .prioridad import calcular_prioridad, corregir_categoria

LARGO_MIN, LARGO_MAX = 5, 2000
LARGO_RESUMEN = 200
_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_DIGITOS = re.compile(r"(?:\d[\s-]?){8,}")
_RFC_CURP = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,8}\b", re.IGNORECASE)


class EntradaTriage(BaseModel):
    texto: str = Field(min_length=LARGO_MIN, max_length=LARGO_MAX)

    @field_validator("texto")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        v = v.strip()
        if len(v) < LARGO_MIN:
            raise ValueError(f"el texto debe tener al menos {LARGO_MIN} caracteres")
        return v


class SalidaTriage(BaseModel):
    """Exactamente el contrato §3."""
    resumen: str
    categoria: str
    prioridad: int = Field(ge=0, le=3)
    valido: bool


class RespuestaLLM(BaseModel):
    resumen: str = Field(min_length=5, max_length=LARGO_RESUMEN)
    categoria: str
    riesgo: bool = False


def ocultar_datos_personales(texto: str) -> str:
    texto = _CORREO.sub("[correo omitido]", texto)
    texto = _RFC_CURP.sub("[identificador omitido]", texto)
    return _DIGITOS.sub("[número omitido] ", texto).strip()


def _instrucciones(clases: list[str]) -> str:
    return (
        "Eres el asistente de triage del área de atención de un organismo operador de agua. "
        "Recibes el texto de UNA queja ciudadana. Responde SOLO un objeto JSON con estas claves: "
        f'"resumen" (una oración en español, máximo {LARGO_RESUMEN} caracteres, sin nombres, domicilios ni teléfonos), '
        f'"categoria" (exactamente una de: {", ".join(clases)}), '
        '"riesgo" (true solo si el texto describe riesgo para la salud, población vulnerable o daño físico; si no, false). '
        "No agregues información que no esté en el texto. Si el texto no es una queja de agua, usa categoria \"atencion\"."
    )


def _pedir_al_llm(cliente, texto_seguro: str, clases: list[str], intentos: int = 2):
    """Devuelve (RespuestaLLM | None, detalle). Nunca lanza: los errores quedan en el detalle."""
    detalle = {"intentos": 0, "errores": [], "proveedor": None}
    if cliente is None:
        detalle["errores"].append("sin proveedor de LLM configurado")
        return None, detalle
    sistema = _instrucciones(clases)
    for _ in range(intentos):
        detalle["intentos"] += 1
        try:
            crudo = cliente.generar_json(sistema, texto_seguro)
            detalle["proveedor"] = getattr(cliente, "nombre", None)
            resp = RespuestaLLM.model_validate(json.loads(crudo))
            if resp.categoria not in clases:
                raise ValueError(f"categoría fuera del catálogo: {resp.categoria!r}")
            return resp, detalle
        except ErrorLLM as exc:
            detalle["errores"].append(str(exc))
            break  # error del proveedor: no tiene caso reintentar el mismo prompt
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            detalle["errores"].append(f"salida inválida: {type(exc).__name__}")
    return None, detalle


def _resumen_respaldo(texto_seguro: str) -> str:
    t = " ".join(texto_seguro.split())
    return t if len(t) <= LARGO_RESUMEN else t[: LARGO_RESUMEN - 1].rstrip() + "…"


def triage(texto: str, cliente=None) -> tuple[SalidaTriage, dict]:
    """Devuelve (salida del contrato, detalle para bitácora y evaluación)."""
    t0 = time.perf_counter()
    entrada = EntradaTriage(texto=texto)  # ValidationError → la API responde 422 en español
    modelo = cargar_modelo()
    categoria_modelo, proba, con_vocab = modelo.predecir(entrada.texto)
    categoria, regla = corregir_categoria(categoria_modelo, entrada.texto)
    seguro = ocultar_datos_personales(entrada.texto)

    resp, det_llm = _pedir_al_llm(cliente, seguro, modelo.clases)
    riesgo = bool(resp and resp.riesgo)
    prioridad, motivos = calcular_prioridad(categoria, entrada.texto, riesgo)
    acuerdo = bool(resp) and resp.categoria == categoria

    salida = SalidaTriage(
        resumen=resp.resumen if resp else _resumen_respaldo(seguro),
        categoria=categoria,
        prioridad=prioridad,
        valido=bool(resp) and acuerdo and con_vocab,
    )
    detalle = {
        "modelo_version": modelo.version,
        "categoria_modelo": categoria_modelo,
        "regla_categoria": regla,
        "probabilidad_categoria": round(proba, 4),
        "texto_con_vocabulario": con_vocab,
        "categoria_llm": resp.categoria if resp else None,
        "acuerdo_llm_modelo": acuerdo if resp else None,
        "motivos_prioridad": motivos,
        "llm": det_llm,
        "ms": round((time.perf_counter() - t0) * 1000),
    }
    return salida, detalle
