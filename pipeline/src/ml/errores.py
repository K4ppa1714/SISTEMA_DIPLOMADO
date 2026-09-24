"""T-09 — Análisis de errores e interpretación del modelo de pago tardío (bloques F e I).

Sobre el conjunto de PRUEBA temporal del modelo elegido en T-07:
1. Umbral: precisión, recall y F1 para varios umbrales (qué se gana y qué se pierde).
2. Calibración: probabilidad predicha contra tasa real por decil. El modelo usa
   class_weight="balanced", así que sus probabilidades están infladas: se reporta
   y se usan como puntaje de riesgo, no como probabilidad literal.
3. Perfil de errores: cómo son los falsos negativos (tardíos no detectados) y
   los falsos positivos frente a los aciertos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from pipeline.src.ml import modelos as m

FUENTE = "pipeline/src/ml/errores.py · pipeline/notebooks/05_errores.ipynb"


def ejecutar(res: dict | None = None) -> list[dict]:
    res = res or m.ejecutar()
    tablas, _ = m.limpiar()
    df = m.construir(tablas["dataset"])
    etiq = df[df["en_entrenamiento"]].copy()
    pru = etiq[etiq["periodo"] >= res["corte_prueba"]].reset_index(drop=True)
    y = pru["pago_tardio"].astype(int).to_numpy()
    info = res["modelos"][res["elegido"]]
    p, umbral = info["_p"], info["umbral"]
    out = []

    # 1. Curva de umbral
    umbrales = np.round(np.arange(0.2, 0.81, 0.05), 2)
    filas = []
    for u in umbrales:
        yh = (p >= u).astype(int)
        filas.append({"umbral": float(u), "precision": precision_score(y, yh, zero_division=0),
                      "recall": recall_score(y, yh), "f1": f1_score(y, yh),
                      "recibos_marcados": int(yh.sum())})
    out.append({"clave": "curva_umbral", "payload": {
        "tipo": "linea", "titulo": f"Precisión, recall y F1 según el umbral — {res['elegido']} (prueba)",
        "x": {"etiqueta": "Umbral", "valores": [f"{u:.2f}" for u in umbrales]},
        "y": {"etiqueta": "Métrica"},
        "series": [{"nombre": k, "valores": [round(f[k], 4) for f in filas]} for k in ("precision", "recall", "f1")],
        "filas": filas,
        "conclusion": f"Con el umbral elegido en CV ({umbral:.2f}) se marcan {int((p >= umbral).sum())} recibos. "
                      "Subir el umbral reduce falsas alarmas pero deja escapar más tardíos: la decisión depende "
                      "de cuántas llamadas de cobranza puede hacer Operaguas.",
        "fuente": FUENTE}})

    # 2. Calibración por decil
    dec = pd.qcut(p, 10, labels=False, duplicates="drop")
    cal = pd.DataFrame({"p": p, "y": y, "d": dec}).groupby("d").agg(pred=("p", "mean"), real=("y", "mean"), n=("y", "size"))
    sesgo = float((cal["pred"] - cal["real"]).mean())
    out.append({"clave": "calibracion", "payload": {
        "tipo": "linea", "titulo": "Calibración: probabilidad predicha contra tasa real por decil (prueba)",
        "x": {"etiqueta": "Decil de riesgo", "valores": [str(int(i) + 1) for i in cal.index]},
        "y": {"etiqueta": "Proporción"},
        "series": [{"nombre": "predicha", "valores": cal["pred"].round(4).tolist()},
                   {"nombre": "real", "valores": cal["real"].round(4).tolist()}],
        "conclusion": f"La probabilidad predicha excede a la real en {sesgo:+.2f} en promedio (efecto de "
                      "class_weight='balanced'). El ORDEN sí sirve: la tasa real crece de "
                      f"{cal['real'].iloc[0]:.0%} en el decil más bajo a {cal['real'].iloc[-1]:.0%} en el más alto; "
                      "se usa como puntaje de riesgo, no como probabilidad literal.",
        "fuente": FUENTE}})

    # 3. Perfil de errores
    yh = (p >= umbral).astype(int)
    grupo = np.select([(y == 1) & (yh == 1), (y == 1) & (yh == 0), (y == 0) & (yh == 1)],
                      ["tardío detectado", "tardío NO detectado", "falsa alarma"], "a tiempo correcto")
    pru["grupo"] = grupo
    perfil = (pru.groupby("grupo").agg(n=("id_toma", "size"),
                                       domiciliado=("domiciliado", "mean"),
                                       tasa_tardio_historica=("tasa_tardio_historica", "mean"),
                                       tardio_anterior=("tardio_anterior", "mean"),
                                       total_pagar=("total_pagar", "mean"),
                                       medidor_mudo=("medidor_mudo", "mean"))
              .round(3).reset_index())
    fn = perfil.set_index("grupo").loc["tardío NO detectado"]
    tp = perfil.set_index("grupo").loc["tardío detectado"]
    out.append({"clave": "perfil_errores", "payload": {
        "tipo": "tabla", "titulo": "Perfil de aciertos y errores (promedios en prueba)",
        "filas": perfil.to_dict("records"),
        "conclusion": f"Los tardíos no detectados tienen historial de atraso de {fn['tasa_tardio_historica']:.0%} contra "
                      f"{tp['tasa_tardio_historica']:.0%} de los detectados: el modelo falla con quien casi nunca se "
                      "atrasaba (atrasos 'nuevos'), algo que ninguna variable disponible al emitir el recibo anticipa.",
        "fuente": FUENTE}})
    return out


if __name__ == "__main__":
    for r in ejecutar():
        print(r["clave"], "→", r["payload"]["conclusion"])
