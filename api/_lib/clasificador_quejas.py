"""Clasificador de quejas en Python puro (TF-IDF + regresión logística exportados de T-14).

Reproduce `TfidfVectorizer(sublinear_tf, norm="l2")` + `LogisticRegression`
multinomial de scikit-learn sin importarlo. La equivalencia se prueba contra
el modelo de sklearn sobre todos los textos (pipeline/tests/test_triage.py).
"""
from __future__ import annotations

import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .texto import tokenizar

RUTA_MODELO = Path(__file__).with_name("modelo_quejas.json")


class ModeloQuejas:
    def __init__(self, datos: dict):
        self.clases: list[str] = datos["clases"]
        self.ngram_min, self.ngram_max = datos["ngram_range"]
        self.sublinear: bool = datos["sublinear_tf"]
        self.indice = {t: i for i, t in enumerate(datos["terminos"])}
        self.idf: list[float] = datos["idf"]
        self.coef: list[list[float]] = datos["coeficientes"]
        self.intercepto: list[float] = datos["interceptos"]
        self.version: str = datos.get("version", "desconocida")

    def _ngramas(self, tokens: list[str]) -> list[str]:
        salida = []
        for n in range(self.ngram_min, self.ngram_max + 1):
            salida += [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
        return salida

    def vectorizar(self, texto: str) -> dict[int, float]:
        conteo = Counter(g for g in self._ngramas(tokenizar(texto)) if g in self.indice)
        vec = {}
        for termino, tf in conteo.items():
            j = self.indice[termino]
            peso = (1.0 + math.log(tf)) if self.sublinear else float(tf)
            vec[j] = peso * self.idf[j]
        norma = math.sqrt(sum(v * v for v in vec.values()))
        return {j: v / norma for j, v in vec.items()} if norma > 0 else {}

    def probabilidades(self, texto: str) -> dict[str, float]:
        x = self.vectorizar(texto)
        z = [b + sum(w[j] * v for j, v in x.items()) for w, b in zip(self.coef, self.intercepto)]
        m = max(z)
        e = [math.exp(v - m) for v in z]
        s = sum(e)
        return {c: p / s for c, p in zip(self.clases, e)}

    def predecir(self, texto: str) -> tuple[str, float, bool]:
        """Devuelve (categoría, probabilidad, hubo_vocabulario).

        Si ningún término del texto está en el vocabulario, el modelo solo
        responde con el intercepto: `hubo_vocabulario=False` avisa que la
        categoría no está sustentada en el texto.
        """
        probas = self.probabilidades(texto)
        cat = max(probas, key=probas.get)
        return cat, probas[cat], bool(self.vectorizar(texto))


@lru_cache(maxsize=1)
def cargar_modelo(ruta: str | None = None) -> ModeloQuejas:
    return ModeloQuejas(json.loads(Path(ruta or RUTA_MODELO).read_text(encoding="utf-8")))
