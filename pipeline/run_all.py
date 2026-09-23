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


def main() -> None:
    for tarea, nombre in PASOS:
        print(f"[{tarea}] {nombre}: pendiente de implementar")


if __name__ == "__main__":
    main()
