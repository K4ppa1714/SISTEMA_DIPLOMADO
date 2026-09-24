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


def payloads(m: dict, detalle: list[dict], exploratorio: bool) -> list[dict]:
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
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--subir", action="store_true")
    ap.add_argument("--incluir-sin-validar", action="store_true")
    a = ap.parse_args()
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
    m, detalle = calcular(preguntas, lambda q: buscar(emb.embeber([q])[0], max(KS)), UMBRAL_SIMILITUD)
    from pipeline.src.data.publicar import guardar, subir
    ruta = guardar("rag_eval", payloads(m, detalle, a.incluir_sin_validar))
    print(m, "→", ruta)
    if a.subir:
        subir(ruta)


if __name__ == "__main__":
    main()
