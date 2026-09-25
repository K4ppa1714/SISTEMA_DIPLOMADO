"""Prioridad de una queja por reglas declaradas (no por modelo).

Por qué reglas: T-14 mostró que en la simulación el texto NO predice la
prioridad (155 de 331 textos tienen prioridades distintas; F1 del modelo
0.179 contra 0.256 del azar; analitica.resultados nlp/prioridad_desde_texto).
Presentar una "prioridad predicha" sería inventar. Estas reglas son una
propuesta explícita y auditable.

VALIDAR: Andrés (dueño de la regla de negocio). Escala del contrato §3:
0 = baja · 1 = normal · 2 = alta · 3 = urgente.
"""
from __future__ import annotations

from .texto import normalizar

NOMBRES = {0: "baja", 1: "normal", 2: "alta", 3: "urgente"}

# Base por categoría: afectación al servicio o a la salud (propuesta).
BASE_POR_CATEGORIA = {
    "sin_agua": 2,       # sin servicio
    "fuga_calle": 2,     # pérdida de agua en red y riesgo en vía pública
    "drenaje": 2,        # riesgo sanitario
    "calidad_agua": 2,   # riesgo sanitario (NOM-127)
    "fuga_toma": 1,
    "baja_presion": 1,
    "medidor": 1,
    "facturacion": 1,
    "atencion": 1,
}
BASE_DESCONOCIDA = 1

# Términos que suben a urgente: población vulnerable o daño físico.
TERMINOS_URGENTES = frozenset({
    "hospital", "clinica", "escuela", "guarderia", "enfermo", "enferma", "enfermos",
    "bebe", "bebes", "embarazada",
    "inunda", "inundado", "inundada", "inundacion", "socavon", "hundimiento", "hundio",
})


def calcular_prioridad(categoria: str, texto: str, riesgo_llm: bool = False) -> tuple[int, list[str]]:
    """Devuelve (prioridad 0–3, motivos). El LLM solo puede SUBIR un nivel, nunca bajarla."""
    base = BASE_POR_CATEGORIA.get(categoria, BASE_DESCONOCIDA)
    motivos = [f"base por categoría {categoria}: {NOMBRES[base]}"]
    prioridad = base
    encontrados = sorted(set(normalizar(texto).split()) & TERMINOS_URGENTES)
    if encontrados:
        prioridad = 3
        motivos.append("términos de urgencia: " + ", ".join(encontrados))
    if riesgo_llm and prioridad < 3:
        prioridad += 1
        motivos.append("el LLM señaló riesgo: +1")
    return prioridad, motivos


# ---------------------------------------------------------------------------
# Reglas de corrección de CATEGORÍA posteriores al modelo (T-12, #72/#76).
# El modelo de T-14 tiene poco vocabulario para dos casos frecuentes en la
# atención real; estas reglas son explícitas, auditables y se reportan en el
# detalle del triage (categoria_modelo contra categoria final). Se evalúan en
# el análisis de errores del bloque L.
# VALIDAR: Andrés.
_VIA_PUBLICA = ("banqueta", "calle", "via publica", "avenida", "esquina", "camellon", "pavimento", "asfalto")
_SALE_AGUA = ("fuga", "sale agua", "brota", "tira agua", "charco", "escurre", "chorro", "se desperdicia")
_SIN_AGUA = ("no hay agua", "sin agua", "no llega agua", "no llega el agua", "no tengo agua", "no tenemos agua",
             "sin servicio de agua", "no sale agua")
_DENTRO = ("dentro de mi casa", "dentro de la casa", "mi toma", "mi medidor", "mi tuberia")


def _contiene(texto: str, frases: tuple[str, ...]) -> list[str]:
    t = f" {texto} "
    return [f for f in frases if f" {f} " in t]


def corregir_categoria(categoria: str, texto: str) -> tuple[str, str | None]:
    """Devuelve (categoría final, motivo de la regla o None si no se aplicó)."""
    t = normalizar(texto)
    via, agua = _contiene(t, _VIA_PUBLICA), _contiene(t, _SALE_AGUA)
    # Solo corrige confusiones entre categorías de agua; nunca toca drenaje, facturación, etc.
    if via and agua and not _contiene(t, _DENTRO) and categoria == "fuga_toma":
        return "fuga_calle", f"regla vía pública: {via[0]} + {agua[0]} → fuga_calle (el modelo dijo {categoria})"
    sin = _contiene(t, _SIN_AGUA)
    if sin and not agua and categoria in ("fuga_calle", "fuga_toma", "baja_presion"):
        return "sin_agua", f"regla sin servicio: «{sin[0]}» sin mención de fuga → sin_agua (el modelo dijo {categoria})"
    return categoria, None
