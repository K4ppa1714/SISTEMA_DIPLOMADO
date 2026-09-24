"""Reconstruye todos los resultados desde data/simulados/.

Uso:  python pipeline/run_all.py
Cada paso escribe en pipeline/artefactos/ y en Supabase (analitica.*).
Los pasos se implementan en las tareas indicadas (docs/TAREAS.md).
"""

PASOS = [
    ("T-04", "pipeline de datos"),
    ("T-05", "EDA y estadística"),
    ("T-06", "series, Fourier y Wavelets"),
    ("T-07", "features y modelos supervisados"),
    ("T-08", "clustering, PCA y deep learning"),
    ("T-14", "NLP y embeddings"),
    ("T-16", "evaluación de RAG y agente"),
]


def paso_t04() -> None:
    from pipeline.src.config import ARTEFACTOS
    from pipeline.src.data.limpieza import ejecutar

    tablas, informe = ejecutar()
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    tablas["dataset"].to_csv(ARTEFACTOS / "dataset_limpio.csv", index=False)
    informe.to_csv(ARTEFACTOS / "informe_calidad.csv", index=False)
    print(informe.to_string(index=False))


def paso_t05() -> None:
    from pipeline.src.data.publicar import guardar, subir
    from pipeline.src.preprocessing.eda import ejecutar

    eda, est = ejecutar()
    for modulo, res in (("eda", eda), ("estadistica", est)):
        subir(guardar(modulo, res))
        for r in res:
            print(f"  {modulo}/{r['clave']}: {r['payload']['conclusion']}")


def paso_t07() -> None:
    from pipeline.src.config import ARTEFACTOS
    from pipeline.src.data.publicar import guardar, subir
    from pipeline.src.ml import errores
    from pipeline.src.ml.modelos import ejecutar, payloads, sql_predicciones

    res = ejecutar()
    subir(guardar("ml", payloads(res) + errores.ejecutar(res)))  # T-07 + T-09
    pred = res["predicciones"]
    pred.to_csv(ARTEFACTOS / "predicciones_pago.csv", index=False)
    (ARTEFACTOS / "resultados" / "predicciones_pago.sql").write_text(sql_predicciones(pred), encoding="utf-8")
    print(f"  ml: elegido {res['elegido']}; {len(pred)} predicciones por lotes")


IMPLEMENTADOS = {"T-04": paso_t04, "T-05": paso_t05, "T-07": paso_t07}


def main() -> None:
    for tarea, nombre in PASOS:
        if tarea in IMPLEMENTADOS:
            print(f"[{tarea}] {nombre}")
            IMPLEMENTADOS[tarea]()
        else:
            print(f"[{tarea}] {nombre}: pendiente de implementar")


if __name__ == "__main__":
    main()
