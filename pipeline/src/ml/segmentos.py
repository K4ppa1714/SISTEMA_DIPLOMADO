"""T-08 (parte 1) — Segmentación de tomas: K-means + PCA (bloque G).

Por qué: la cobranza y la atención pueden priorizar grupos de tomas con
comportamiento parecido. Unidad: la toma. Variables por toma (solo historia
etiquetada, sin columnas prohibidas): consumo medio y variabilidad, estacionalidad
(consumo abril–junio contra el resto), tasa de pago tardío, domiciliación,
proporción de lecturas inconsistentes y antigüedad.
Cómo: estandarización, K de 2 a 8 elegido por silhouette (semilla 42), PCA de
2 componentes para visualizar y describir los grupos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from pipeline.src.config import SEMILLA
from pipeline.src.data.limpieza import ejecutar as limpiar

FUENTE = "pipeline/src/ml/segmentos.py · pipeline/notebooks/06_segmentos_dl.ipynb"
VARIABLES = ["consumo_medio", "consumo_cv", "estacionalidad", "tasa_tardio", "domiciliado",
             "pct_lecturas_inconsistentes", "antiguedad_meses"]
VERSION = "v1"


def por_toma(ds: pd.DataFrame) -> pd.DataFrame:
    etiq = ds[ds["en_entrenamiento"]]
    g = etiq.groupby("id_toma")
    t = pd.DataFrame({
        "consumo_medio": g["consumo_m3"].mean(),
        "consumo_cv": g["consumo_m3"].std() / g["consumo_m3"].mean().replace(0, np.nan),
        "estacionalidad": (etiq[etiq["mes"].isin([4, 5, 6])].groupby("id_toma")["consumo_m3"].mean()
                           / g["consumo_m3"].mean().replace(0, np.nan)),
        "tasa_tardio": g["pago_tardio"].mean().astype(float),
        "domiciliado": g["domiciliado"].mean().astype(float),
        "pct_lecturas_inconsistentes": g["lectura_inconsistente"].mean().astype(float),
        "antiguedad_meses": g["antiguedad_meses"].max(),
        "tipo_tarifa": g["tipo_tarifa"].first(),
    })
    return t.fillna(t.median(numeric_only=True))


def nombrar(centro: pd.Series, global_: pd.Series) -> str:
    rasgos = []
    if centro["tasa_tardio"] > global_["tasa_tardio"] * 1.3:
        rasgos.append("atraso alto")
    elif centro["tasa_tardio"] < global_["tasa_tardio"] * 0.7:
        rasgos.append("puntual")
    if centro["consumo_medio"] > global_["consumo_medio"] * 1.5:
        rasgos.append("consumo alto")
    elif centro["consumo_medio"] < global_["consumo_medio"] * 0.7:
        rasgos.append("consumo bajo")
    if centro["domiciliado"] > 0.5:
        rasgos.append("domiciliado")
    return ", ".join(rasgos) or "comportamiento típico"


def ejecutar() -> tuple[list[dict], pd.DataFrame]:
    tablas, _ = limpiar()
    t = por_toma(tablas["dataset"])
    X = StandardScaler().fit_transform(t[VARIABLES])

    sil = {k: silhouette_score(X, KMeans(k, n_init=10, random_state=SEMILLA).fit_predict(X)) for k in range(2, 9)}
    k = max(sil, key=sil.get)
    km = KMeans(k, n_init=10, random_state=SEMILLA).fit(X)
    t["segmento"] = km.labels_
    pca = PCA(2, random_state=SEMILLA).fit(X)
    pcs = pca.transform(X)
    t["pc1"], t["pc2"] = pcs[:, 0], pcs[:, 1]

    medias = t.groupby("segmento")[VARIABLES].mean()
    glob = t[VARIABLES].mean()
    nombres = {s: nombrar(medias.loc[s], glob) for s in medias.index}
    t["nombre_segmento"] = t["segmento"].map(nombres)
    tam = t["segmento"].value_counts().sort_index()
    cargas = pd.DataFrame(pca.components_.T, index=VARIABLES, columns=["PC1", "PC2"])
    top1 = cargas["PC1"].abs().sort_values(ascending=False).index[:2]

    out = [
        {"clave": "silhouette", "payload": {
            "tipo": "barras", "titulo": "Silhouette por número de grupos (K-means)",
            "x": {"etiqueta": "K", "valores": [str(i) for i in sil]}, "y": {"etiqueta": "Silhouette"},
            "series": [{"nombre": "silhouette", "valores": [round(float(v), 4) for v in sil.values()]}],
            "conclusion": f"El mejor K es {k} (silhouette {sil[k]:.3f}); con valores menores a 0.5 los grupos "
                          "se traslapan y deben leerse como tendencias, no como clases tajantes.",
            "fuente": FUENTE}},
        {"clave": "segmentos_perfil", "payload": {
            "tipo": "tabla", "titulo": f"Perfil de los {k} segmentos de tomas (medias)",
            "filas": [{"segmento": int(s), "nombre": nombres[s], "tomas": int(tam[s]),
                       **{v: round(float(medias.loc[s, v]), 3) for v in VARIABLES}} for s in medias.index],
            "conclusion": "Segmentos: " + "; ".join(f"{int(s)} = {nombres[s]} ({int(tam[s])} tomas)" for s in medias.index)
                          + ". " + (f"El grupo \"{max(nombres.values(), key=lambda n: 'atraso alto' in n)}\" es la lista natural de cobranza preventiva."
                                    if any("atraso alto" in n for n in nombres.values()) else
                                    "La separación principal es domiciliado/puntual contra el resto: la segmentación confirma H2 más que descubrir grupos nuevos."),
            "fuente": FUENTE}},
        {"clave": "pca_segmentos", "payload": {
            "tipo": "dispersion", "titulo": "Tomas en los dos primeros componentes principales, por segmento",
            "x": {"etiqueta": f"PC1 ({pca.explained_variance_ratio_[0]:.0%} de la varianza)"},
            "y": {"etiqueta": f"PC2 ({pca.explained_variance_ratio_[1]:.0%} de la varianza)"},
            "series": [{"nombre": nombres[s], "x": t.loc[t.segmento == s, "pc1"].round(3).tolist(),
                        "valores": t.loc[t.segmento == s, "pc2"].round(3).tolist()} for s in medias.index],
            "filas": [{"variable": v, "carga_pc1": round(float(cargas.loc[v, "PC1"]), 3),
                       "carga_pc2": round(float(cargas.loc[v, "PC2"]), 3)} for v in VARIABLES],
            "conclusion": f"PC1 y PC2 explican {pca.explained_variance_ratio_[:2].sum():.0%} de la varianza; "
                          f"PC1 lo dominan {top1[0]} y {top1[1]}.",
            "fuente": FUENTE}},
    ]
    seg = t.reset_index()[["id_toma", "segmento", "nombre_segmento", "pc1", "pc2"]].assign(version=VERSION)
    return out, seg


if __name__ == "__main__":
    res, seg = ejecutar()
    for r in res:
        print(r["clave"], "→", r["payload"]["conclusion"])
