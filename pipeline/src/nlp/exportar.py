"""Exporta el clasificador de quejas (T-14) a JSON para usarlo en la API sin scikit-learn.

Por qué: Vercel solo instala el requirements.txt ligero (regla 8 de CLAUDE.md);
la API no puede cargar un .joblib de sklearn. El modelo es lineal, así que
basta guardar vocabulario, idf, coeficientes e interceptos y repetir el
cálculo en Python puro (api/_lib/clasificador_quejas.py).

Uso:  python -m pipeline.src.nlp.exportar
Salida: api/_lib/modelo_quejas.json (sin datos personales: solo términos y pesos).
"""
from __future__ import annotations

import json

from pipeline.src.config import RAIZ
from pipeline.src.nlp.clasificador import entrenar_y_evaluar

SALIDA = RAIZ / "api" / "_lib" / "modelo_quejas.json"
DECIMALES = 8


def exportar(modelo=None) -> dict:
    modelo = modelo or entrenar_y_evaluar().modelo
    tfidf, clf = modelo.named_steps["tfidf"], modelo.named_steps["clf"]
    if tfidf.norm != "l2" or not tfidf.use_idf or not tfidf.smooth_idf:
        raise ValueError("La exportación solo soporta TF-IDF con norm=l2, use_idf y smooth_idf")
    vocab = tfidf.vocabulary_
    terminos = sorted(vocab, key=vocab.get)  # índice i ↔ columna i
    return {
        "version": "v0",
        "fuente": "pipeline/src/nlp/clasificador.py (T-14), semilla 42",
        "ngram_range": list(tfidf.ngram_range),
        "sublinear_tf": bool(tfidf.sublinear_tf),
        "clases": [str(c) for c in clf.classes_],
        "terminos": terminos,
        "idf": [round(float(v), DECIMALES) for v in tfidf.idf_],
        "coeficientes": [[round(float(v), DECIMALES) for v in fila] for fila in clf.coef_],
        "interceptos": [round(float(v), DECIMALES) for v in clf.intercept_],
    }


def main() -> None:
    datos = exportar()
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(datos['terminos'])} términos, {len(datos['clases'])} clases → {SALIDA}")


if __name__ == "__main__":
    main()
