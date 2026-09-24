"""T-08 (parte 2) — Red neuronal MLP en PyTorch contra Gradient Boosting (bloque I).

Mismo problema, variables y separación temporal que T-07 (pago tardío por recibo):
- entrenamiento: periodos anteriores a la prueba; se aparta el último periodo de
  entrenamiento como validación para parar temprano (early stopping) y elegir umbral;
- prueba: los 4 últimos periodos con etiqueta (idéntica a T-07).
Arquitectura: entrada → 64 → 32 → 1, ReLU, dropout 0.2, BCEWithLogits con
pos_weight (clase positiva ~25 %), Adam lr 1e-3, lotes de 256, semilla 42.
La red no tiene que ganar: se reporta la comparación honesta contra Gradient Boosting.
"""
from __future__ import annotations

import numpy as np
import torch
from sklearn.base import clone
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from torch import nn

from pipeline.src.config import SEMILLA
from pipeline.src.features.variables import BINARIAS, CATEGORICAS, NUMERICAS, construir
from pipeline.src.data.limpieza import ejecutar as limpiar
from pipeline.src.ml.modelos import PERIODOS_PRUEBA, mejor_umbral, modelos, preprocesador

FUENTE = "pipeline/src/deep_learning/mlp.py · pipeline/notebooks/06_segmentos_dl.ipynb"
X_COLS = NUMERICAS + BINARIAS + CATEGORICAS


class MLP(nn.Module):
    def __init__(self, n: int):
        super().__init__()
        self.red = nn.Sequential(nn.Linear(n, 64), nn.ReLU(), nn.Dropout(0.2),
                                 nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1))

    def forward(self, x):
        return self.red(x).squeeze(-1)


def entrenar(Xtr, ytr, Xva, yva, epocas: int = 100, paciencia: int = 10):
    torch.manual_seed(SEMILLA)
    np.random.seed(SEMILLA)
    modelo = MLP(Xtr.shape[1])
    pos_weight = torch.tensor((1 - ytr.mean()) / ytr.mean(), dtype=torch.float32)
    perdida = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.Adam(modelo.parameters(), lr=1e-3, weight_decay=1e-4)
    Xt, yt = torch.tensor(Xtr, dtype=torch.float32), torch.tensor(ytr, dtype=torch.float32)
    Xv, yv = torch.tensor(Xva, dtype=torch.float32), torch.tensor(yva, dtype=torch.float32)
    gen = torch.Generator().manual_seed(SEMILLA)
    historia, mejor, estado, sin_mejora = [], np.inf, None, 0
    for ep in range(epocas):
        modelo.train()
        orden = torch.randperm(len(Xt), generator=gen)
        total = 0.0
        for i in range(0, len(Xt), 256):
            idx = orden[i:i + 256]
            opt.zero_grad()
            l = perdida(modelo(Xt[idx]), yt[idx])
            l.backward()
            opt.step()
            total += l.item() * len(idx)
        modelo.eval()
        with torch.no_grad():
            lv = perdida(modelo(Xv), yv).item()
        historia.append((total / len(Xt), lv))
        if lv < mejor - 1e-4:
            mejor, estado, sin_mejora = lv, {k: v.clone() for k, v in modelo.state_dict().items()}, 0
        else:
            sin_mejora += 1
            if sin_mejora >= paciencia:
                break
    modelo.load_state_dict(estado)
    return modelo, historia


def predecir(modelo, X) -> np.ndarray:
    modelo.eval()
    with torch.no_grad():
        return torch.sigmoid(modelo(torch.tensor(X, dtype=torch.float32))).numpy()


def ejecutar() -> list[dict]:
    tablas, _ = limpiar()
    df = construir(tablas["dataset"])
    etiq = df[df["en_entrenamiento"]].copy()
    etiq["y"] = etiq["pago_tardio"].astype(int)
    per = sorted(etiq["periodo"].unique())
    corte, corte_val = per[-PERIODOS_PRUEBA], per[-PERIODOS_PRUEBA - 1]
    ent = etiq[etiq["periodo"] < corte_val]
    val = etiq[etiq["periodo"] == corte_val]
    pru = etiq[etiq["periodo"] >= corte]

    prep = preprocesador(escalar=True).fit(ent[X_COLS])
    Xtr, Xva, Xpr = (prep.transform(d[X_COLS]) for d in (ent, val, pru))
    Xtr, Xva, Xpr = (np.asarray(x.todense() if hasattr(x, "todense") else x, dtype=np.float32) for x in (Xtr, Xva, Xpr))
    red, historia = entrenar(Xtr, ent["y"].to_numpy(), Xva, val["y"].to_numpy())
    umbral_red = mejor_umbral(val["y"].to_numpy(), predecir(red, Xva))
    p_red = predecir(red, Xpr)

    gb = clone(modelos()["gradient_boosting"]).fit(ent[X_COLS], ent["y"])
    umbral_gb = mejor_umbral(val["y"].to_numpy(), gb.predict_proba(val[X_COLS])[:, 1])
    p_gb = gb.predict_proba(pru[X_COLS])[:, 1]

    y = pru["y"].to_numpy()
    fila = lambda n, p, u: {"modelo": n, "pr_auc": round(average_precision_score(y, p), 4),
                            "roc_auc": round(roc_auc_score(y, p), 4), "umbral": round(u, 2),
                            "f1": round(f1_score(y, (p >= u).astype(int)), 4)}
    filas = [fila("MLP PyTorch (64-32)", p_red, umbral_red), fila("Gradient Boosting", p_gb, umbral_gb)]
    gana = max(filas, key=lambda f: f["pr_auc"])["modelo"]
    n_param = sum(p.numel() for p in red.parameters())
    return [
        {"clave": "mlp_vs_gb", "payload": {
            "tipo": "tabla", "titulo": "Red neuronal (MLP) contra Gradient Boosting — misma prueba temporal",
            "filas": filas,
            "conclusion": f"Gana {gana} por PR-AUC ({filas[0]['pr_auc']:.3f} MLP contra {filas[1]['pr_auc']:.3f} GB). "
                          f"La red tiene {n_param:,} parámetros y entrenó {len(historia)} épocas con parada temprana. "
                          + ("En datos tabulares de este tamaño no supera a los árboles; GB es más simple de explicar y mantener."
                             if gana == "Gradient Boosting" else
                             "Mejora a GB, pero la diferencia debe pesarse contra su menor interpretabilidad."),
            "fuente": FUENTE}},
        {"clave": "mlp_curva_perdida", "payload": {
            "tipo": "linea", "titulo": "Curva de pérdida del MLP (entrenamiento y validación)",
            "x": {"etiqueta": "Época", "valores": [str(i + 1) for i in range(len(historia))]},
            "y": {"etiqueta": "BCE ponderada"},
            "series": [{"nombre": "entrenamiento", "valores": [round(a, 5) for a, _ in historia]},
                       {"nombre": "validación", "valores": [round(b, 5) for _, b in historia]}],
            "conclusion": f"La validación deja de mejorar en la época {int(np.argmin([b for _, b in historia])) + 1}; "
                          "la parada temprana evita el sobreajuste que se ve cuando la pérdida de entrenamiento sigue bajando.",
            "fuente": FUENTE}},
    ]


if __name__ == "__main__":
    for r in ejecutar():
        print(r["clave"], "→", r["payload"]["conclusion"])
