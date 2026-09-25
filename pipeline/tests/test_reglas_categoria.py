"""Reglas de corrección de categoría del triage (#72/#76). Sin red."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api._lib.clasificador_quejas import cargar_modelo  # noqa: E402
from api._lib.prioridad import calcular_prioridad, corregir_categoria  # noqa: E402
from api._lib.triage import triage  # noqa: E402
from pipeline.src.nlp.clasificador import cargar_quejas, textos_unicos  # noqa: E402


def test_fuga_en_banqueta_es_fuga_calle_con_prioridad_alta():
    s, d = triage("Desde ayer sale agua de la banqueta frente a mi casa y ya hay un charco enorme")
    assert s.categoria == "fuga_calle" and s.prioridad >= 2
    assert d["regla_categoria"] and d["categoria_modelo"] == "fuga_toma"


def test_sin_agua_no_se_confunde_con_fuga_y_bebe_es_urgente():
    s, d = triage("No hay agua en mi casa desde hace tres días, tengo un bebé")
    assert s.categoria == "sin_agua" and s.prioridad == 3


def test_fuga_dentro_de_la_toma_no_cambia():
    assert corregir_categoria("fuga_toma", "Se rompió el tubo de mi toma y tira agua dentro de mi casa") == ("fuga_toma", None)


def test_drenaje_que_escurre_a_la_calle_no_cambia():
    assert corregir_categoria("drenaje", "Registro de alcantarillado tapado, escurre a la calle.")[0] == "drenaje"


def test_reglas_no_cambian_ninguna_prediccion_del_conjunto_simulado():
    """Las reglas solo corrigen casos fuera de la simulación: sobre los 331 textos únicos no cambian nada."""
    modelo, unicos = cargar_modelo(), textos_unicos(cargar_quejas())
    cambios = [t for t in unicos["descripcion"] if corregir_categoria(modelo.predecir(t)[0], t)[1] is not None]
    assert cambios == []


def test_prioridad_de_fuga_calle_es_al_menos_alta():
    assert calcular_prioridad("fuga_calle", "fuga en la calle")[0] >= 2


def test_sale_mucha_agua_frente_a_mi_casa_es_fuga_calle():
    # Caso límite reportado en producción (#86): "sale mucha agua" no coincidía con "sale agua".
    from api._lib.prioridad import corregir_categoria
    cat, motivo = corregir_categoria("fuga_toma", "Sale mucha agua de la banqueta frente a mi casa desde ayer")
    assert cat == "fuga_calle" and motivo
    # Dentro del predio no cambia aunque use la misma construcción.
    assert corregir_categoria("fuga_toma", "Sale mucha agua de mi medidor en la banqueta")[0] == "fuga_toma"
