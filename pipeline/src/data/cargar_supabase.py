"""Carga las tablas limpias de T-04 al esquema raw de Supabase.

Dos modos:
- Directo (recomendado): con SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el
  entorno (nunca en el repo), sube todas las tablas por la API de Supabase.
      python -m pipeline.src.data.cargar_supabase
- SQL (respaldo): escribe archivos INSERT en pipeline/artefactos/sql_raw/ para
  aplicarlos con el SQL Editor o el conector de Supabase cuando no hay red
  directa. Por tamaño, en este modo se cargan tomas completas y los recibos de
  los últimos N periodos (los que consulta la herramienta estado_cuenta).
      python -m pipeline.src.data.cargar_supabase --sql --periodos 3
"""
from __future__ import annotations

import argparse
import math
import os

import pandas as pd

from pipeline.src.config import ARTEFACTOS
from pipeline.src.data.limpieza import ejecutar

COLUMNAS = {
    "tomas": ["id_toma", "privada", "tipo_ocupante", "tipo_tarifa", "domiciliado",
              "incluye_alcantarillado", "incluye_saneamiento", "fecha_alta"],
    "recibos": ["id_toma", "periodo", "fecha_emision", "fecha_vencimiento", "fecha_pago", "pagado",
                "consumo_m3", "consumo_facturado", "importe_agua", "importe_alcantarillado",
                "importe_saneamiento", "iva", "total_pagar", "domiciliado", "tipo_tarifa",
                "pago_tardio", "en_entrenamiento"],
    "lecturas": ["id_toma", "periodo", "fecha_lectura", "lectura_inicial", "lectura_final",
                 "consumo_m3", "medidor_mudo", "lectura_inconsistente", "tiene_fuga"],
    "quejas": ["id_queja", "id_toma", "categoria", "descripcion", "canal", "prioridad", "fecha_reporte"],
    "telemetria": ["id_toma", "marca_tiempo", "volumen_m3", "tiene_fuga"],
}


def _sql_valor(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA or v is pd.NaT:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(round(v, 4)) if isinstance(v, float) else str(v)
    if isinstance(v, pd.Timestamp):
        return f"'{v.isoformat(sep=' ')}'" if (v.hour or v.minute) else f"'{v.date()}'"
    return "'" + str(v).replace("'", "''") + "'"


def a_sql(tabla: str, df: pd.DataFrame, lote: int = 500) -> list[str]:
    cols = COLUMNAS[tabla]
    df = df[cols].astype(object).where(df[cols].notna(), None)
    sentencias = []
    for i in range(0, len(df), lote):
        filas = ",\n".join("(" + ",".join(_sql_valor(v) for v in fila) + ")"
                           for fila in df.iloc[i:i + lote].itertuples(index=False))
        sentencias.append(f"insert into raw.{tabla} ({', '.join(cols)}) values\n{filas}\n"
                          f"on conflict do nothing;")
    return sentencias


def cargar_directo(tablas: dict[str, pd.DataFrame]) -> None:
    from supabase import create_client  # dependencia del pipeline, no de Vercel

    cliente = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    for tabla in ["tomas", "recibos", "lecturas", "quejas", "telemetria"]:
        df = tablas[tabla][COLUMNAS[tabla]].copy()
        for c in df.select_dtypes(include=["datetime64[ns]"]).columns:
            df[c] = df[c].dt.strftime("%Y-%m-%dT%H:%M:%S")
        registros = df.astype(object).where(df.notna(), None).to_dict("records")
        for i in range(0, len(registros), 1000):
            cliente.schema("raw").table(tabla).upsert(registros[i:i + 1000]).execute()
        print(f"raw.{tabla}: {len(registros)} filas")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sql", action="store_true", help="escribe archivos SQL en lugar de subir")
    p.add_argument("--periodos", type=int, default=3, help="periodos recientes de recibos en modo SQL")
    args = p.parse_args()

    tablas, _ = ejecutar()
    if not args.sql:
        cargar_directo(tablas)
        return

    destino = ARTEFACTOS / "sql_raw"
    destino.mkdir(parents=True, exist_ok=True)
    recientes = sorted(tablas["recibos"]["periodo"].unique())[-args.periodos:]
    recibos = tablas["recibos"][tablas["recibos"]["periodo"].isin(recientes)]
    for nombre, df in [("tomas", tablas["tomas"]), ("recibos", recibos)]:
        for j, sentencia in enumerate(a_sql(nombre, df)):
            (destino / f"{nombre}_{j:02d}.sql").write_text(sentencia, encoding="utf-8")
    print(f"SQL en {destino} (recibos de {recientes[0]} a {recientes[-1]})")


if __name__ == "__main__":
    main()
