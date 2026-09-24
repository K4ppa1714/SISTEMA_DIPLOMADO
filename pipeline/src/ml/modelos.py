"""T-07 — Modelos supervisados para `pago_tardio` (bloques F y H).

Diseño:
- Separación TEMPORAL: prueba = los 4 últimos periodos con etiqueta; todo lo
  anterior es entrenamiento. La validación cruzada también es temporal
  (bloques por periodo, TimeSeriesSplit de 5 cortes).
- Líneas base: clase mayoritaria y la regla "si pagó tarde el recibo anterior".
- Modelos en `Pipeline` (imputación + escalado/one-hot + clasificador):
  regresión logística, Random Forest y Gradient Boosting (HistGradientBoosting),
  más un ensamble de votación suave (bloque H).
- Métrica principal: PR-AUC (la clase positiva es ~25 %); también ROC-AUC,
  F1, precisión, recall y Brier. El umbral se elige en validación cruzada,
  nunca en prueba.
- El mejor modelo por PR-AUC en CV se reentrena con todo lo etiquetado y
  predice los recibos censurados (vencimiento posterior a FECHA_CORTE):
  eso es analitica.predicciones_pago.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score,
                             precision_score, recall_score, roc_auc_score, confusion_matrix)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from pipeline.src.config import SEMILLA
from pipeline.src.data.limpieza import ejecutar as limpiar
from pipeline.src.features.variables import BINARIAS, CATEGORICAS, JUSTIFICACION, NUMERICAS, construir

FUENTE = "pipeline/src/ml/modelos.py · pipeline/notebooks/04_modelos.ipynb"
PERIODOS_PRUEBA = 4
VERSION = "v1"


def preprocesador(escalar: bool) -> ColumnTransformer:
    num = [("imp", SimpleImputer(strategy="median", add_indicator=True))]
    if escalar:
        num.append(("esc", StandardScaler()))
    return ColumnTransformer([
        ("num", Pipeline(num), NUMERICAS + BINARIAS),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAS),
    ])


def modelos() -> dict[str, Pipeline]:
    lr = Pipeline([("prep", preprocesador(True)),
                   ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5))])
    rf = Pipeline([("prep", preprocesador(False)),
                   ("clf", RandomForestClassifier(n_estimators=300, min_samples_leaf=20, max_features="sqrt",
                                                  class_weight="balanced_subsample", n_jobs=-1,
                                                  random_state=SEMILLA))])
    gb = Pipeline([("prep", preprocesador(False)),
                   ("clf", HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
                                                          l2_regularization=1.0, class_weight="balanced",
                                                          random_state=SEMILLA))])
    ens = VotingClassifier([("lr", clone(lr)), ("rf", clone(rf)), ("gb", clone(gb))], voting="soft")
    return {"regresion_logistica": lr, "random_forest": rf, "gradient_boosting": gb, "ensamble_votacion": ens}


def cortes_temporales(periodos: pd.Series, n: int = 5):
    """TimeSeriesSplit sobre periodos únicos: nunca valida con el pasado."""
    unicos = np.array(sorted(periodos.unique()))
    for tr, va in TimeSeriesSplit(n_splits=n).split(unicos):
        yield (np.where(periodos.isin(unicos[tr]))[0], np.where(periodos.isin(unicos[va]))[0])


def metricas(y, p, umbral) -> dict:
    yh = (p >= umbral).astype(int)
    return {"pr_auc": average_precision_score(y, p), "roc_auc": roc_auc_score(y, p),
            "f1": f1_score(y, yh), "precision": precision_score(y, yh, zero_division=0),
            "recall": recall_score(y, yh), "brier": brier_score_loss(y, p)}


def mejor_umbral(y, p) -> float:
    candidatos = np.linspace(0.1, 0.9, 81)
    return float(candidatos[np.argmax([f1_score(y, (p >= u).astype(int)) for u in candidatos])])


def ejecutar() -> dict:
    tablas, _ = limpiar()
    df = construir(tablas["dataset"])
    X_cols = NUMERICAS + BINARIAS + CATEGORICAS
    etiq = df[df["en_entrenamiento"]].copy()
    etiq["y"] = etiq["pago_tardio"].astype(int)
    per = sorted(etiq["periodo"].unique())
    corte_prueba = per[-PERIODOS_PRUEBA]
    ent = etiq[etiq["periodo"] < corte_prueba].sort_values("periodo").reset_index(drop=True)
    pru = etiq[etiq["periodo"] >= corte_prueba].reset_index(drop=True)

    res = {"corte_prueba": corte_prueba, "n_ent": len(ent), "n_pru": len(pru),
           "tasa_ent": ent["y"].mean(), "tasa_pru": pru["y"].mean(), "modelos": {}}

    # Líneas base
    base_may = np.full(len(pru), ent["y"].mean())
    res["modelos"]["base_mayoritaria"] = {"cv_pr_auc": ent["y"].mean(), "umbral": 0.5,
                                          "prueba": metricas(pru["y"], base_may, 0.5)}
    regla = pru["tardio_anterior"].fillna(ent["y"].mean()).to_numpy()
    res["modelos"]["base_regla_recibo_anterior"] = {"cv_pr_auc": np.nan, "umbral": 0.5,
                                                    "prueba": metricas(pru["y"], regla, 0.5)}

    # Modelos con CV temporal
    for nombre, modelo in modelos().items():
        oof_p, oof_y = [], []
        for tr, va in cortes_temporales(ent["periodo"]):
            m = clone(modelo).fit(ent.loc[tr, X_cols], ent.loc[tr, "y"])
            oof_p.append(m.predict_proba(ent.loc[va, X_cols])[:, 1])
            oof_y.append(ent.loc[va, "y"].to_numpy())
        oof_p, oof_y = np.concatenate(oof_p), np.concatenate(oof_y)
        umbral = mejor_umbral(oof_y, oof_p)
        final = clone(modelo).fit(ent[X_cols], ent["y"])
        p = final.predict_proba(pru[X_cols])[:, 1]
        res["modelos"][nombre] = {"cv_pr_auc": average_precision_score(oof_y, oof_p), "umbral": umbral,
                                  "prueba": metricas(pru["y"], p, umbral), "_modelo": final, "_p": p}

    candidatos = {k: v for k, v in res["modelos"].items() if "_modelo" in v}
    elegido = max(candidatos, key=lambda k: candidatos[k]["cv_pr_auc"])  # elegido en CV, no en prueba
    res["elegido"] = elegido
    info = candidatos[elegido]
    yh = (info["_p"] >= info["umbral"]).astype(int)
    res["matriz_confusion"] = confusion_matrix(pru["y"], yh).tolist()

    imp = permutation_importance(info["_modelo"], pru[X_cols], pru["y"], scoring="average_precision",
                                 n_repeats=5, random_state=SEMILLA, n_jobs=-1)
    res["importancias"] = (pd.Series(imp.importances_mean, index=X_cols).sort_values(ascending=False))

    # Error por segmento (insumo de T-09)
    pru["p"], pru["yh"] = info["_p"], yh
    res["errores_segmento"] = (pru.groupby("tipo_tarifa")
                               .apply(lambda g: pd.Series({"n": len(g), "tasa_real": g["y"].mean(),
                                                           "recall": recall_score(g["y"], g["yh"], zero_division=0),
                                                           "precision": precision_score(g["y"], g["yh"], zero_division=0)}),
                                      include_groups=False).reset_index())

    # Reentrenar con todo lo etiquetado y predecir los recibos censurados
    final = clone(modelos()[elegido]).fit(etiq[X_cols], etiq["y"])
    fut = df[~df["en_entrenamiento"]].copy()
    fut["prob_pago_tardio"] = final.predict_proba(fut[X_cols])[:, 1]
    fut["clase_predicha"] = fut["prob_pago_tardio"] >= info["umbral"]
    res["predicciones"] = fut[["id_toma", "periodo", "prob_pago_tardio", "clase_predicha"]].assign(
        modelo=elegido, version=VERSION).reset_index(drop=True)
    return res


def payloads(res: dict) -> list[dict]:
    filas = []
    for k, v in res["modelos"].items():
        filas.append({"modelo": k, "cv_pr_auc": round(float(v["cv_pr_auc"]), 4) if v["cv_pr_auc"] == v["cv_pr_auc"] else None,
                      "umbral": v["umbral"], **{m: round(float(x), 4) for m, x in v["prueba"].items()}})
    el = res["modelos"][res["elegido"]]["prueba"]
    base = res["modelos"]["base_regla_recibo_anterior"]["prueba"]
    imp = res["importancias"]
    tn, fp, fn, tp = np.array(res["matriz_confusion"]).ravel()
    pred = res["predicciones"]
    return [
        {"clave": "comparacion_modelos", "payload": {
            "tipo": "tabla", "titulo": f"Modelos de pago tardío — prueba temporal ({res['corte_prueba']} en adelante, n={res['n_pru']})",
            "filas": filas,
            "conclusion": f"Elegido por PR-AUC en validación cruzada temporal: {res['elegido']} "
                          f"(PR-AUC prueba {el['pr_auc']:.3f}, ROC-AUC {el['roc_auc']:.3f}, F1 {el['f1']:.3f}) contra la "
                          f"regla del recibo anterior (PR-AUC {base['pr_auc']:.3f}, F1 {base['f1']:.3f}). "
                          f"Tasa real de atraso en prueba: {res['tasa_pru']:.1%}.",
            "fuente": FUENTE}},
        {"clave": "comparacion_pr_auc", "payload": {
            "tipo": "barras", "titulo": "PR-AUC en prueba por modelo",
            "x": {"etiqueta": "Modelo", "valores": [f["modelo"] for f in filas]},
            "y": {"etiqueta": "PR-AUC (prueba temporal)"},
            "series": [{"nombre": "PR-AUC", "valores": [f["pr_auc"] for f in filas]}],
            "conclusion": "La línea base mayoritaria marca el piso (PR-AUC = tasa de positivos); "
                          "cualquier modelo útil debe superarla con claridad.",
            "fuente": FUENTE}},
        {"clave": "matriz_confusion", "payload": {
            "tipo": "tabla", "titulo": f"Matriz de confusión — {res['elegido']}",
            "filas": [{"real": "a tiempo", "pred_a_tiempo": int(tn), "pred_tarde": int(fp)},
                      {"real": "tarde", "pred_a_tiempo": int(fn), "pred_tarde": int(tp)}],
            "conclusion": f"Detecta {tp} de {tp + fn} recibos tardíos ({tp / (tp + fn):.0%}) con {fp} falsas alarmas; "
                          "el umbral se fijó en validación cruzada para maximizar F1.",
            "fuente": FUENTE}},
        {"clave": "importancia_variables", "payload": {
            "tipo": "barras", "titulo": f"Importancia por permutación (PR-AUC) — {res['elegido']}",
            "x": {"etiqueta": "Variable", "valores": list(imp.index[:10])},
            "y": {"etiqueta": "Caída de PR-AUC al permutar"},
            "series": [{"nombre": "importancia", "valores": [float(x) for x in imp.values[:10]]}],
            "filas": [{"variable": k, "justificacion": JUSTIFICACION[k]} for k in imp.index[:10]],
            "conclusion": f"Las variables que más aportan son {', '.join(imp.index[:3])}: el hábito de pago previo "
                          "pesa más que el monto. Importancia no es causalidad.",
            "fuente": FUENTE}},
        {"clave": "errores_por_segmento", "payload": {
            "tipo": "tabla", "titulo": "Desempeño por tipo de tarifa (prueba)",
            "filas": [{k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for k, v in r.items()}
                      for r in res["errores_segmento"].to_dict("records")],
            "conclusion": "Los segmentos con pocos recibos (público, industrial) tienen métricas inestables; "
                          "se analizan en T-09.",
            "fuente": FUENTE}},
        {"clave": "predicciones_resumen", "payload": {
            "tipo": "metrica", "titulo": "Predicción por lotes de recibos aún no vencidos",
            "filas": [{"indicador": "recibos predichos", "valor": len(pred)},
                      {"indicador": "periodos", "valor": ", ".join(sorted(pred["periodo"].unique()))},
                      {"indicador": "marcados en riesgo", "valor": int(pred["clase_predicha"].sum())},
                      {"indicador": "probabilidad media", "valor": round(float(pred["prob_pago_tardio"].mean()), 4)}],
            "conclusion": f"{int(pred['clase_predicha'].sum())} de {len(pred)} recibos por vencer quedan marcados en riesgo "
                          "de pago tardío; la lista está en analitica.predicciones_pago.",
            "fuente": FUENTE}},
    ]


def sql_predicciones(pred: pd.DataFrame) -> str:
    """SQL compacto (arreglos + unnest) para cargar analitica.predicciones_pago sin credenciales locales."""
    ids = ",".join(f"'{x}'" for x in pred["id_toma"])
    per = ",".join(f"'{x}'" for x in pred["periodo"])
    prob = ",".join(f"{x:.4f}" for x in pred["prob_pago_tardio"])
    cls = ",".join("true" if x else "false" for x in pred["clase_predicha"])
    modelo, version = pred["modelo"].iloc[0], pred["version"].iloc[0]
    return (f"delete from analitica.predicciones_pago where version = '{version}';\n"
            "insert into analitica.predicciones_pago (id_toma, periodo, prob_pago_tardio, clase_predicha, modelo, version)\n"
            f"select unnest(array[{ids}]), unnest(array[{per}]), unnest(array[{prob}]::numeric[]), "
            f"unnest(array[{cls}]), '{modelo}', '{version}';")


if __name__ == "__main__":
    r = ejecutar()
    for k, v in r["modelos"].items():
        print(f"{k:28s} cv_pr_auc={v['cv_pr_auc']:.3f} umbral={v['umbral']:.2f} "
              + " ".join(f"{m}={x:.3f}" for m, x in v["prueba"].items()))
    print("elegido:", r["elegido"]); print(r["importancias"].head(8)); print(r["errores_segmento"])
    print(r["predicciones"].describe(include="all").T[["count", "mean"]])
