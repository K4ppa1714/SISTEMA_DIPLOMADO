"""Evaluadores de L (LLM) y M (RAG) sin red."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api._lib.llm import ErrorLLM  # noqa: E402
from pipeline.src.nlp.evaluar_llm import evaluar, payloads as payloads_llm  # noqa: E402
from pipeline.src.rag.evaluar import calcular, cargar_preguntas, payloads as payloads_rag, rango  # noqa: E402


class LlmEco:
    """Responde la categoría que se le indique; falla en los textos marcados."""
    nombre = "eco"

    def __init__(self, categoria):
        self.categoria = categoria

    def generar_json(self, sistema, usuario):
        if "FALLA" in usuario:
            raise ErrorLLM("HTTP 429")
        return json.dumps({"resumen": "Resumen de prueba de la queja.", "categoria": self.categoria, "riesgo": False})


def test_metricas_llm():
    textos = ["Hay una fuga en la calle desde ayer", "Hay una fuga en la calle frente al parque", "FALLA fuga en la calle"]
    m, filas = evaluar(textos, ["fuga_calle"] * 3, LlmEco("fuga_calle"))
    assert m["textos"] == 3 and m["formato_valido"] == round(2 / 3, 4)
    assert m["acuerdo_llm_modelo"] == 1.0 and m["exactitud_llm"] == 1.0
    assert payloads_llm(m)[0]["payload"]["tipo"] == "metrica"


def test_rango_y_recall_mrr():
    assert rango([{"documento_id": "a"}, {"documento_id": "b"}], "b") == 2
    preguntas = [{"pregunta": "p1", "esperado": "A", "con_evidencia": True}, {"pregunta": "p2", "esperado": "B", "con_evidencia": True},
                 {"pregunta": "p3", "esperado": "", "con_evidencia": False}]
    tops = {"p1": [{"documento_id": "A", "similitud": 0.9}], "p2": [{"documento_id": "X", "similitud": 0.8}, {"documento_id": "Y", "similitud": 0.7},
            {"documento_id": "B", "similitud": 0.65}], "p3": [{"documento_id": "Z", "similitud": 0.3}]}
    m, _ = calcular(preguntas, lambda q: tops[q], 0.6)
    assert m["recall@1"] == 0.5 and m["recall@3"] == 1.0 and m["mrr"] == round((1 + 1 / 3) / 2, 4)
    assert m["abstencion_correcta"] == 1.0 and m["falsa_abstencion"] == 0.0
    assert payloads_rag(m, [], False)[0]["payload"]["series"][0]["valores"][0] == 0.5


def test_preguntas_del_borrador():
    todas = cargar_preguntas(incluir_sin_validar=True)
    assert len(todas) == 40 and sum(not p["con_evidencia"] for p in todas) == 7
