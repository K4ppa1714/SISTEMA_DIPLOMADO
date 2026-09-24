"""Publica resultados (payloads de CONTRATOS §2.4) en analitica.resultados.

Cada módulo del pipeline devuelve una lista de dicts {"clave": str, "payload": dict}.
Este módulo:
- valida la forma mínima del payload (tipo, titulo, conclusion, fuente);
- los guarda en pipeline/artefactos/resultados/<modulo>.json (evidencia reproducible);
- sube a Supabase con service_role si hay SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el
  entorno, o escribe un .sql para aplicarlo con el SQL Editor / conector cuando no hay red.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

from pipeline.src.config import ARTEFACTOS

TIPOS = {"linea", "barras", "dispersion", "histograma", "caja", "tabla", "texto", "metrica"}
CARPETA = ARTEFACTOS / "resultados"


def _limpio(v):
    """Convierte tipos de numpy/pandas a JSON estándar (NaN -> None)."""
    if isinstance(v, dict):
        return {k: _limpio(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_limpio(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else float(f"{f:.6g}")
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def validar(payload: dict) -> None:
    faltan = {"tipo", "titulo", "conclusion", "fuente"} - set(payload)
    if faltan:
        raise ValueError(f"payload sin {faltan}")
    if payload["tipo"] not in TIPOS:
        raise ValueError(f"tipo desconocido: {payload['tipo']}")


def guardar(modulo: str, resultados: list[dict], version: str = "v1") -> Path:
    CARPETA.mkdir(parents=True, exist_ok=True)
    salida = []
    for r in resultados:
        payload = _limpio(r["payload"])
        validar(payload)
        salida.append({"modulo": modulo, "clave": r["clave"], "version": version, "payload": payload})
    ruta = CARPETA / f"{modulo}.json"
    ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return ruta


def a_sql(ruta: Path) -> str:
    filas = json.loads(ruta.read_text(encoding="utf-8"))
    valores = []
    for f in filas:
        payload = json.dumps(f["payload"], ensure_ascii=False).replace("'", "''")
        valores.append(f"('{f['modulo']}','{f['clave']}','{payload}'::jsonb,'{f['version']}')")
    return ("insert into analitica.resultados (modulo, clave, payload, version) values\n"
            + ",\n".join(valores)
            + "\non conflict (modulo, clave, version) do update set payload = excluded.payload, "
              "creado_en = now();")


def subir(ruta: Path) -> None:
    """Sube con service_role si hay variables de entorno; si no, deja el .sql junto al .json."""
    url, llave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and llave):
        sql = ruta.with_suffix(".sql")
        sql.write_text(a_sql(ruta), encoding="utf-8")
        print(f"Sin credenciales: SQL listo en {sql}")
        return
    from supabase import create_client

    filas = json.loads(ruta.read_text(encoding="utf-8"))
    cliente = create_client(url, llave)
    cliente.schema("analitica").table("resultados").upsert(
        filas, on_conflict="modulo,clave,version").execute()
    print(f"analitica.resultados: {len(filas)} filas de {ruta.stem}")
