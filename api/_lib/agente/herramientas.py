"""Herramientas del agente (T-15, bloque N). Contrato: docs/CONTRATOS.md §4.

Cada herramienta tiene: nombre, descripción para el LLM, esquema de argumentos
(Pydantic → JSON Schema) y una función que recibe argumentos YA validados.
El dispatcher (agente.py) valida, ejecuta, mide el tiempo y registra.

Nota de ubicación: el contrato decía `api/agente/herramientas.py`, pero en
Vercel cualquier .py dentro de api/ sin "_" se publica como función propia;
por eso vive en `api/_lib/agente/`.

Datos: las herramientas leen Supabase con service_role mediante un objeto
`Datos` inyectable (en pruebas se usa uno falso, sin red).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from ..tarifas import calcular_importe, tipos_de_tarifa

_ID_TOMA = re.compile(r"^[A-Za-z0-9]{6,24}$")
_PERIODO = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ErrorHerramienta(Exception):
    """Error de negocio de una herramienta (dato inexistente, fuente no disponible). Se devuelve al LLM."""


class Datos(Protocol):
    def recibos(self, id_toma: str, n: int) -> list[dict]: ...
    def predicciones(self, id_toma: str, periodo: str | None) -> list[dict]: ...
    def resultados(self, modulo: str) -> list[dict]: ...


# ------------------------------------------------------------------ argumentos
class ArgsIdToma(BaseModel):
    id_toma: str = Field(description="Identificador cifrado de la toma, p. ej. T95A557D58C")

    @field_validator("id_toma")
    @classmethod
    def _formato(cls, v: str) -> str:
        v = v.strip()
        if not _ID_TOMA.match(v):
            raise ValueError("id_toma debe ser alfanumérico de 6 a 24 caracteres")
        return v


class ArgsEstadoCuenta(ArgsIdToma):
    pass


class ArgsPredecirPago(ArgsIdToma):
    periodo: str | None = Field(default=None, description="Periodo AAAA-MM; si se omite, todos los disponibles")

    @field_validator("periodo")
    @classmethod
    def _periodo(cls, v: str | None) -> str | None:
        if v is not None and not _PERIODO.match(v.strip()):
            raise ValueError("periodo debe tener formato AAAA-MM")
        return v.strip() if v else None


class ArgsImporte(BaseModel):
    tipo_tarifa: str = Field(description="Tipo de tarifa CEA, p. ej. domestico_medio o comercial")
    consumo_m3: float = Field(ge=0, le=100000, description="Consumo del periodo en m³")
    alcantarillado: bool = Field(default=False)
    saneamiento: bool = Field(default=False)

    @field_validator("tipo_tarifa")
    @classmethod
    def _tipo(cls, v: str) -> str:
        v = v.strip().lower().replace(" ", "_")
        if v not in tipos_de_tarifa():
            raise ValueError(f"tipo_tarifa no válido; opciones: {', '.join(tipos_de_tarifa())}")
        return v


class ArgsBuscar(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)
    k: int = Field(default=5, ge=1, le=10)


class ArgsSerie(BaseModel):
    analisis: Literal["tendencia", "fourier", "wavelets"]


# ------------------------------------------------------------------ funciones
def _estado_cuenta(a: ArgsEstadoCuenta, ctx: "Contexto") -> dict:
    filas = ctx.datos.recibos(a.id_toma, 6)
    if not filas:
        raise ErrorHerramienta(f"No hay recibos de la toma {a.id_toma} en raw.recibos.")
    pendientes = [f for f in filas if not f.get("pagado")]
    return {
        "id_toma": a.id_toma,
        "recibos": [{k: f.get(k) for k in ("periodo", "fecha_vencimiento", "total_pagar", "pagado", "pago_tardio")} for f in filas],
        "adeudo_total": round(sum(float(f.get("total_pagar") or 0) for f in pendientes), 2),
        "recibos_sin_pagar": len(pendientes),
    }


def _predecir_pago(a: ArgsPredecirPago, ctx: "Contexto") -> dict:
    filas = ctx.datos.predicciones(a.id_toma, a.periodo)
    if not filas:
        raise ErrorHerramienta(f"No hay predicción por lotes para la toma {a.id_toma}"
                               + (f" en {a.periodo}" if a.periodo else "") + ".")
    return {
        "id_toma": a.id_toma,
        "predicciones": [{"periodo": f["periodo"], "prob_pago_tardio": round(float(f["prob_pago_tardio"]), 4),
                          "en_riesgo": bool(f["clase_predicha"]), "modelo": f.get("modelo"), "version": f.get("version")}
                         for f in filas],
        "nota": "Probabilidad de pagar TARDE, calculada por lotes en pipeline/ (analitica.predicciones_pago).",
    }


def _calcular_importe(a: ArgsImporte, ctx: "Contexto") -> dict:
    return calcular_importe(a.tipo_tarifa, a.consumo_m3, a.alcantarillado, a.saneamiento)


def _buscar_documentos(a: ArgsBuscar, ctx: "Contexto") -> dict:
    if ctx.buscar_documentos is None:
        raise ErrorHerramienta("El buscador de documentos (RAG) no está configurado.")
    return ctx.buscar_documentos(a.pregunta, a.k)


_MODULO_SERIE = {"tendencia": "series", "fourier": "fourier", "wavelets": "wavelets"}


def _analizar_serie(a: ArgsSerie, ctx: "Contexto") -> dict:
    filas = ctx.datos.resultados(_MODULO_SERIE[a.analisis])
    if not filas:
        raise ErrorHerramienta(f"No hay resultados publicados del módulo {_MODULO_SERIE[a.analisis]}.")
    return {
        "analisis": a.analisis,
        "hallazgos": [{"clave": f["clave"], "titulo": f["payload"].get("titulo"), "conclusion": f["payload"].get("conclusion")}
                      for f in filas],
    }


# ------------------------------------------------------------------ catálogo
@dataclass
class Contexto:
    datos: Datos
    buscar_documentos: Callable[[str, int], dict] | None = None


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    argumentos: type[BaseModel]
    funcion: Callable[[BaseModel, Contexto], dict]

    def esquema(self) -> dict:
        s = self.argumentos.model_json_schema()
        return {"nombre": self.nombre, "descripcion": self.descripcion,
                "argumentos": {k: {kk: vv for kk, vv in v.items() if kk in ("type", "description", "enum", "default", "anyOf")}
                               for k, v in s.get("properties", {}).items()},
                "obligatorios": s.get("required", [])}


HERRAMIENTAS: dict[str, Herramienta] = {h.nombre: h for h in [
    Herramienta("estado_cuenta", "Recibos recientes, adeudo y pagos tardíos de UNA toma (raw.recibos).",
                ArgsEstadoCuenta, _estado_cuenta),
    Herramienta("calcular_importe", "Calcula el importe de un recibo con el tarifario CEA para un tipo de tarifa y un consumo en m³.",
                ArgsImporte, _calcular_importe),
    Herramienta("predecir_pago", "Probabilidad de que una toma pague TARDE su recibo (predicción por lotes del modelo de pago).",
                ArgsPredecirPago, _predecir_pago),
    Herramienta("buscar_documentos", "Busca en los documentos (tarifario, reglas del recibo, documentación del proyecto) y responde con fuentes.",
                ArgsBuscar, _buscar_documentos),
    Herramienta("analizar_serie", "Conclusiones del análisis temporal del consumo: tendencia/estacionalidad, Fourier (ciclos) o wavelets (fugas).",
                ArgsSerie, _analizar_serie),
]}


class DatosSupabase:
    """Implementación real con el cliente de Supabase (service_role)."""

    def __init__(self, cliente):
        self.c = cliente

    def recibos(self, id_toma: str, n: int) -> list[dict]:
        r = (self.c.schema("raw").table("recibos")
             .select("periodo,fecha_vencimiento,fecha_pago,total_pagar,pagado,pago_tardio")
             .eq("id_toma", id_toma).order("periodo", desc=True).limit(n).execute())
        return r.data or []

    def predicciones(self, id_toma: str, periodo: str | None) -> list[dict]:
        q = (self.c.schema("analitica").table("predicciones_pago")
             .select("periodo,prob_pago_tardio,clase_predicha,modelo,version").eq("id_toma", id_toma))
        if periodo:
            q = q.eq("periodo", periodo)
        return q.order("periodo").execute().data or []

    def resultados(self, modulo: str) -> list[dict]:
        r = (self.c.schema("analitica").table("resultados_vigentes")
             .select("clave,payload").eq("modulo", modulo).order("clave").execute())
        return r.data or []
