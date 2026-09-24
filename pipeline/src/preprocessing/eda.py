"""T-05 — EDA (bloque B) y estadística inferencial (bloque C).

Todo número que aparece en una conclusión se calcula aquí (regla 5: métricas
solo desde código). Las interpretaciones de negocio van al reporte marcadas
"VALIDAR: Emilio".

Hipótesis (definidas antes de mirar los resultados):
- H1: el consumo mensual de las tomas domésticas difiere entre privadas
      (Kruskal-Wallis; el consumo no es normal).
- H2: pagar tarde no es independiente de tener el pago domiciliado (chi²).
Además: IC 95 % (Wilson) de la tasa de pago tardío por segmento y
correlación de Spearman entre variables por toma.

Uso:
    from pipeline.src.preprocessing.eda import ejecutar
    eda, estadistica = ejecutar()          # listas de {"clave", "payload"}
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from pipeline.src.data.limpieza import ejecutar as limpiar

FUENTE = "pipeline/src/preprocessing/eda.py · pipeline/notebooks/02_eda_estadistica.ipynb"
ALFA = 0.05


# ------------------------------------------------------------------ utilidades
def _pl(n: float, dec: int = 1) -> str:
    return f"{n:,.{dec}f}"


def caja(valores: pd.Series, nombre: str, max_atipicos: int = 50) -> dict:
    """Cuartiles precalculados (convención acordada en #38/#40)."""
    v = valores.dropna().to_numpy(dtype=float)
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    dentro = v[(v >= lo) & (v <= hi)]
    atip = np.sort(v[(v < lo) | (v > hi)])
    if len(atip) > max_atipicos:  # muestra representativa y reproducible
        atip = atip[np.linspace(0, len(atip) - 1, max_atipicos).astype(int)]
    return {"nombre": nombre, "n": int(len(v)), "min": float(dentro.min()), "q1": float(q1),
            "mediana": float(med), "q3": float(q3), "max": float(dentro.max()),
            "atipicos": [float(a) for a in atip]}


def wilson(exitos: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = exitos / n
    den = 1 + z ** 2 / n
    centro = (p + z ** 2 / (2 * n)) / den
    margen = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return centro - margen, centro + margen


# ------------------------------------------------------------------ EDA
def eda(t: dict[str, pd.DataFrame]) -> list[dict]:
    ds, quejas, tel = t["dataset"], t["quejas"], t["telemetria"]
    etiq = ds[ds["en_entrenamiento"]]
    out = []

    # 1. Resumen de los datos
    filas = [
        {"tabla": "tomas", "filas": len(t["tomas"]), "descripcion": "tomas de la simulación (sin parámetros del generador)"},
        {"tabla": "recibos", "filas": len(t["recibos"]), "descripcion": f"periodos {ds['periodo'].min()} a {ds['periodo'].max()}"},
        {"tabla": "lecturas", "filas": len(t["lecturas"]), "descripcion": "sin duplicados; nulas y retrocesos marcados"},
        {"tabla": "telemetria", "filas": len(tel), "descripcion": f"lecturas horarias de {tel['id_toma'].nunique()} tomas"},
        {"tabla": "quejas", "filas": len(quejas), "descripcion": f"{quejas['descripcion'].nunique()} textos únicos"},
    ]
    out.append({"clave": "resumen_datos", "payload": {
        "tipo": "tabla", "titulo": "Datos analizados (simulación declarada)", "filas": filas,
        "conclusion": f"{len(t['tomas'])} tomas y {len(ds):,} recibos mensuales; "
                      f"{len(etiq):,} recibos tienen etiqueta de pago a la fecha de corte.",
        "fuente": FUENTE}})

    # 2. Consumo por tipo de tarifa (caja)
    orden = ["domestico", "comercial", "publico", "industrial"]
    series = [caja(ds.loc[ds["tipo_tarifa"] == k, "consumo_m3"], k) for k in orden]
    med = {s["nombre"]: s["mediana"] for s in series}
    out.append({"clave": "consumo_por_tarifa", "payload": {
        "tipo": "caja", "titulo": "Consumo mensual por tipo de tarifa",
        "y": {"etiqueta": "Consumo (m³/mes)"}, "series": series,
        "conclusion": f"Mediana doméstica {_pl(med['domestico'])} m³ contra {_pl(med['industrial'])} m³ "
                      f"industrial: los segmentos se analizan por separado porque sus escalas no son comparables.",
        "fuente": FUENTE}})

    # 3. Consumo mensual promedio por tarifa (línea)
    mensual = ds.pivot_table(index="periodo", columns="tipo_tarifa", values="consumo_m3", aggfunc="mean").sort_index()
    dom = mensual["domestico"]
    out.append({"clave": "consumo_mensual", "payload": {
        "tipo": "linea", "titulo": "Consumo promedio por toma y mes",
        "x": {"etiqueta": "Periodo", "valores": list(mensual.index)},
        "y": {"etiqueta": "Consumo promedio (m³/toma)"},
        "series": [{"nombre": k, "valores": [float(v) for v in mensual[k]]} for k in orden],
        "conclusion": f"El consumo doméstico promedio va de {_pl(dom.min())} a {_pl(dom.max())} m³ por toma "
                      f"(máximo en {dom.idxmax()}, mínimo en {dom.idxmin()}); la estacionalidad se analiza en T-06.",
        "fuente": FUENTE}})

    # 4. Distribución del importe doméstico (histograma)
    imp = ds.loc[ds["tipo_tarifa"] == "domestico", "total_pagar"]
    conteos, bordes = np.histogram(imp, bins=20)
    out.append({"clave": "importe_domestico", "payload": {
        "tipo": "histograma", "titulo": "Distribución del importe mensual doméstico (tarifario CEA)",
        "x": {"etiqueta": "Total a pagar (MXN)", "valores": [f"{bordes[i]:.0f}–{bordes[i+1]:.0f}" for i in range(len(conteos))]},
        "y": {"etiqueta": "Recibos"}, "series": [{"nombre": "recibos", "valores": conteos.tolist()}],
        "conclusion": f"Mediana {_pl(imp.median(), 0)} MXN; el 90 % de los recibos domésticos está por debajo de "
                      f"{_pl(imp.quantile(.9), 0)} MXN (asimetría a la derecha por la tarifa escalonada).",
        "fuente": FUENTE}})

    # 5. Tasa de pago tardío por segmento (barras)
    segs = []
    for col in ["tipo_tarifa", "domiciliado", "privada"]:
        g = etiq.groupby(col)["pago_tardio"].agg(["mean", "size"]).reset_index()
        for _, r in g.iterrows():
            segs.append({"variable": col, "valor": str(r[col]), "tasa": float(r["mean"]), "n": int(r["size"])})
    seg = pd.DataFrame(segs)
    top = seg[seg["variable"] == "privada"].sort_values("tasa", ascending=False).iloc[0]
    dom_t = seg[(seg["variable"] == "domiciliado")].set_index("valor")["tasa"]
    out.append({"clave": "tardio_por_segmento", "payload": {
        "tipo": "barras", "titulo": "Tasa de pago tardío por segmento",
        "x": {"etiqueta": "Segmento", "valores": [f"{r.variable}={r.valor}" for r in seg.itertuples()]},
        "y": {"etiqueta": "Proporción de recibos pagados tarde"},
        "series": [{"nombre": "tasa", "valores": seg["tasa"].round(4).tolist()}],
        "filas": segs,
        "conclusion": f"Domiciliados {dom_t.get('True', np.nan):.1%} contra no domiciliados {dom_t.get('False', np.nan):.1%}; "
                      f"la privada con más atraso es {top['valor']} ({top['tasa']:.1%}, n={top['n']}). Se prueba en H2.",
        "fuente": FUENTE}})

    # 6. Cartera: facturado y monto pagado tarde o no pagado por periodo
    c = etiq.assign(tarde_monto=etiq["total_pagar"].where(etiq["pago_tardio"].astype(bool), 0.0))
    cart = c.groupby("periodo").agg(facturado=("total_pagar", "sum"), tarde=("tarde_monto", "sum")).sort_index()
    pct = cart["tarde"].sum() / cart["facturado"].sum()
    out.append({"clave": "cartera_mensual", "payload": {
        "tipo": "linea", "titulo": "Facturado y monto pagado tarde (o no pagado) por periodo",
        "x": {"etiqueta": "Periodo", "valores": list(cart.index)}, "y": {"etiqueta": "MXN"},
        "series": [{"nombre": "facturado", "valores": cart["facturado"].round(2).tolist()},
                   {"nombre": "pagado tarde o no pagado", "valores": cart["tarde"].round(2).tolist()}],
        "conclusion": f"El {pct:.1%} de lo facturado en recibos etiquetados se pagó tarde o no se pagó a la fecha de corte.",
        "fuente": FUENTE}})

    # 7. Quejas por categoría y canal
    cat = quejas["categoria"].value_counts()
    canal = quejas["canal"].value_counts()
    out.append({"clave": "quejas_por_categoria", "payload": {
        "tipo": "barras", "titulo": "Quejas por categoría",
        "x": {"etiqueta": "Categoría", "valores": list(cat.index)}, "y": {"etiqueta": "Quejas"},
        "series": [{"nombre": "quejas", "valores": cat.tolist()}],
        "filas": [{"canal": k, "quejas": int(v)} for k, v in canal.items()],
        "conclusion": f"Las tres categorías principales ({', '.join(cat.index[:3])}) suman {cat.iloc[:3].sum() / cat.sum():.0%} "
                      f"de las quejas; el canal más usado es {canal.index[0]} ({canal.iloc[0] / canal.sum():.0%}).",
        "fuente": FUENTE}})

    # 8. Calidad de lecturas
    lec = t["lecturas"]
    out.append({"clave": "calidad_lecturas", "payload": {
        "tipo": "metrica", "titulo": "Calidad de las lecturas de medidor",
        "filas": [{"indicador": "lecturas nulas", "valor": int(lec["lectura_nula"].sum())},
                  {"indicador": "retrocesos de medidor", "valor": int(lec["retroceso_medidor"].sum())},
                  {"indicador": "medidores mudos", "valor": int(lec["medidor_mudo"].sum())},
                  {"indicador": "% inconsistentes", "valor": round(float(lec["lectura_inconsistente"].mean() * 100), 2)}],
        "conclusion": f"{lec['lectura_inconsistente'].mean():.1%} de las lecturas son inconsistentes; se marcan y no se imputan.",
        "fuente": FUENTE}})
    return out


# ------------------------------------------------------------------ estadística
def estadistica(t: dict[str, pd.DataFrame]) -> list[dict]:
    ds = t["dataset"]
    etiq = ds[ds["en_entrenamiento"]]
    out = []

    # H1 Kruskal-Wallis: consumo doméstico por privada (promedio por toma, para no inflar n)
    dom = ds[ds["tipo_tarifa"] == "domestico"].groupby(["id_toma", "privada"])["consumo_m3"].mean().reset_index()
    grupos = {k: g["consumo_m3"].to_numpy() for k, g in dom.groupby("privada") if len(g) >= 5}
    h, p_h1 = stats.kruskal(*grupos.values())
    n = sum(len(v) for v in grupos.values())
    eps2 = (h - len(grupos) + 1) / (n - len(grupos))  # tamaño de efecto epsilon²
    # H2 chi²: pago tardío vs domiciliado
    tabla = pd.crosstab(etiq["domiciliado"], etiq["pago_tardio"].astype(bool))
    chi2, p_h2, gl, _ = stats.chi2_contingency(tabla)
    v_cramer = np.sqrt(chi2 / (tabla.to_numpy().sum() * (min(tabla.shape) - 1)))

    filas = [
        {"hipotesis": "H1: el consumo doméstico difiere entre privadas", "prueba": "Kruskal-Wallis (promedio por toma)",
         "estadistico": round(float(h), 3), "gl": len(grupos) - 1, "p_valor": float(p_h1),
         "efecto": f"ε² = {eps2:.3f}", "decision": "se rechaza H0" if p_h1 < ALFA else "no se rechaza H0"},
        {"hipotesis": "H2: pagar tarde depende de estar domiciliado", "prueba": "chi² de independencia",
         "estadistico": round(float(chi2), 3), "gl": int(gl), "p_valor": float(p_h2),
         "efecto": f"V de Cramér = {v_cramer:.3f}", "decision": "se rechaza H0" if p_h2 < ALFA else "no se rechaza H0"},
    ]
    out.append({"clave": "pruebas_hipotesis", "payload": {
        "tipo": "tabla", "titulo": "Pruebas de hipótesis (α = 0.05)", "filas": filas,
        "conclusion": f"H1: p = {p_h1:.3g} ({filas[0]['decision']}, ε² = {eps2:.3f}). "
                      f"H2: p = {p_h2:.3g} ({filas[1]['decision']}, V = {v_cramer:.3f}). "
                      "Significancia no implica causalidad; el tamaño de efecto dice cuánto importa.",
        "fuente": FUENTE}})

    # IC 95 % de la tasa de pago tardío por tipo de tarifa y domiciliado (Wilson)
    ic = []
    for col in ["tipo_tarifa", "domiciliado"]:
        for k, g in etiq.groupby(col):
            x, m = int(g["pago_tardio"].astype(bool).sum()), len(g)
            lo, hi = wilson(x, m)
            ic.append({"segmento": f"{col}={k}", "n": m, "tasa": round(x / m, 4),
                       "ic95_inf": round(lo, 4), "ic95_sup": round(hi, 4)})
    ancho = max(r["ic95_sup"] - r["ic95_inf"] for r in ic)
    out.append({"clave": "ic95_tardio", "payload": {
        "tipo": "tabla", "titulo": "Tasa de pago tardío con IC 95 % (Wilson)", "filas": ic,
        "conclusion": f"El intervalo más ancho mide {ancho:.1%}: los segmentos pequeños (público, industrial) "
                      "se interpretan con cautela.",
        "fuente": FUENTE}})

    # Correlación de Spearman entre variables por toma
    por_toma = (etiq.groupby("id_toma").agg(consumo_medio=("consumo_m3", "mean"),
                                            importe_medio=("total_pagar", "mean"),
                                            antiguedad_meses=("antiguedad_meses", "max"),
                                            pct_lecturas_inconsistentes=("lectura_inconsistente", "mean"),
                                            tasa_tardio=("pago_tardio", "mean")))
    rho = por_toma.corr(method="spearman")
    pares = []
    cols = list(rho.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r, p = stats.spearmanr(por_toma[a], por_toma[b])
            pares.append({"variable_a": a, "variable_b": b, "rho": round(float(r), 3), "p_valor": float(p)})
    con_tardio = sorted([x for x in pares if "tasa_tardio" in (x["variable_a"], x["variable_b"])],
                        key=lambda x: -abs(x["rho"]))[0]
    otra = con_tardio["variable_a"] if con_tardio["variable_b"] == "tasa_tardio" else con_tardio["variable_b"]
    out.append({"clave": "correlacion_spearman", "payload": {
        "tipo": "tabla", "titulo": f"Correlación de Spearman por toma (n = {len(por_toma)})", "filas": pares,
        "conclusion": f"La variable más asociada a la tasa de pago tardío es {otra} (ρ = {con_tardio['rho']:.2f}, "
                      f"p = {con_tardio['p_valor']:.2g}); consumo e importe correlacionan casi 1 por construcción de la tarifa.",
        "fuente": FUENTE}})
    return out


def ejecutar() -> tuple[list[dict], list[dict]]:
    tablas, _ = limpiar()
    return eda(tablas), estadistica(tablas)


if __name__ == "__main__":
    import json
    a, b = ejecutar()
    for r in a + b:
        print(r["clave"], "→", r["payload"]["conclusion"])
    print(json.dumps(b[0]["payload"]["filas"], ensure_ascii=False, indent=1))
