"""Clasificación de quejas por categoría con TF-IDF + regresión logística (bloque J).

Dónde: quejas de data/simulados/quejas.csv (1,400 quejas, 9 categorías).
Por qué: el área de atención necesita enrutar la queja a la cuadrilla correcta
sin leerla primero; la categoría es la decisión de enrutamiento.
Cómo: TF-IDF (unigramas y bigramas) + regresión logística multiclase dentro de
un `Pipeline` de sklearn; hiperparámetros por validación cruzada estratificada.

Punto crítico — fuga por textos repetidos:
la simulación repite textos (solo 331 descripciones distintas en 1,400 quejas)
y cada texto tiene una sola categoría. Si se divide por fila, casi todas las
quejas de prueba tienen su texto idéntico en entrenamiento y el modelo solo
"recuerda". Por eso la división de entrenamiento/prueba se hace por TEXTO ÚNICO
(regla (b) de la propuesta #5, aprobada por Andrés). Este módulo también mide
la división ingenua por fila para dejar documentado cuánto se inflaría la métrica.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold, StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

from pipeline.src.config import DATOS_SIMULADOS, SEMILLA
from pipeline.src.nlp.texto import tokenizar

PROPORCION_PRUEBA = 0.25
REJILLA = {
    "tfidf__ngram_range": [(1, 1), (1, 2)],
    "clf__C": [0.3, 1.0, 3.0, 10.0],
}


def cargar_quejas(ruta=None) -> pd.DataFrame:
    """Carga quejas.csv y descarta filas sin texto o sin categoría (no se imputan)."""
    ruta = ruta or DATOS_SIMULADOS / "quejas.csv"
    df = pd.read_csv(ruta)
    faltan = {"descripcion", "categoria", "prioridad"} - set(df.columns)
    if faltan:
        raise ValueError(f"quejas.csv no trae las columnas {sorted(faltan)}")
    df = df.dropna(subset=["descripcion", "categoria"]).copy()
    df["descripcion"] = df["descripcion"].astype(str)
    return df


def textos_unicos(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por texto distinto, con su categoría y cuántas veces aparece.

    Falla si un mismo texto tiene más de una categoría: entonces la etiqueta
    sería ambigua y la división por texto único no bastaría.
    """
    conflicto = df.groupby("descripcion")["categoria"].nunique()
    if (conflicto > 1).any():
        raise ValueError(f"{int((conflicto > 1).sum())} textos tienen más de una categoría")
    return (
        df.groupby("descripcion", as_index=False)
        .agg(categoria=("categoria", "first"), ocurrencias=("categoria", "size"))
        .sort_values("descripcion")
        .reset_index(drop=True)
    )


def dividir_por_texto_unico(unicos: pd.DataFrame, semilla: int = SEMILLA):
    """Divide los textos únicos (no las filas) en entrenamiento y prueba, estratificado por categoría."""
    return train_test_split(
        unicos, test_size=PROPORCION_PRUEBA, stratify=unicos["categoria"], random_state=semilla
    )


def construir_modelo(ngram_range=(1, 2), C: float = 1.0) -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    tokenizer=tokenizar, token_pattern=None, lowercase=False,
                    ngram_range=ngram_range, sublinear_tf=True, min_df=1,
                ),
            ),
            (
                "clf",
                LogisticRegression(C=C, max_iter=2000, class_weight="balanced", random_state=SEMILLA),
            ),
        ]
    )


@dataclass
class ResultadoClasificacion:
    mejores_parametros: dict
    cv_f1_macro_media: float
    cv_f1_macro_desv: float
    n_entrenamiento: int
    n_prueba: int
    metricas: list[dict] = field(default_factory=list)       # una fila por (modelo, evaluación)
    por_categoria: pd.DataFrame | None = None
    matriz: pd.DataFrame | None = None
    palabras_clave: pd.DataFrame | None = None
    modelo: Pipeline | None = None


def _fila(modelo: str, evaluacion: str, y_real, y_pred, n: int) -> dict:
    return {
        "modelo": modelo,
        "evaluacion": evaluacion,
        "n_prueba": int(n),
        "accuracy": round(float(accuracy_score(y_real, y_pred)), 4),
        "f1_macro": round(float(f1_score(y_real, y_pred, average="macro")), 4),
    }


def palabras_clave_por_categoria(modelo: Pipeline, n: int = 5) -> pd.DataFrame:
    """Términos con mayor coeficiente positivo por categoría (explica qué 'mira' el modelo)."""
    vocab = np.asarray(modelo.named_steps["tfidf"].get_feature_names_out())
    clf = modelo.named_steps["clf"]
    filas = []
    for i, cat in enumerate(clf.classes_):
        top = np.argsort(clf.coef_[i])[::-1][:n]
        filas.append({"categoria": cat, "terminos": ", ".join(vocab[top])})
    return pd.DataFrame(filas)


def entrenar_y_evaluar(df: pd.DataFrame | None = None) -> ResultadoClasificacion:
    df = cargar_quejas() if df is None else df
    unicos = textos_unicos(df)
    entrena, prueba = dividir_por_texto_unico(unicos)
    assert not set(entrena["descripcion"]) & set(prueba["descripcion"]), "fuga: texto en ambos lados"

    # 1) Hiperparámetros: validación cruzada SOLO dentro de entrenamiento.
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA)
    busqueda = GridSearchCV(construir_modelo(), REJILLA, scoring="f1_macro", cv=cv, n_jobs=1)
    busqueda.fit(entrena["descripcion"], entrena["categoria"])
    modelo = busqueda.best_estimator_
    idx = busqueda.best_index_
    cv_media = float(busqueda.cv_results_["mean_test_score"][idx])
    cv_desv = float(busqueda.cv_results_["std_test_score"][idx])

    # 2) Evaluación en prueba por texto único (métrica principal).
    pred = modelo.predict(prueba["descripcion"])
    metricas = [_fila("TF-IDF + regresión logística", "prueba por texto único", prueba["categoria"], pred, len(prueba))]

    # 2b) Misma prueba, ponderada por cuántas quejas reales tiene cada texto.
    filas_prueba = df[df["descripcion"].isin(set(prueba["descripcion"]))]
    metricas.append(
        _fila("TF-IDF + regresión logística", "prueba por texto único, ponderada por quejas",
              filas_prueba["categoria"], modelo.predict(filas_prueba["descripcion"]), len(filas_prueba))
    )

    # 3) Línea base: siempre la clase más frecuente.
    base = DummyClassifier(strategy="most_frequent").fit(entrena["descripcion"], entrena["categoria"])
    metricas.append(_fila("Línea base (clase más frecuente)", "prueba por texto único",
                          prueba["categoria"], base.predict(prueba["descripcion"]), len(prueba)))

    # 4) Contraste: división ingenua por fila (con fuga) para documentar la inflación.
    tr, te = train_test_split(df, test_size=PROPORCION_PRUEBA, stratify=df["categoria"], random_state=SEMILLA)
    ingenuo = construir_modelo(**_params_modelo(busqueda.best_params_)).fit(tr["descripcion"], tr["categoria"])
    fila_ingenua = _fila("TF-IDF + regresión logística", "división ingenua por fila (CON FUGA, no válida)",
                         te["categoria"], ingenuo.predict(te["descripcion"]), len(te))
    fila_ingenua["textos_de_prueba_vistos_en_entrenamiento"] = round(
        float(te["descripcion"].isin(set(tr["descripcion"])).mean()), 4)
    metricas.append(fila_ingenua)

    # Detalle por categoría y matriz de confusión (prueba por texto único).
    etiquetas = sorted(unicos["categoria"].unique())
    p, r, f, s = precision_recall_fscore_support(prueba["categoria"], pred, labels=etiquetas, zero_division=0)
    por_cat = pd.DataFrame({"categoria": etiquetas, "precision": p.round(4), "recall": r.round(4),
                            "f1": f.round(4), "textos_prueba": s})
    matriz = pd.DataFrame(confusion_matrix(prueba["categoria"], pred, labels=etiquetas),
                          index=etiquetas, columns=etiquetas)

    # Modelo final: se reentrena con TODOS los textos únicos para uso posterior;
    # las métricas reportadas son las de la prueba de arriba, no las de este ajuste.
    final = construir_modelo(**_params_modelo(busqueda.best_params_)).fit(unicos["descripcion"], unicos["categoria"])

    return ResultadoClasificacion(
        mejores_parametros={k: (list(v) if isinstance(v, tuple) else v) for k, v in busqueda.best_params_.items()},
        cv_f1_macro_media=round(cv_media, 4), cv_f1_macro_desv=round(cv_desv, 4),
        n_entrenamiento=len(entrena), n_prueba=len(prueba),
        metricas=metricas, por_categoria=por_cat, matriz=matriz,
        palabras_clave=palabras_clave_por_categoria(final), modelo=final,
    )


def _params_modelo(best: dict) -> dict:
    return {"ngram_range": tuple(best["tfidf__ngram_range"]), "C": best["clf__C"]}


def prioridad_desde_texto(df: pd.DataFrame | None = None) -> dict:
    """¿El texto de la queja determina su prioridad? (insumo de diseño para T-12 triage).

    Validación cruzada agrupada por texto (StratifiedGroupKFold) para que un mismo
    texto no esté en entrenamiento y prueba a la vez.
    """
    df = cargar_quejas() if df is None else df.copy()
    grupos = df["descripcion"]
    n_prior = df.groupby("descripcion")["prioridad"].nunique()
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEMILLA)
    f1_texto = cross_val_score(construir_modelo(), df["descripcion"], df["prioridad"],
                               groups=grupos, cv=cv, scoring="f1_macro")
    f1_azar = cross_val_score(DummyClassifier(strategy="stratified", random_state=SEMILLA),
                              df["descripcion"], df["prioridad"], groups=grupos, cv=cv, scoring="f1_macro")
    return {
        "textos_unicos": int(len(n_prior)),
        "textos_con_mas_de_una_prioridad": int((n_prior > 1).sum()),
        "f1_macro_tfidf": round(float(f1_texto.mean()), 4),
        "f1_macro_tfidf_desv": round(float(f1_texto.std()), 4),
        "f1_macro_azar_estratificado": round(float(f1_azar.mean()), 4),
    }
