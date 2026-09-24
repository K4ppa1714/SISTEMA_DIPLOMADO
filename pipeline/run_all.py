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


IMPLEMENTADOS = {"T-04": paso_t04}


def main() -> None:
    for tarea, nombre in PASOS:
        if tarea in IMPLEMENTADOS:
            print(f"[{tarea}] {nombre}")
            IMPLEMENTADOS[tarea]()
        else:
            print(f"[{tarea}] {nombre}: pendiente de implementar")


if __name__ == "__main__":
    main()
