"""Embeddings por HTTP (httpx). Lo usan la API (consulta) y el pipeline (indexado).

Gemini (decisión #49), documentación oficial https://ai.google.dev/gemini-api/docs/embeddings:
- POST .../v1beta/models/{modelo}:batchEmbedContents con cabecera x-goog-api-key.
- `outputDimensionality` recorta la dimensión (EMBEDDINGS_DIM = 768).
- gemini-embedding-2 NO acepta `taskType`; por eso no se envía.
- La respuesta trae `embeddings[].values`. Se vuelve a normalizar (L2) aquí para
  que la similitud coseno de pgvector sea comparable sin importar el modelo.

Variables: EMBEDDINGS_MODEL, EMBEDDINGS_DIM, LLM_API_KEY (la misma llave de Gemini).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import httpx

from .llm import ErrorLLM, _post

URL_BATCH = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:batchEmbedContents"
LOTE_MAX = 100


def normalizar_l2(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    if n == 0:
        raise ErrorLLM("embedding nulo (norma 0)")
    return [x / n for x in v]


@dataclass
class EmbeddingsGemini:
    api_key: str
    modelo: str
    dimension: int = 768
    http: httpx.Client | None = None

    def embeber(self, textos: list[str]) -> list[list[float]]:
        salida: list[list[float]] = []
        for i in range(0, len(textos), LOTE_MAX):
            lote = textos[i:i + LOTE_MAX]
            cuerpo = {"requests": [
                {"model": f"models/{self.modelo}", "content": {"parts": [{"text": t}]},
                 "outputDimensionality": self.dimension}
                for t in lote
            ]}
            datos = _post(self.http, URL_BATCH.format(modelo=self.modelo), cuerpo, {"x-goog-api-key": self.api_key})
            vectores = [e.get("values") for e in (datos.get("embeddings") or [])]
            if len(vectores) != len(lote) or any(not v for v in vectores):
                raise ErrorLLM("embeddings: la respuesta no trae un vector por texto")
            if any(len(v) != self.dimension for v in vectores):
                raise ErrorLLM(f"embeddings: dimensión distinta de {self.dimension}")
            salida += [normalizar_l2(v) for v in vectores]
        return salida


def crear_embeddings(entorno: dict | None = None, http: httpx.Client | None = None):
    env = os.environ if entorno is None else entorno
    llave, modelo = env.get("LLM_API_KEY"), env.get("EMBEDDINGS_MODEL")
    if not (llave and modelo) or (env.get("LLM_PROVIDER") or "").lower() != "gemini":
        return None
    return EmbeddingsGemini(llave, modelo, int(env.get("EMBEDDINGS_DIM") or 768), http)
