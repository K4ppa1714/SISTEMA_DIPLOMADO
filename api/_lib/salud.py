"""Chequeo de salud (T-10). Semántica acordada en #38/#40:

- HTTP 200 mientras la función viva (el cuerpo dice qué falla).
- supabase = lectura real de 1 fila de analitica.resultados_vigentes (PostgREST, 3 s máx.).
- llm = LLM_PROVIDER y LLM_API_KEY no vacíos; NO se llama al modelo (costo y cuota).
- ok = supabase and llm.

Se usa httpx directo contra PostgREST (no el SDK) para no cargar el cliente completo
en cada chequeo. La llave usada es la anon/publishable si existe (lo mismo que ve la web);
si no, la service_role.
"""
from __future__ import annotations

import os

import httpx

VERSION = "v1"
TIMEOUT_S = 3.0


def _env(nombre: str) -> str:
    return (os.environ.get(nombre) or "").strip()


def supabase_responde(http: httpx.Client | None = None) -> bool:
    url = _env("SUPABASE_URL") or _env("NEXT_PUBLIC_SUPABASE_URL")
    llave = _env("NEXT_PUBLIC_SUPABASE_ANON_KEY") or _env("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and llave):
        return False
    cliente = http or httpx.Client(timeout=TIMEOUT_S)
    try:
        r = cliente.get(
            f"{url.rstrip('/')}/rest/v1/resultados_vigentes",
            params={"select": "modulo", "limit": "1"},
            headers={"apikey": llave, "Accept-Profile": "analitica"},
            timeout=TIMEOUT_S,
        )
        # HTTP 200 con una lista es éxito de negocio; un 200 con otra cosa no.
        return r.status_code == 200 and isinstance(r.json(), list)
    except (httpx.HTTPError, ValueError):
        return False
    finally:
        if http is None:
            cliente.close()


def llm_configurado() -> bool:
    return bool(_env("LLM_PROVIDER") and _env("LLM_API_KEY"))


def revisar_salud(http: httpx.Client | None = None) -> dict:
    supa = supabase_responde(http)
    llm = llm_configurado()
    return {"ok": supa and llm, "supabase": supa, "llm": llm, "version": VERSION}
