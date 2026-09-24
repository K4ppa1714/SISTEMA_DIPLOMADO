"""Clientes externos creados una vez por instancia de la función (se reutilizan entre peticiones).

Todo sale de variables de entorno (CONTRATOS §1); si falta una, la función devuelve None
y la ruta decide cómo degradar. Nunca se registra ni se devuelve el valor de una llave.
"""
from __future__ import annotations

import os
from functools import lru_cache


def _env(nombre: str) -> str:
    return (os.environ.get(nombre) or "").strip()


@lru_cache(maxsize=1)
def cliente_llm():
    from .llm import crear_cliente
    return crear_cliente()


@lru_cache(maxsize=1)
def cliente_embeddings():
    from .embeddings import crear_embeddings
    return crear_embeddings()


@lru_cache(maxsize=1)
def cliente_supabase():
    """Cliente con service_role (solo servidor). None si falta configuración."""
    url, llave = _env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and llave):
        return None
    from supabase import create_client
    return create_client(url, llave)


def limpiar_cache() -> None:
    """Para pruebas: obliga a releer las variables de entorno."""
    for f in (cliente_llm, cliente_embeddings, cliente_supabase):
        getattr(f, "cache_clear", lambda: None)()
