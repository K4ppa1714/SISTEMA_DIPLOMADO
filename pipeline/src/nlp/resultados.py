"""Arma los payloads de T-14 (CONTRATOS §2.4) y los publica.

Uso:
    python -m pipeline.src.nlp.resultados            # escribe pipeline/artefactos/nlp_resultados.json
    python -m pipeline.src.nlp.resultados --subir    # además hace upsert en analitica.resultados

Todas las cifras y conclusiones salen del cálculo de esta corrida (semilla 42):
no hay números escritos a mano. Para subir se necesitan SUPABASE_URL y
SUPABASE_SERVICE_ROLE_KEY en el entorno (nunca en el repo).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import joblib

from pipeline.src.config import ARTEFACTOS
from pipeline.src.nlp.clasificador import entrenar_y_evaluar, prioridad_desde_texto
from pipeline.src.nlp.similitud import comparar

VERSION = "v0"
FUENTE = "pipeline/src/nlp (T-14) · pipeline/notebooks/07_nlp_quejas.ipynb · data/simulados/quejas.csv (simulación declarada)"


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %"


def construir_payloads() -> list[dict]:
    r = entrenar_y_evaluar()
    prio = prioridad_desde_texto()
    sim = comparar()

    principal = r.metricas[0]
    ponderada = r.metricas[1]
    base = r.metricas[2]
    ingenua = r.metricas[3]
    peores = r.por_categoria.sort_values("f1").head(2)

    filas_metricas = [
        {"Modelo": m["modelo"], "Evaluación": m["evaluacion"], "n prueba": m["n_prueba"],
         "Accuracy": m["accuracy"], "F1 macro": m["f1_macro"]}
        for m in r.metricas
    ]
    filas_metricas.append({
        "Modelo": "TF-IDF + regresión logística",
        "Evaluación": "validación cruzada 5 pliegues (solo entrenamiento)",
        "n prueba": r.n_entrenamiento,
        "Accuracy": None,
        "F1 macro": r.cv_f1_macro_media,
    })

    payloads = [
        ("nlp", "clasificacion_metricas", {
            "tipo": "tabla",
            "titulo": "Clasificación de quejas por categoría: TF-IDF + regresión logística",
            "filas": filas_metricas,
            "conclusion": (
                f"Con división por texto único el modelo logra F1 macro {principal['f1_macro']:.3f} en "
                f"{principal['n_prueba']} textos nunca vistos (línea base {base['f1_macro']:.3f}); ponderado por "
                f"quejas reales baja a {ponderada['f1_macro']:.3f} porque los textos que falla se repiten mucho. "
                f"La división ingenua por fila da {ingenua['f1_macro']:.3f} porque "
                f"{_pct(ingenua['textos_de_prueba_vistos_en_entrenamiento'])} de sus textos de prueba ya estaban "
                f"en entrenamiento: esa cifra es fuga y no se usa."
            ),
            "fuente": FUENTE,
            "parametros": {**r.mejores_parametros, "semilla": 42, "cv_f1_macro_desv": r.cv_f1_macro_desv,
                            "textos_entrenamiento": r.n_entrenamiento, "textos_prueba": r.n_prueba},
        }),
        ("nlp", "f1_por_categoria", {
            "tipo": "barras",
            "titulo": "F1 por categoría de queja (prueba por texto único)",
            "x": {"etiqueta": "Categoría", "valores": r.por_categoria["categoria"].tolist()},
            "y": {"etiqueta": "F1 (0–1)"},
            "series": [{"nombre": "F1", "valores": r.por_categoria["f1"].tolist()}],
            "filas": r.por_categoria.to_dict(orient="records"),
            "conclusion": (
                "Las categorías más débiles son "
                + " y ".join(f"{c} (F1 {f:.2f}, {int(n)} textos de prueba)"
                             for c, f, n in zip(peores["categoria"], peores["f1"], peores["textos_prueba"]))
                + ". Con tan pocos textos de prueba por clase, cada error mueve mucho la cifra."
            ),
            "fuente": FUENTE,
        }),
        ("nlp", "matriz_confusion", {
            "tipo": "tabla",
            "titulo": "Matriz de confusión (filas = real, columnas = predicha)",
            "filas": [{"real": idx, **{c: int(v) for c, v in fila.items()}} for idx, fila in r.matriz.iterrows()],
            "conclusion": _conclusion_matriz(r.matriz),
            "fuente": FUENTE,
        }),
        ("nlp", "palabras_clave", {
            "tipo": "tabla",
            "titulo": "Términos que más empujan a cada categoría (coeficientes del modelo)",
            "filas": r.palabras_clave.rename(columns={"categoria": "Categoría", "terminos": "Términos"}).to_dict(orient="records"),
            "conclusion": (
                "Cada categoría se explica con términos propios de su tipo de problema ("
                + "; ".join(f"{c}: {t.split(', ')[0]}" for c, t in
                            zip(r.palabras_clave["categoria"].head(3), r.palabras_clave["terminos"].head(3)))
                + "…), así que la decisión del modelo se puede revisar término por término."
            ),
            "fuente": FUENTE,
        }),
        ("nlp", "prioridad_desde_texto", {
            "tipo": "tabla",
            "titulo": "¿El texto de la queja determina su prioridad?",
            "filas": [
                {"Indicador": "Textos únicos", "Valor": prio["textos_unicos"]},
                {"Indicador": "Textos con más de una prioridad asignada", "Valor": prio["textos_con_mas_de_una_prioridad"]},
                {"Indicador": "F1 macro TF-IDF + LR (CV agrupada por texto)", "Valor": prio["f1_macro_tfidf"]},
                {"Indicador": "F1 macro azar estratificado", "Valor": prio["f1_macro_azar_estratificado"]},
            ],
            "conclusion": (
                f"{prio['textos_con_mas_de_una_prioridad']} de {prio['textos_unicos']} textos aparecen con prioridades "
                f"distintas y el modelo de texto (F1 {prio['f1_macro_tfidf']:.3f}) no supera al azar "
                f"({prio['f1_macro_azar_estratificado']:.3f}): en esta simulación la prioridad no se deduce del texto. "
                "El triage no debe presentar la prioridad como predicción del texto."
            ),
            "fuente": FUENTE,
        }),
    ]

    ejecutadas = [s for s in sim if s["ejecutado"]]
    pendientes = [s for s in sim if not s["ejecutado"]]
    conclusion_sim = (
        "Precision@5 (vecinos de la misma categoría): "
        + "; ".join(f"{s['representacion']} {s['precision_at_5']:.3f}" for s in ejecutadas) + ". "
    )
    if pendientes:
        conclusion_sim += ("Sentence-Transformers queda pendiente de ejecutar en un entorno con acceso a Hugging Face; "
                           "no se reporta cifra hasta correrlo.")
    payloads.append(("embeddings", "similitud_precision5", {
        "tipo": "barras",
        "titulo": "Búsqueda de quejas similares: precision@5 por representación",
        "x": {"etiqueta": "Representación", "valores": [s["representacion"] for s in ejecutadas]},
        "y": {"etiqueta": "Precision@5 (0–1)"},
        "series": [{"nombre": "Precision@5", "valores": [s["precision_at_5"] for s in ejecutadas]}],
        "filas": sim,
        "conclusion": conclusion_sim,
        "fuente": FUENTE,
    }))

    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    joblib.dump(r.modelo, ARTEFACTOS / "nlp_clasificador_quejas.joblib")
    return [{"modulo": m, "clave": c, "version": VERSION, "payload": p} for m, c, p in payloads]


def _conclusion_matriz(matriz) -> str:
    errores = [(real, pred, int(matriz.loc[real, pred])) for real in matriz.index for pred in matriz.columns
               if real != pred and matriz.loc[real, pred] > 0]
    if not errores:
        return "Sin confusiones en la prueba por texto único."
    return "Confusiones: " + "; ".join(f"{n} de {real} → {pred}" for real, pred, n in errores) + "."


def subir(filas: list[dict]) -> None:
    url, llave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not llave:
        sys.exit("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno; no se subió nada.")
    from supabase import create_client
    cliente = create_client(url, llave)
    cliente.schema("analitica").table("resultados").upsert(filas, on_conflict="modulo,clave,version").execute()


def _nativo(o):
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(f"tipo no serializable: {type(o).__name__}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subir", action="store_true")
    args = ap.parse_args()
    # Ida y vuelta por JSON: convierte tipos de numpy a tipos nativos antes de guardar o subir.
    filas = json.loads(json.dumps(construir_payloads(), ensure_ascii=False, default=_nativo))
    salida = ARTEFACTOS / "nlp_resultados.json"
    salida.write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(filas)} resultados → {salida}")
    if args.subir:
        subir(filas)
        print("upsert en analitica.resultados hecho")


if __name__ == "__main__":
    main()
