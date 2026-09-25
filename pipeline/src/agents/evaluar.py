"""Evaluación del agente (T-16, bloque N): Tool Selection Accuracy y éxito de tareas.

Uso (con la URL pública, donde viven las llaves; no requiere llaves locales):
    python -m pipeline.src.agents.evaluar --url https://operaguas-analitica.vercel.app
    python -m pipeline.src.agents.evaluar --url ... --subir   # publica agente_eval en analitica

Casos: docs/eval/agente_casos_borrador.csv. Solo cuentan los que tienen
`validado_por` (CONTRATOS §2.3: un caso sin validar no entra a la métrica).
`--incluir-sin-validar` sirve para una corrida exploratoria y lo marca en el payload.

Definiciones (declaradas, sin ajustar después de ver resultados):
- Selección correcta: el CONJUNTO de herramientas que el agente llamó es igual al
  conjunto esperado (el orden y las repeticiones no cuentan).
- TSA = casos con selección correcta / casos evaluados.
- Primera herramienta correcta: la primera llamada es una de las esperadas.
- Éxito de tarea: selección correcta, ningún paso con error, no se alcanzó el
  límite de pasos y hubo respuesta final.
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[3]
CASOS = RAIZ / "docs" / "eval" / "agente_casos_borrador.csv"
FUENTE = "pipeline/src/agents/evaluar.py · docs/eval/agente_casos_borrador.csv · POST /api/agente"


def cargar_casos(ruta: Path = CASOS, incluir_sin_validar: bool = False) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        casos = [
            {"consulta": r["consulta"], "esperadas": [h for h in r["herramientas_esperadas"].split("|") if h],
             "multipaso": r["multipaso"].strip().lower() == "true", "validado_por": (r.get("validado_por") or "").strip()}
            for r in csv.DictReader(f)
        ]
    return casos if incluir_sin_validar else [c for c in casos if c["validado_por"]]


def calificar(caso: dict, respuesta: dict) -> dict:
    pasos = respuesta.get("pasos", [])
    usadas = [p["herramienta"] for p in pasos]
    seleccion = set(usadas) == set(caso["esperadas"])
    con_error = any(isinstance(p.get("resultado"), dict) and "error" in p["resultado"] for p in pasos)
    limite = "límite de" in (respuesta.get("respuesta") or "")
    return {
        "consulta": caso["consulta"], "multipaso": caso["multipaso"],
        "esperadas": "|".join(caso["esperadas"]), "usadas": "|".join(usadas) or "(ninguna)",
        "seleccion_correcta": seleccion,
        "primera_correcta": bool(usadas) and usadas[0] in caso["esperadas"],
        "exito": seleccion and not con_error and not limite and bool(respuesta.get("respuesta")),
        "pasos": len(pasos),
    }


def evaluar(url: str, casos: list[dict], pausa_s: float = 4.0, http: httpx.Client | None = None) -> list[dict]:
    cliente = http or httpx.Client(timeout=90)
    filas = []
    for c in casos:
        t0 = time.perf_counter()
        try:
            r = cliente.post(f"{url.rstrip('/')}/api/agente", json={"mensaje": c["consulta"]})
            datos = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            fila = calificar(c, datos if r.status_code == 200 else {})
            fila["http"] = r.status_code
        except httpx.HTTPError as exc:
            fila = calificar(c, {})
            fila["http"] = f"error {type(exc).__name__}"
        fila["ms"] = round((time.perf_counter() - t0) * 1000)
        filas.append(fila)
        time.sleep(pausa_s)  # respeta el límite gratuito del LLM
    return filas


def _tasa(filas, campo, filtro=lambda f: True):
    sub = [f for f in filas if filtro(f)]
    return round(sum(f[campo] for f in sub) / len(sub), 4) if sub else None


def payloads(filas: list[dict], sin_validar: bool) -> list[dict]:
    nota = " (EXPLORATORIO: incluye casos sin validar)" if sin_validar else ""
    tsa, exito = _tasa(filas, "seleccion_correcta"), _tasa(filas, "exito")
    multi = _tasa(filas, "exito", lambda f: f["multipaso"])
    return [
        {"clave": "tool_selection", "payload": {
            "tipo": "metrica", "titulo": "Agente: selección de herramientas y éxito de tareas" + nota,
            "filas": [
                {"indicador": "casos evaluados", "valor": len(filas)},
                {"indicador": "Tool Selection Accuracy", "valor": tsa},
                {"indicador": "primera herramienta correcta", "valor": _tasa(filas, "primera_correcta")},
                {"indicador": "éxito de tareas", "valor": exito},
                {"indicador": "éxito en tareas multipaso", "valor": multi},
                {"indicador": "pasos promedio", "valor": round(sum(f["pasos"] for f in filas) / len(filas), 2) if filas else None},
            ],
            "conclusion": (f"El agente eligió exactamente las herramientas esperadas en {tsa:.0%} de los casos y completó "
                           f"{exito:.0%} de las tareas sin errores" + (f" ({multi:.0%} en las de varios pasos)." if multi is not None else ".")
                           if filas else "Sin casos validados todavía."),
            "fuente": FUENTE}},
        {"clave": "casos", "payload": {
            "tipo": "tabla", "titulo": "Agente: resultado por caso" + nota,
            "filas": [{k: f[k] for k in ("consulta", "esperadas", "usadas", "seleccion_correcta", "exito", "pasos", "ms")} for f in filas],
            "conclusion": "Cada fila compara las herramientas esperadas (caso validado por una persona) con las que llamó el agente.",
            "fuente": FUENTE}},
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--subir", action="store_true")
    ap.add_argument("--incluir-sin-validar", action="store_true")
    ap.add_argument("--pausa", type=float, default=4.0)
    a = ap.parse_args()
    casos = cargar_casos(incluir_sin_validar=a.incluir_sin_validar)
    if not casos:
        raise SystemExit("No hay casos validados en docs/eval/agente_casos_borrador.csv (columna validado_por).")
    filas = evaluar(a.url, casos, a.pausa)
    from pipeline.src.data.publicar import guardar, subir
    ruta = guardar("agente_eval", payloads(filas, a.incluir_sin_validar))
    print(f"TSA={payloads(filas, False)[0]['payload']['filas'][1]['valor']} · guardado en {ruta}")
    if a.subir:
        subir(ruta)


if __name__ == "__main__":
    main()
