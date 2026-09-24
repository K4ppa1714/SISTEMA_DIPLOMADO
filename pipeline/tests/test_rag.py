"""Pruebas de T-11 (RAG) sin red: embeddings, búsqueda y LLM simulados."""
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api._lib.embeddings import EmbeddingsGemini  # noqa: E402
from api._lib.llm import ErrorLLM  # noqa: E402
from api._lib.rag import SIN_EVIDENCIA, UMBRAL_SIMILITUD, responder  # noqa: E402
from pipeline.src.rag.corpus import Documento, construir_corpus, documentos_externos, fragmentar  # noqa: E402

TEXTO = ("Primer párrafo sobre tarifas domésticas y su cálculo mensual. " * 8 + "\n\n"
         + "Segundo párrafo con reglas de IVA y saneamiento. " * 10 + "\n\n" + "Tercero corto.")


def test_fragmentos_respetan_tamano_y_no_pierden_texto():
    frags = fragmentar(TEXTO, tamano=300, solape=60)
    assert len(frags) > 2 and all(len(f) <= 300 + 60 + 2 for f in frags)
    assert "Tercero corto." in frags[-1]
    assert "Primer párrafo" in frags[0]


def test_ids_deterministas():
    d = Documento("Título", "regla", "archivo.py", "texto")
    assert d.documento_id == Documento("Título", "regla", "archivo.py", "otro").documento_id
    assert d.fragmento_id(0) != d.fragmento_id(1)


def test_corpus_del_repo_sin_datos_personales():
    docs = construir_corpus()
    assert docs, "el corpus no debe quedar vacío"
    texto = " ".join(f for d in docs for f in d.fragmentos)
    assert "@" not in texto  # sin correos


def test_documento_externo_exige_cabecera(tmp_path):
    (tmp_path / "malo.md").write_text("titulo: X\n---\ncuerpo", encoding="utf-8")
    with pytest.raises(ValueError):
        documentos_externos(tmp_path)
    (tmp_path / "malo.md").write_text("titulo: NOM\ntipo: norma\nfuente: DOF\nurl: https://dof.gob.mx\n---\ncuerpo", encoding="utf-8")
    assert documentos_externos(tmp_path)[0].url == "https://dof.gob.mx"


def test_embeddings_gemini_normaliza_y_valida_dimension():
    vistos = []

    def manejador(request):
        cuerpo = json.loads(request.content)
        assert "taskType" not in cuerpo["requests"][0]  # gemini-embedding-2 no lo acepta
        vistos.append(cuerpo["requests"][0]["outputDimensionality"])
        return httpx.Response(200, json={"embeddings": [{"values": [3, 4, 0, 0]} for _ in cuerpo["requests"]]})

    e = EmbeddingsGemini("k", "gemini-embedding-2", 4, httpx.Client(transport=httpx.MockTransport(manejador)))
    assert e.embeber(["a", "b"]) == [[0.6, 0.8, 0.0, 0.0]] * 2
    assert vistos == [4]
    malo = EmbeddingsGemini("k", "m", 8, httpx.Client(transport=httpx.MockTransport(manejador)))
    with pytest.raises(ErrorLLM):
        malo.embeber(["a"])


class EmbFalso:
    def embeber(self, textos):
        return [[1.0, 0.0]] * len(textos)


def buscador(similitudes):
    def buscar(vector, k):
        return [{"fragmento_id": i, "documento_id": i, "titulo": f"Doc {i}", "contenido": f"contenido {i}", "similitud": s}
                for i, s in enumerate(similitudes[:k])]
    return buscar


class LLMFalso:
    nombre = "falso"

    def __init__(self, r):
        self.r = r

    def generar_json(self, s, u):
        if isinstance(self.r, Exception):
            raise self.r
        return self.r


def test_sin_evidencia_no_llama_al_llm():
    llm = LLMFalso(AssertionError("no debió llamarse"))
    salida, det = responder("¿cuánto cuesta?", 5, EmbFalso(), buscador([UMBRAL_SIMILITUD - 0.1]), llm)
    assert salida.evidencia is False and salida.respuesta == SIN_EVIDENCIA and salida.fuentes == []


def test_con_evidencia_devuelve_solo_fuentes_citadas():
    llm = LLMFalso(json.dumps({"respuesta": "Cuesta X.", "fuentes_usadas": [2]}))
    salida, _ = responder("¿cuánto cuesta?", 5, EmbFalso(), buscador([0.9, 0.8, 0.2]), llm)
    assert salida.evidencia and [f.titulo for f in salida.fuentes] == ["Doc 1"]


def test_llm_dice_sin_evidencia():
    salida, _ = responder("¿clima?", 5, EmbFalso(), buscador([0.9]), LLMFalso('{"respuesta": "SIN_EVIDENCIA"}'))
    assert salida.evidencia is False and salida.respuesta == SIN_EVIDENCIA


@pytest.mark.parametrize("r", [ErrorLLM("503"), "no json", json.dumps({"respuesta": "x", "fuentes_usadas": [9]})])
def test_fallas_del_llm_dan_respuesta_extractiva_honesta(r):
    salida, det = responder("¿cuánto cuesta?", 5, EmbFalso(), buscador([0.9]), LLMFalso(r))
    assert salida.evidencia and "No pude generar" in salida.respuesta and det["llm"].startswith("falló")


def test_k_fuera_de_rango():
    with pytest.raises(Exception):
        responder("¿cuánto cuesta?", 50, EmbFalso(), buscador([0.9]), None)
