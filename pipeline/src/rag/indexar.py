"""Indexa el corpus en rag.documentos / rag.fragmentos (pgvector).

Uso:
    python -m pipeline.src.rag.indexar --seco     # solo corpus y fragmentos → artefactos/rag_corpus.json
    python -m pipeline.src.rag.indexar            # además embeddings (Gemini) + upsert en Supabase

Idempotente: los IDs son uuid5 de (fuente, título, orden); reindexar reemplaza, no duplica.
Requiere (solo sin --seco): LLM_PROVIDER=gemini, LLM_API_KEY, EMBEDDINGS_MODEL,
EMBEDDINGS_DIM, SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el entorno.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from api._lib.embeddings import crear_embeddings
from pipeline.src.config import ARTEFACTOS
from pipeline.src.rag.corpus import construir_corpus


def filas(docs, vectores=None):
    documentos, fragmentos, i = [], [], 0
    for d in docs:
        documentos.append({"documento_id": d.documento_id, "titulo": d.titulo, "tipo": d.tipo,
                           "fuente": d.fuente, "url": d.url})
        for orden, contenido in enumerate(d.fragmentos):
            f = {"fragmento_id": d.fragmento_id(orden), "documento_id": d.documento_id, "orden": orden,
                 "contenido": contenido, "metadata": {"fuente": d.fuente, "tipo": d.tipo, "caracteres": len(contenido)}}
            if vectores is not None:
                f["embedding"] = vectores[i]
            fragmentos.append(f)
            i += 1
    return documentos, fragmentos


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seco", action="store_true")
    args = ap.parse_args()
    docs = construir_corpus()
    documentos, fragmentos = filas(docs)
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    (ARTEFACTOS / "rag_corpus.json").write_text(
        json.dumps({"documentos": documentos, "fragmentos": fragmentos}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(documentos)} documentos, {len(fragmentos)} fragmentos → artefactos/rag_corpus.json")
    if args.seco:
        return
    emb = crear_embeddings()
    url, llave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if emb is None or not (url and llave):
        sys.exit("Falta configuración de embeddings o de Supabase; no se indexó nada (usa --seco para probar).")
    vectores = emb.embeber([f["contenido"] for f in fragmentos])
    documentos, fragmentos = filas(docs, vectores)
    from supabase import create_client
    rag = create_client(url, llave).schema("rag")
    rag.table("documentos").upsert(documentos, on_conflict="documento_id").execute()
    rag.table("fragmentos").upsert(fragmentos, on_conflict="fragmento_id").execute()
    print(f"upsert hecho: {len(documentos)} documentos, {len(fragmentos)} fragmentos con embeddings de {emb.dimension} dims")


if __name__ == "__main__":
    main()
