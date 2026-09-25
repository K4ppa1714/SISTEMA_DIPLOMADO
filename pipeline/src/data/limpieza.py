"""T-04 — Pipeline de datos sobre la simulación declarada (bloque A).

Qué hace, en orden (cada paso deja una fila en el informe de calidad):
1. Carga los cinco CSV crudos de data/simulados/ con tipos explícitos.
2. Lecturas: quita duplicados por (toma, periodo), marca retrocesos de
   medidor y lecturas nulas. No inventa valores: los marca.
3. Recibos: recalcula importe_agua, alcantarillado, saneamiento, IVA y total
   con el tarifario CEA real (api/_lib/tarifas.py, T-03), como pidió Andrés
   (#32, punto 5). La simulación original usaba una tarifa inventada.
4. Objetivo `pago_tardio` con censura (propuesta #5, aprobada por Andrés):
   - vencido a FECHA_CORTE y sin pagar  -> tardío (True)
   - vencimiento posterior a FECHA_CORTE -> sin etiqueta y fuera del
     entrenamiento (`en_entrenamiento = False`).
5. Une recibos + lecturas + tomas en una tabla por (toma, periodo) y quita
   los parámetros ocultos del generador (consumo_base, propension_mora).

Uso:
    from pipeline.src.data.limpieza import ejecutar
    tablas, informe = ejecutar()
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.src.config import DATOS_SIMULADOS, FECHA_CORTE, RAIZ

sys.path.insert(0, str(RAIZ / "api" / "_lib"))
import tarifas  # noqa: E402  (función pura de T-03, sin dependencias)

# Mapeo tipo de tarifa de la simulación -> tipo del tarifario CEA (#32, punto 5).
MAPEO_TARIFA_CEA = {
    "domestico": "domestico_medio",
    "comercial": "comercial",
    "publico": "publico_oficial",
    "industrial": "industrial",
}

# Parámetros ocultos del generador: nunca salen de este módulo.
PARAMETROS_GENERADOR = ["consumo_base", "propension_mora"]


def periodo_tarifario(periodo: str) -> str:
    """Trimestre del tarifario CEA que se aplica a un periodo AAAA-MM.

    Solo tenemos el tarifario 2026-T2 y 2026-T3. Supuesto declarado:
    periodos hasta 2026-06 usan 2026-T2 (el más antiguo disponible) y
    periodos desde 2026-07 usan 2026-T3.
    """
    return "2026-T3" if periodo >= "2026-07" else "2026-T2"


@dataclass
class InformeCalidad:
    pasos: list[dict] = field(default_factory=list)

    def agregar(self, paso: str, resultado: str) -> None:
        self.pasos.append({"Paso": paso, "Resultado": resultado})

    def como_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.pasos)


# ---------------------------------------------------------------- carga
def cargar_crudos(carpeta: Path = DATOS_SIMULADOS) -> dict[str, pd.DataFrame]:
    fechas = {
        "tomas": ["fecha_alta"],
        "lecturas": ["fecha_lectura"],
        "recibos": ["fecha_emision", "fecha_vencimiento", "fecha_pago"],
        "telemetria": ["marca_tiempo"],
        "quejas": ["fecha_reporte"],
    }
    return {
        nombre: pd.read_csv(carpeta / f"{nombre}.csv", parse_dates=cols)
        for nombre, cols in fechas.items()
    }


# ---------------------------------------------------------------- lecturas
def limpiar_lecturas(lecturas: pd.DataFrame, informe: InformeCalidad) -> pd.DataFrame:
    df = lecturas.copy()
    n0 = len(df)
    df = df.sort_values("fecha_lectura").drop_duplicates(["id_toma", "periodo"], keep="last")
    informe.agregar("Lecturas: duplicados por (toma, periodo)",
                    f"{n0 - len(df)} filas eliminadas (se conserva la lectura más reciente)")

    df["lectura_nula"] = df["lectura_final"].isna()
    df["retroceso_medidor"] = df["lectura_final"] < df["lectura_inicial"]
    df["lectura_inconsistente"] = df["lectura_nula"] | df["retroceso_medidor"]
    informe.agregar("Lecturas: nulas", f"{int(df['lectura_nula'].sum())} marcadas (no se imputan)")
    informe.agregar("Lecturas: retrocesos de medidor",
                    f"{int(df['retroceso_medidor'].sum())} marcados como inconsistentes")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- recibos
def recalcular_importes(recibos: pd.DataFrame, tomas: pd.DataFrame,
                        informe: InformeCalidad) -> pd.DataFrame:
    df = recibos.merge(
        tomas[["id_toma", "incluye_alcantarillado", "incluye_saneamiento"]],
        on="id_toma", how="left", validate="many_to_one",
    )
    total_original = df["total_pagar"].sum()

    def _fila(r):
        d = tarifas.calcular_importe(
            MAPEO_TARIFA_CEA[r.tipo_tarifa], r.consumo_m3,
            bool(r.incluye_alcantarillado), bool(r.incluye_saneamiento),
            periodo_tarifario(r.periodo),
        )
        return (d["consumo_facturado"], d["agua"], d["alcantarillado"],
                d["saneamiento"], d["iva"], d["total"])

    calc = pd.DataFrame(
        [_fila(r) for r in df.itertuples(index=False)],
        columns=["consumo_facturado", "importe_agua", "importe_alcantarillado",
                 "importe_saneamiento", "iva", "total_pagar"],
        index=df.index,
    )
    df[calc.columns] = calc
    df = df.drop(columns=["incluye_alcantarillado", "incluye_saneamiento"])
    informe.agregar(
        "Recibos: importes con tarifario CEA real",
        f"{len(df)} recibos recalculados; total facturado {total_original:,.0f} -> "
        f"{df['total_pagar'].sum():,.0f} MXN (mapeo {MAPEO_TARIFA_CEA})",
    )
    return df


def aplicar_censura(recibos: pd.DataFrame, informe: InformeCalidad,
                    fecha_corte: str = FECHA_CORTE) -> pd.DataFrame:
    df = recibos.copy()
    corte = pd.Timestamp(fecha_corte)
    etiqueta = df["pago_tardio"].map({True: True, False: False, "True": True, "False": False})

    vencido_sin_pago = etiqueta.isna() & (df["fecha_vencimiento"] <= corte) & ~df["pagado"]
    etiqueta = etiqueta.mask(vencido_sin_pago, True)
    pagado_sin_fecha = df["pagado"] & df["fecha_pago"].isna()

    df["en_entrenamiento"] = df["fecha_vencimiento"] <= corte
    etiqueta = etiqueta.where(df["en_entrenamiento"])  # sin etiqueta después del corte
    df["pago_tardio"] = etiqueta.astype("boolean")

    informe.agregar("Recibos: pagados sin fecha de pago",
                    f"{int(pagado_sin_fecha.sum())} recibos; se conserva la etiqueta original "
                    "(la fecha no se imputa)")
    informe.agregar("Recibos: vencidos y sin pagar a la fecha de corte",
                    f"{int(vencido_sin_pago.sum())} etiquetados como pago tardío")
    informe.agregar("Recibos: censura por fecha de corte",
                    f"{int((~df['en_entrenamiento']).sum())} recibos con vencimiento posterior a "
                    f"{fecha_corte} quedan fuera del entrenamiento")
    tasa = df.loc[df["en_entrenamiento"], "pago_tardio"].mean()
    informe.agregar("Objetivo pago_tardio", f"tasa {tasa:.1%} en {int(df['en_entrenamiento'].sum())} recibos etiquetados")
    return df


# ---------------------------------------------------------------- tabla de análisis
def construir_dataset(recibos: pd.DataFrame, lecturas: pd.DataFrame,
                      tomas: pd.DataFrame, informe: InformeCalidad) -> pd.DataFrame:
    tomas_pub = tomas.drop(columns=PARAMETROS_GENERADOR)
    lect = lecturas[["id_toma", "periodo", "fecha_lectura", "lectura_inicial",
                     "lectura_final", "medidor_mudo", "lectura_inconsistente", "tiene_fuga"]]
    df = (recibos
          .merge(lect, on=["id_toma", "periodo"], how="left", validate="one_to_one")
          .merge(tomas_pub.drop(columns=["tipo_tarifa", "domiciliado"]),
                 on="id_toma", how="left", validate="many_to_one"))
    df["periodo_fecha"] = pd.to_datetime(df["periodo"] + "-01")
    df["anio"] = df["periodo_fecha"].dt.year
    df["mes"] = df["periodo_fecha"].dt.month
    df["antiguedad_meses"] = ((df["periodo_fecha"] - df["fecha_alta"]).dt.days / 30.44).round(1)
    df["dias_atraso"] = (df["fecha_pago"] - df["fecha_vencimiento"]).dt.days.clip(lower=0)
    df = df.sort_values(["id_toma", "periodo"]).reset_index(drop=True)

    faltan = df["fecha_lectura"].isna().sum()
    informe.agregar("Tabla de análisis",
                    f"{len(df)} filas x {df.shape[1]} columnas; {faltan} recibos sin lectura; "
                    f"sin {', '.join(PARAMETROS_GENERADOR)}")
    return df


# ---------------------------------------------------------------- orquestación
def ejecutar(carpeta: Path = DATOS_SIMULADOS) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    informe = InformeCalidad()
    crudos = cargar_crudos(carpeta)
    for nombre, df in crudos.items():
        informe.agregar(f"Carga de {nombre}", f"{len(df):,} filas x {df.shape[1]} columnas, "
                                                f"{int(df.isna().sum().sum())} celdas nulas")

    lecturas = limpiar_lecturas(crudos["lecturas"], informe)
    recibos = recalcular_importes(crudos["recibos"], crudos["tomas"], informe)
    recibos = aplicar_censura(recibos, informe)
    dataset = construir_dataset(recibos, lecturas, crudos["tomas"], informe)

    quejas = crudos["quejas"].copy()
    unicos = quejas["descripcion"].nunique()
    informe.agregar("Quejas", f"{len(quejas)} quejas, {unicos} textos únicos: la división "
                              "entrenamiento/prueba debe hacerse por texto único")

    tablas = {
        "tomas": crudos["tomas"].drop(columns=PARAMETROS_GENERADOR),
        "lecturas": lecturas,
        "recibos": recibos,
        "telemetria": crudos["telemetria"],
        "quejas": quejas,
        "dataset": dataset,
    }
    return tablas, informe.como_dataframe()


if __name__ == "__main__":
    tablas, informe = ejecutar()
    pd.set_option("display.max_colwidth", 120)
    print(informe.to_string(index=False))


def payload_informe(informe: pd.DataFrame) -> list[dict]:
    """Resultado `pipeline/informe_calidad` (CONTRATOS §2.4) a partir del informe de este módulo."""
    filas = [{"Paso": f.Paso, "Resultado": f.Resultado} for f in informe.itertuples()]
    buscar = lambda texto: next((f["Resultado"] for f in filas if texto in f["Paso"]), "")
    return [{"clave": "informe_calidad", "payload": {
        "tipo": "tabla", "titulo": "Pipeline de datos: qué hizo cada paso de limpieza",
        "filas": filas,
        "conclusion": (f"Lecturas duplicadas: {buscar('duplicados')}; retrocesos: {buscar('retrocesos')}; "
                       f"censura: {buscar('censura')}. Objetivo: {buscar('Objetivo')}."),
        "fuente": "pipeline/src/data/limpieza.py · pipeline/notebooks/01_pipeline_datos.ipynb"}}]
