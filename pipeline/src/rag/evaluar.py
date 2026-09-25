"""Evaluación del retriever del RAG (T-16, bloque M): Recall@k, MRR y abstención correcta.

Uso (con .env: LLM_PROVIDER=gemini, LLM_API_KEY, EMBEDDINGS_MODEL, EMBEDDINGS_DIM,
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY; y rag.fragmentos ya indexado):
    python -m pipeline.src.rag.evaluar            # guarda pipeline/artefactos/resultados/rag_eval.json
    python -m pipeline.src.rag.evaluar --subir    # además publica en analitica.resultados

Preguntas: docs/eval/rag_preguntas_borrador.csv. Solo cuentan las que tienen
`validado_por` (CONTRATOS §2.3). Definiciones declaradas antes de ver resultados:
- Con evidencia esperada: el acierto es que algún fragmento del Top-k pertenezca a
  `documento_esperado_id`. Recall@k = aciertos en Top-k / preguntas. MRR = promedio
  de 1/posición del primer fragmento correcto (0 si no aparece en el Top-5).
- Sin evidencia esperada: abstención correcta si la mayor similitud queda por
  debajo del umbral de api/_lib/rag.py (así /api/rag responde evidencia=false sin LLM).
- Calibración del umbral (#91 de Claude-E): con las mismas similitudes máximas (sin
  llamadas extra) se barre el umbral de 0.30 a 0.90 y se elige el que maximiza la
  exactitud balanceada = (abstención correcta + (1 − falsa abstención)) / 2; si varios
  empatan se toma la mediana del empate (el punto más alejado de ambos errores).
  Como se calibra con las mismas 40 preguntas, se reporta además una estimación
  honesta por validación dejando una fuera (LOO): cada pregunta se juzga con el umbral
  elegido sin ella.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
PREGUNTAS = RAIZ / "docs" / "eval" / "rag_preguntas_borrador.csv"
KS = (1, 3, 5)
FUENTE = "pipeline/src/rag/evaluar.py · docs/eval/rag_preguntas_borrador.csv · rag.buscar_fragmentos"


def cargar_preguntas(ruta: Path = PREGUNTAS, incluir_sin_validar: bool = False) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        filas = [{"pregunta": r["pregunta"], "esperado": (r.get("documento_esperado_id") or "").strip(),
                  "titulo": r.get("documento_esperado", ""), "con_evidencia": r["espera_evidencia"].strip().lower() == "si",
                  "validado_por": (r.get("validado_por") or "").strip()} for r in csv.DictReader(f)]
    return filas if incluir_sin_validar else [p for p in filas if p["validado_por"]]


def rango(recuperados: list[dict], esperado: str) -> int | None:
    """Posición (1-based) del primer fragmento del documento esperado, o None."""
    for i, f in enumerate(recuperados, 1):
        if str(f.get("documento_id")) == esperado:
            return i
    return None


def calcular(preguntas: list[dict], recuperar, umbral: float) -> tuple[dict, list[dict]]:
    """`recuperar(pregunta) -> list[dict]` con documento_id y similitud, ordenado, Top-5."""
    detalle = []
    for p in preguntas:
        top = recuperar(p["pregunta"])
        r = rango(top, p["esperado"]) if p["con_evidencia"] else None
        detalle.append({"pregunta": p["pregunta"], "con_evidencia": p["con_evidencia"], "posicion": r,
                        "similitud_max": round(max((f["similitud"] for f in top), default=0.0), 4),
                        "abstiene": max((f["similitud"] for f in top), default=0.0) < umbral})
    con = [d for d in detalle if d["con_evidencia"]]
    sin = [d for d in detalle if not d["con_evidencia"]]
    m = {"preguntas_con_evidencia": len(con), "preguntas_sin_evidencia": len(sin), "umbral": umbral}
    for k in KS:
        m[f"recall@{k}"] = round(sum(1 for d in con if d["posicion"] and d["posicion"] <= k) / len(con), 4) if con else None
    m["mrr"] = round(sum(1 / d["posicion"] for d in con if d["posicion"]) / len(con), 4) if con else None
    m["abstencion_correcta"] = round(sum(d["abstiene"] for d in sin) / len(sin), 4) if sin else None
    m["falsa_abstencion"] = round(sum(d["abstiene"] for d in con) / len(con), 4) if con else None
    return m, detalle


UMBRALES = tuple(round(0.30 + 0.01 * i, 2) for i in range(61))


def _barrido(detalle: list[dict], umbrales=UMBRALES) -> list[dict]:
    con = [d["similitud_max"] for d in detalle if d["con_evidencia"]]
    sin = [d["similitud_max"] for d in detalle if not d["con_evidencia"]]
    filas = []
    for u in umbrales:
        ac = sum(s < u for s in sin) / len(sin) if sin else 0.0
        fa = sum(s < u for s in con) / len(con) if con else 0.0
        filas.append({"umbral": u, "abstencion_correcta": round(ac, 4), "falsa_abstencion": round(fa, 4),
                      "exactitud_balanceada": round((ac + 1 - fa) / 2, 4)})
    return filas


def _elegir(filas: list[dict]) -> float:
    mejor = max(f["exactitud_balanceada"] for f in filas)
    empate = [f["umbral"] for f in filas if f["exactitud_balanceada"] == mejor]
    return empate[len(empate) // 2]


def calibrar(detalle: list[dict]) -> dict:
    """Umbral que mejor separa preguntas con y sin evidencia, y su estimación LOO."""
    filas = _barrido(detalle)
    umbral = _elegir(filas)
    aciertos_loo = 0
    for i, d in enumerate(detalle):
        u = _elegir(_barrido(detalle[:i] + detalle[i + 1:]))
        aciertos_loo += (d["similitud_max"] >= u) if d["con_evidencia"] else (d["similitud_max"] < u)
    fila = next(f for f in filas if f["umbral"] == umbral)
    return {"umbral_calibrado": umbral, **{k: v for k, v in fila.items() if k != "umbral"},
            "exactitud_loo": round(aciertos_loo / len(detalle), 4), "barrido": filas}


def payloads(m: dict, detalle: list[dict], exploratorio: bool, cal: dict | None = None) -> list[dict]:
    nota = " (EXPLORATORIO: incluye preguntas sin validar)" if exploratorio else ""
    return [
        {"clave": "recall_mrr", "payload": {
            "tipo": "barras", "titulo": "RAG: Recall@k y MRR del retriever" + nota,
            "x": {"etiqueta": "Métrica", "valores": [f"Recall@{k}" for k in KS] + ["MRR"]},
            "y": {"etiqueta": "Valor (0–1)"},
            "series": [{"nombre": "retriever", "valores": [m[f"recall@{k}"] for k in KS] + [m["mrr"]]}],
            "filas": [{"indicador": k, "valor": v} for k, v in m.items()],
            "conclusion": (f"Con {m['preguntas_con_evidencia']} preguntas, el documento correcto aparece en el Top-5 en "
                           f"{m['recall@5']:.0%} de los casos (MRR {m['mrr']:.2f}); con {m['preguntas_sin_evidencia']} preguntas "
                           f"sin respuesta en los documentos, se abstiene correctamente en {m['abstencion_correcta']:.0%}."
                           if m["recall@5"] is not None and m["abstencion_correcta"] is not None else "Métricas incompletas."),
            "fuente": FUENTE}},
        {"clave": "preguntas", "payload": {
            "tipo": "tabla", "titulo": "RAG: resultado por pregunta" + nota, "filas": detalle,
            "conclusion": "posicion = lugar del primer fragmento del documento esperado en el Top-5 (vacío si no aparece).",
            "fuente": FUENTE}},
    ] + ([{"clave": "umbral", "payload": {
            "tipo": "linea", "titulo": "RAG: calibración del umbral de similitud" + nota,
            "x": {"etiqueta": "Umbral de similitud", "valores": [f["umbral"] for f in cal["barrido"]]},
            "y": {"etiqueta": "Proporción (0–1)"},
            "series": [{"nombre": k.replace("_", " "), "valores": [f[k] for f in cal["barrido"]]}
                       for k in ("abstencion_correcta", "falsa_abstencion", "exactitud_balanceada")],
            "conclusion": (f"El umbral {cal['umbral_calibrado']:.2f} maximiza la exactitud balanceada "
                           f"({cal['exactitud_balanceada']:.0%}: abstención correcta {cal['abstencion_correcta']:.0%}, "
                           f"falsa abstención {cal['falsa_abstencion']:.0%}) frente a {m['umbral']:.2f} declarado. Como se "
                           f"eligió con las mismas preguntas, la estimación honesta es la de dejar una fuera: "
                           f"{cal['exactitud_loo']:.0%}."),
            "fuente": FUENTE}}] if cal else [])


def _embeber_con_espera(emb, textos: list[str], intentos: int = 5, espera_s: float = 30.0) -> list[list[float]]:
    """Una sola llamada por lote (no una por pregunta); si el plan gratuito responde 429, espera y reintenta."""
    import time
    from api._lib.llm import ErrorLLM
    for i in range(intentos):
        try:
            return emb.embeber(textos)
        except ErrorLLM as e:
            if "429" not in str(e) or i == intentos - 1:
                raise
            print(f"Gemini respondió 429 (límite gratuito); espero {espera_s:.0f} s y reintento ({i + 1}/{intentos - 1})", flush=True)
            time.sleep(espera_s)
    raise RuntimeError("inalcanzable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--subir", action="store_true")
    ap.add_argument("--incluir-sin-validar", action="store_true")
    a = ap.parse_args()
    import pipeline.src.config  # noqa: F401  carga el .env de la raíz antes de leer el entorno
    from api._lib.embeddings import crear_embeddings
    from api._lib.rag import UMBRAL_SIMILITUD, buscar_en_supabase
    from supabase import create_client
    import os

    emb = crear_embeddings()
    if emb is None:
        raise SystemExit("Faltan LLM_PROVIDER=gemini, LLM_API_KEY y EMBEDDINGS_MODEL en el entorno.")
    buscar = buscar_en_supabase(create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]))
    preguntas = cargar_preguntas(incluir_sin_validar=a.incluir_sin_validar)
    if not preguntas:
        raise SystemExit("No hay preguntas validadas (columna validado_por).")
    vectores = _embeber_con_espera(emb, [p["pregunta"] for p in preguntas])
    por_pregunta = dict(zip((p["pregunta"] for p in preguntas), vectores))
    m, detalle = calcular(preguntas, lambda q: buscar(por_pregunta[q], max(KS)), UMBRAL_SIMILITUD)
    cal = calibrar(detalle)
    for d in sorted(detalle, key=lambda d: d["similitud_max"]):
        print(f"{d['similitud_max']:.4f}  {'CON' if d['con_evidencia'] else 'SIN'}  pos={d['posicion']}  {d['pregunta'][:70]}")
    print("CALIBRACION:", {k: v for k, v in cal.items() if k != "barrido"})
    from pipeline.src.data.publicar import guardar, subir
    ruta = guardar("rag_eval", payloads(m, detalle, a.incluir_sin_validar, cal))
    print(m, "→", ruta)
    if a.subir:
        subir(ruta)


if __name__ == "__main__":
    main()
