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
