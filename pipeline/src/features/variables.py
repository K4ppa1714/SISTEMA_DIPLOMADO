"""T-07 — Variables para predecir `pago_tardio` (bloque E).

Regla: una variable solo entra si se conoce el día en que se EMITE el recibo.
Por eso nunca se usan fecha_pago, dias_atraso, pagado ni el saldo
(COLUMNAS_PROHIBIDAS), y el historial de pagos de la toma se calcula solo con
recibos anteriores cuya etiqueta ya se conocía:

- El vencimiento del recibo t-1 ocurre antes o el mismo día de la emisión del
  recibo t (se verificó: 0 a 19 días antes), así que "¿pagó tarde el recibo
  anterior?" ya se sabe al emitir t.
- Para los recibos posteriores al corte, las etiquetas censuradas quedan como
  desconocidas y se usa la última etiqueta conocida (sin mirar el futuro).

Cada variable tiene su justificación en JUSTIFICACION (va al reporte).
"""
from __future__ import annotations

import pandas as pd

from pipeline.src.config import COLUMNAS_PROHIBIDAS

CATEGORICAS = ["tipo_tarifa", "privada"]
BINARIAS = ["domiciliado", "incluye_alcantarillado", "incluye_saneamiento",
            "medidor_mudo", "lectura_inconsistente"]
NUMERICAS = ["consumo_m3", "total_pagar", "antiguedad_meses", "mes",
             "tardio_anterior", "tasa_tardio_historica", "tardios_ultimos_6",
             "recibos_con_historia", "consumo_vs_promedio_6"]

JUSTIFICACION = {
    "tipo_tarifa": "segmento de cliente; el EDA mostró tasas de atraso distintas por tarifa",
    "privada": "zona; captura diferencias socioeconómicas y operativas sin datos personales",
    "domiciliado": "H2: la asociación con el atraso es significativa (V de Cramér ≈ 0.20)",
    "incluye_alcantarillado": "cambia el importe (+10 %) y el tipo de servicio",
    "incluye_saneamiento": "cambia el importe (+12 %)",
    "medidor_mudo": "un recibo estimado puede generar inconformidad y retraso",
    "lectura_inconsistente": "misma razón: lecturas dudosas generan reclamos",
    "consumo_m3": "consumo del periodo facturado",
    "total_pagar": "monto a pagar con tarifario CEA; montos altos pueden retrasar el pago",
    "antiguedad_meses": "tiempo como cliente al emitir el recibo",
    "mes": "estacionalidad del calendario (aguinaldo, inicio de año)",
    "tardio_anterior": "comportamiento inmediato previo; se conoce al emitir (vencimiento anterior ≤ emisión)",
    "tasa_tardio_historica": "hábito de pago de la toma con recibos anteriores ya vencidos",
    "tardios_ultimos_6": "tendencia reciente del hábito de pago",
    "recibos_con_historia": "cuánta historia respalda las dos variables anteriores",
    "consumo_vs_promedio_6": "un salto de consumo (fuga, error de lectura) puede generar un recibo inesperado",
}


def construir(dataset: pd.DataFrame) -> pd.DataFrame:
    df = dataset.sort_values(["id_toma", "periodo"]).copy()
    g = df.groupby("id_toma", group_keys=False)

    etiqueta_conocida = df["pago_tardio"].astype("float")  # NaN para censurados
    previa = g["pago_tardio"].shift(1).astype("float")
    df["tardio_anterior"] = previa.groupby(df["id_toma"]).ffill()
    hist = etiqueta_conocida.groupby(df["id_toma"]).shift(1)
    df["tasa_tardio_historica"] = hist.groupby(df["id_toma"]).transform(lambda s: s.expanding().mean())
    df["tardios_ultimos_6"] = hist.groupby(df["id_toma"]).transform(lambda s: s.rolling(6, min_periods=1).sum())
    df["recibos_con_historia"] = hist.notna().groupby(df["id_toma"]).cumsum()
    prom6 = g["consumo_m3"].transform(lambda s: s.shift(1).rolling(6, min_periods=1).mean())
    df["consumo_vs_promedio_6"] = df["consumo_m3"] / prom6.where(prom6 > 0)

    for c in BINARIAS:
        df[c] = df[c].astype(float)
    usadas = set(CATEGORICAS + BINARIAS + NUMERICAS)
    assert not usadas & COLUMNAS_PROHIBIDAS, "una columna prohibida entró como variable"
    assert set(JUSTIFICACION) == usadas, "toda variable necesita justificación"
    return df
