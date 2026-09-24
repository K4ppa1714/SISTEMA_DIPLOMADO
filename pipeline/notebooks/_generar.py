"""Genera los notebooks 01, 02, 04 y 05 (dueño: Claude-E) a partir del código del pipeline.

Los notebooks NO contienen lógica propia ni números escritos a mano: llaman a los
módulos de pipeline/src, dibujan cada payload con matplotlib (título, ejes con
unidades y la conclusión debajo) y terminan con una celda "Conclusiones" que
imprime las conclusiones calculadas por el código.

Uso (genera y luego ejecuta con salidas visibles):
    python pipeline/notebooks/_generar.py
    jupyter nbconvert --to notebook --execute --inplace pipeline/notebooks/0[1245]_*.ipynb
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent

PREAMBULO = """import sys, pathlib
raiz = pathlib.Path.cwd()
while not (raiz / "pipeline").exists() and raiz != raiz.parent:
    raiz = raiz.parent
sys.path.insert(0, str(raiz))
import warnings; warnings.filterwarnings("ignore")
import pandas as pd
pd.set_option("display.max_colwidth", 120)
from pipeline.notebooks.graficas import dibujar, tabla"""


def md(texto: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": texto.strip("\n").splitlines(keepends=True)}


def code(texto: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": texto.strip("\n").splitlines(keepends=True)}


def notebook(celdas: list[dict]) -> dict:
    return {"cells": celdas, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                                          "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def guardar(nombre: str, celdas: list[dict]) -> None:
    (AQUI / nombre).write_text(json.dumps(notebook(celdas), ensure_ascii=False, indent=1), encoding="utf-8")
    print("escrito", nombre)


NB = {
    "01_pipeline_datos.ipynb": [
        md("""# 01 · Pipeline de datos (T-04, bloque A)

**Dónde:** `pipeline/src/data/limpieza.py`. **Por qué:** los datos crudos traen duplicados, lecturas nulas,
retrocesos de medidor e importes con una tarifa inventada; además hay que definir el objetivo `pago_tardio`
sin fuga de información. **Cómo:** carga tipada, deduplicación, marcas de calidad (no se imputa),
recálculo de importes con el tarifario CEA real (T-03), censura por `FECHA_CORTE` y `merge` de recibos,
lecturas y tomas. **Con qué datos:** los cinco CSV de `data/simulados/` (simulación declarada, sin datos personales)."""),
        code(PREAMBULO),
        code("""from pipeline.src.data.limpieza import ejecutar
tablas, informe = ejecutar()
informe"""),
        code("""for nombre, df in tablas.items():
    print(f"{nombre:11s} {df.shape}")
tablas["dataset"].dtypes.value_counts()"""),
        code("""tablas["dataset"].head()"""),
        md("## Conclusiones"),
        code("""for fila in informe.itertuples():
    print(f"- {fila.Paso}: {fila.Resultado}")"""),
    ],
    "02_eda_estadistica.ipynb": [
        md("""# 02 · EDA y estadística (T-05, bloques B y C)

**Dónde:** `pipeline/src/preprocessing/eda.py`. **Por qué:** entender escalas de consumo, cartera, segmentos y quejas
antes de modelar, y probar dos hipótesis definidas antes de ver los resultados. **Cómo:** distribuciones, series
mensuales, tasas por segmento; Kruskal-Wallis (H1), chi² (H2), IC 95 % de Wilson y Spearman. **Con qué datos:** la tabla
de análisis de T-04 (recibos con etiqueta solo hasta la fecha de corte)."""),
        code(PREAMBULO),
        code("""from pipeline.src.preprocessing.eda import ejecutar
eda, estadistica = ejecutar()
for r in eda:
    dibujar(r["payload"])"""),
        md("## Estadística inferencial"),
        code("""for r in estadistica:
    dibujar(r["payload"])"""),
        md("## Conclusiones"),
        code("""for r in eda + estadistica:
    print(f"- {r['payload']['titulo']}: {r['payload']['conclusion']}")"""),
    ],
    "04_modelos.ipynb": [
        md("""# 04 · Features y modelos de pago tardío (T-07, bloques E, F y H)

**Dónde:** `pipeline/src/features/variables.py` y `pipeline/src/ml/modelos.py`. **Por qué:** anticipar qué recibos se
pagarán tarde para priorizar la cobranza. **Cómo:** variables conocidas al emitir el recibo (cada una justificada),
separación temporal (prueba = 4 últimos periodos etiquetados), CV temporal por periodo, líneas base, regresión
logística, Random Forest, Gradient Boosting y ensamble de votación en `Pipeline`; umbral elegido en CV.
**Con qué datos:** recibos etiquetados; los recibos censurados se predicen por lotes."""),
        code(PREAMBULO),
        code("""from pipeline.src.features.variables import JUSTIFICACION
pd.DataFrame(JUSTIFICACION.items(), columns=["variable", "justificación"])"""),
        code("""from pipeline.src.ml.modelos import ejecutar, payloads
res = ejecutar()
for r in payloads(res):
    dibujar(r["payload"])"""),
        code("""res["predicciones"].sort_values("prob_pago_tardio", ascending=False).head(10)"""),
        md("## Conclusiones"),
        code("""for r in payloads(res):
    print(f"- {r['payload']['titulo']}: {r['payload']['conclusion']}")"""),
    ],
    "05_errores.ipynb": [
        md("""# 05 · Análisis de errores e interpretación (T-09)

**Dónde:** `pipeline/src/ml/errores.py`. **Por qué:** una métrica sola no dice dónde ni por qué falla el modelo.
**Cómo:** curva de umbral, calibración por decil y perfil de aciertos y errores en la prueba temporal.
**Con qué datos:** las predicciones del modelo elegido en T-07 sobre los 4 últimos periodos etiquetados."""),
        code(PREAMBULO),
        code("""from pipeline.src.ml import errores
salida = errores.ejecutar()
for r in salida:
    dibujar(r["payload"])"""),
        md("## Conclusiones"),
        code("""for r in salida:
    print(f"- {r['payload']['titulo']}: {r['payload']['conclusion']}")"""),
    ],
    "03_series_fourier_wavelets.ipynb": [
        md("""# 03 · Series de tiempo, Fourier y wavelets (T-06, bloques D, O y P)

**Dónde:** `pipeline/src/signals/temporal.py`. **Por qué:** entender la dinámica del consumo y detectar fugas en la
telemetría horaria. **Cómo:** descomposición y predicción de la serie mensual, media móvil, autocorrelación y cambio
de régimen; FFT con conversión frecuencia → periodo y reconstrucción filtrada; DWT/SWT db4 con energía por nivel y
detección de fugas contra la regla de flujo nocturno. **Con qué datos:** consumo mensual de recibos y telemetría
horaria de 40 tomas; `tiene_fuga` solo para evaluar."""),
        code(PREAMBULO),
        code("""from pipeline.src.signals.temporal import ejecutar
r = ejecutar()
for modulo in ("series", "fourier", "wavelets"):
    for x in r[modulo]:
        dibujar(x["payload"])"""),
        md("## Conclusiones"),
        code("""for modulo in ("series", "fourier", "wavelets"):
    for x in r[modulo]:
        print(f"- {x['payload']['titulo']}: {x['payload']['conclusion']}")"""),
    ],
    "06_segmentos_dl.ipynb": [
        md("""# 06 · Segmentación (K-means + PCA) y red neuronal (T-08, bloques G e I)

**Dónde:** `pipeline/src/ml/segmentos.py` y `pipeline/src/deep_learning/mlp.py`. **Por qué:** agrupar tomas con
comportamiento parecido para priorizar acciones, y probar si una red neuronal mejora al mejor modelo clásico.
**Cómo:** K elegido por silhouette y PCA de 2 componentes; MLP en PyTorch (64-32, dropout, parada temprana) contra
Gradient Boosting con la misma separación temporal de T-07. **Con qué datos:** variables por toma y por recibo de T-04/T-07."""),
        code(PREAMBULO),
        code("""from pipeline.src.ml import segmentos
seg_res, seg = segmentos.ejecutar()
for x in seg_res:
    dibujar(x["payload"])"""),
        code("""from pipeline.src.deep_learning import mlp
dl = mlp.ejecutar()
for x in dl:
    dibujar(x["payload"])"""),
        md("## Conclusiones"),
        code("""for x in seg_res + dl:
    print(f"- {x['payload']['titulo']}: {x['payload']['conclusion']}")"""),
    ],
}

if __name__ == "__main__":
    # No sobrescribe notebooks ya ejecutados salvo con --forzar.
    forzar = "--forzar" in sys.argv
    for nombre, celdas in NB.items():
        if forzar or not (AQUI / nombre).exists():
            guardar(nombre, celdas)
