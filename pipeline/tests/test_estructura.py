"""Prueba mínima: la estructura del pipeline existe y la configuración es coherente."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

MODULOS = ["data", "preprocessing", "features", "ml", "deep_learning", "signals", "nlp", "rag", "agents"]


def test_modulos_importan():
    for m in MODULOS:
        importlib.import_module(f"pipeline.src.{m}")


def test_datos_simulados_presentes():
    from pipeline.src.config import DATOS_SIMULADOS
    for archivo in ["tomas.csv", "recibos.csv", "lecturas.csv", "telemetria.csv", "quejas.csv"]:
        assert (DATOS_SIMULADOS / archivo).exists(), archivo


def test_columnas_prohibidas_incluyen_parametros_del_generador():
    from pipeline.src.config import COLUMNAS_PROHIBIDAS
    assert {"propension_mora", "consumo_base", "tiene_fuga"} <= COLUMNAS_PROHIBIDAS
