"""Dibuja cualquier payload de CONTRATOS §2.4 con matplotlib (versión notebook del componente único de la app).

Cada gráfica lleva título, ejes con unidades y la conclusión escrita debajo.
"""
from __future__ import annotations

import textwrap

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display


def tabla(payload: dict) -> pd.DataFrame:
    return pd.DataFrame(payload.get("filas", []))


def _conclusion(fig, payload):
    texto = "\n".join(textwrap.wrap(payload["conclusion"], 120))
    fig.text(0.01, -0.02, texto, ha="left", va="top", fontsize=9, style="italic")


def dibujar(payload: dict) -> None:
    tipo = payload["tipo"]
    if tipo in ("tabla", "metrica", "texto"):
        display(Markdown(f"**{payload['titulo']}**"))
        if payload.get("filas"):
            display(tabla(payload))
        display(Markdown(f"_{payload['conclusion']}_  \n`fuente: {payload['fuente']}`"))
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    x = payload.get("x", {}).get("valores")
    if tipo == "linea":
        for s in payload["series"]:
            ax.plot(range(len(s["valores"])), s["valores"], label=s["nombre"])
    elif tipo in ("barras", "histograma"):
        series = payload["series"]
        ancho = 0.8 / len(series)
        for i, s in enumerate(series):
            ax.bar([j + i * ancho for j in range(len(s["valores"]))], s["valores"], width=ancho, label=s["nombre"])
    elif tipo == "dispersion":
        for s in payload["series"]:
            ax.scatter(s.get("x", range(len(s["valores"]))), s["valores"], s=8, label=s["nombre"])
    elif tipo == "caja":
        stats = [{"label": s["nombre"], "whislo": s["min"], "q1": s["q1"], "med": s["mediana"],
                  "q3": s["q3"], "whishi": s["max"], "fliers": s.get("atipicos", [])} for s in payload["series"]]
        ax.bxp(stats, showfliers=True)
        x = None
    if x is not None:
        paso = max(1, len(x) // 15)
        ax.set_xticks(range(0, len(x), paso))
        ax.set_xticklabels([x[i] for i in range(0, len(x), paso)], rotation=45, ha="right", fontsize=8)
    ax.set_title(payload["titulo"])
    ax.set_xlabel(payload.get("x", {}).get("etiqueta", ""))
    ax.set_ylabel(payload.get("y", {}).get("etiqueta", ""))
    if tipo != "caja" and len(payload.get("series", [])) > 1:
        ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    _conclusion(fig, payload)
    plt.show()
