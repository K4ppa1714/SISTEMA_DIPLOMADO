"""Quejas similares: TF-IDF frente a representaciones densas (bloque K).

Pregunta de negocio: al llegar una queja nueva, ¿el sistema encuentra quejas
anteriores del mismo tipo (para reutilizar la respuesta o detectar un brote)?

Métrica: precision@5. Para cada texto de prueba se buscan los 5 textos de
entrenamiento más parecidos (coseno) y se cuenta qué fracción es de la misma
categoría. Se usa la MISMA división por texto único que el clasificador, así
un texto nunca se encuentra a sí mismo.

Representaciones comparadas:
- TF-IDF: coincidencia de palabras (dispersa).
- LSA: TF-IDF reducido con SVD truncado (densa, sin modelo externo).
- Sentence-Transformers (opcional): embeddings de un modelo preentrenado
  multilingüe. Requiere descargar el modelo de Hugging Face; si no hay acceso,
  NO se inventa el resultado: se reporta como "no ejecutado" y el motivo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from pipeline.src.config import SEMILLA
from pipeline.src.nlp.clasificador import cargar_quejas, dividir_por_texto_unico, textos_unicos
from pipeline.src.nlp.texto import normalizar, tokenizar

K = 5
MODELO_ST = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COMPONENTES_LSA = 100


def precision_en_k(emb_consulta: np.ndarray, emb_base: np.ndarray, cat_consulta, cat_base, k: int = K) -> float:
    """Precision@k con similitud coseno. Las matrices deben venir normalizadas (norma L2 = 1)."""
    sim = emb_consulta @ emb_base.T
    if hasattr(sim, "toarray"):
        sim = sim.toarray()
    top = np.argsort(-sim, axis=1)[:, :k]
    cat_base = np.asarray(cat_base)
    aciertos = cat_base[top] == np.asarray(cat_consulta)[:, None]
    return float(aciertos.mean())


def _tfidf(entrena, prueba):
    vec = TfidfVectorizer(tokenizer=tokenizar, token_pattern=None, lowercase=False, sublinear_tf=True)
    return vec, vec.fit_transform(entrena), vec.transform(prueba)


def comparar(df: pd.DataFrame | None = None, usar_sentence_transformers: bool = True) -> list[dict]:
    df = cargar_quejas() if df is None else df
    entrena, prueba = dividir_por_texto_unico(textos_unicos(df))
    filas = []

    _, xe, xp = _tfidf(entrena["descripcion"], prueba["descripcion"])
    filas.append({"representacion": "TF-IDF", "dimension": int(xe.shape[1]), "ejecutado": True,
                  "precision_at_5": round(precision_en_k(xp, xe, prueba["categoria"], entrena["categoria"]), 4)})

    n_comp = min(COMPONENTES_LSA, xe.shape[1] - 1, xe.shape[0] - 1)
    svd = TruncatedSVD(n_components=n_comp, random_state=SEMILLA).fit(xe)
    le, lp = normalize(svd.transform(xe)), normalize(svd.transform(xp))
    filas.append({"representacion": f"LSA (SVD de TF-IDF, {n_comp} dims)", "dimension": int(n_comp), "ejecutado": True,
                  "precision_at_5": round(precision_en_k(lp, le, prueba["categoria"], entrena["categoria"]), 4)})

    if usar_sentence_transformers:
        filas.append(_sentence_transformers(entrena, prueba))
    return filas


def _sentence_transformers(entrena, prueba) -> dict:
    fila = {"representacion": f"Sentence-Transformers ({MODELO_ST.split('/')[-1]})", "ejecutado": False}
    try:
        from sentence_transformers import SentenceTransformer  # dependencia pesada, solo pipeline
        modelo = SentenceTransformer(MODELO_ST)
        ee = modelo.encode([normalizar(t) for t in entrena["descripcion"]], normalize_embeddings=True)
        ep = modelo.encode([normalizar(t) for t in prueba["descripcion"]], normalize_embeddings=True)
    except Exception as exc:  # sin red a Hugging Face, librería ausente, etc.
        fila["motivo"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        return fila
    fila.update(ejecutado=True, dimension=int(ee.shape[1]),
                precision_at_5=round(precision_en_k(ep, ee, prueba["categoria"], entrena["categoria"]), 4))
    return fila
