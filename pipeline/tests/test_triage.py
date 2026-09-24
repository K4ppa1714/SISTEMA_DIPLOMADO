"""Pruebas de T-12 (triage). Sin red: el LLM se simula con httpx.MockTransport o un cliente falso."""
import json
import sys
from pathlib import Path

import httpx
import numpy as np
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api._lib import texto as texto_api  # noqa: E402
from api._lib.clasificador_quejas import ModeloQuejas  # noqa: E402
from api._lib.llm import ClienteConRespaldo, ClienteGemini, ClienteGroq, ErrorLLM, crear_cliente  # noqa: E402
from api._lib.prioridad import calcular_prioridad  # noqa: E402
from api._lib.triage import ocultar_datos_personales, triage  # noqa: E402
from pipeline.src.nlp import texto as texto_pipeline  # noqa: E402
from pipeline.src.nlp.clasificador import cargar_quejas, entrenar_y_evaluar, textos_unicos  # noqa: E402
from pipeline.src.nlp.exportar import exportar  # noqa: E402


@pytest.fixture(scope="module")
def modelos():
    sk = entrenar_y_evaluar().modelo
    return sk, ModeloQuejas(json.loads(json.dumps(exportar(sk))))


@pytest.fixture(scope="module")
def textos():
    return textos_unicos(cargar_quejas())["descripcion"].tolist()


# --- equivalencia API ↔ pipeline -------------------------------------------------

def test_tokenizador_api_igual_al_del_pipeline(textos):
    assert texto_api.PALABRAS_VACIAS == texto_pipeline.PALABRAS_VACIAS
    for t in textos + ["¡Año nuevo, SIN agua!", None, "nan"]:
        assert texto_api.tokenizar(t) == texto_pipeline.tokenizar(t)


def test_clasificador_puro_igual_a_sklearn(modelos, textos):
    sk, puro = modelos
    esperado = sk.predict(textos)
    probas_sk = sk.predict_proba(textos)
    for i, t in enumerate(textos):
        cat, _, _ = puro.predecir(t)
        assert cat == esperado[i]
        p = puro.probabilidades(t)
        np.testing.assert_allclose([p[c] for c in sk.classes_], probas_sk[i], atol=1e-6)


def test_texto_sin_vocabulario_se_marca(modelos):
    _, puro = modelos
    assert puro.predecir("zzzz qqqq")[2] is False


def test_json_versionado_coincide_con_el_modelo_actual():
    """Si cambia el modelo de T-14 y no se reexporta, esta prueba lo detecta."""
    ruta = Path(__file__).resolve().parents[2] / "api" / "_lib" / "modelo_quejas.json"
    assert json.loads(ruta.read_text(encoding="utf-8")) == json.loads(json.dumps(exportar(), ensure_ascii=False))


# --- prioridad ---------------------------------------------------------------------

def test_prioridad_base_y_urgencia():
    assert calcular_prioridad("sin_agua", "no llega agua")[0] == 2
    assert calcular_prioridad("medidor", "el medidor no marca")[0] == 1
    assert calcular_prioridad("fuga_calle", "hay una fuga frente a la escuela")[0] == 3
    assert calcular_prioridad("facturacion", "me cobraron doble", riesgo_llm=True)[0] == 2
    assert calcular_prioridad("drenaje", "se inundó la calle, está inundada", riesgo_llm=True)[0] == 3  # tope 3


# --- datos personales ---------------------------------------------------------------

def test_oculta_correos_telefonos_y_rfc():
    t = ocultar_datos_personales("Llámenme al 442 123 4567 o a juan.perez@correo.mx, RFC PEPJ800101AB1")
    assert "442" not in t and "@" not in t and "PEPJ" not in t


# --- proveedores (sin red) ----------------------------------------------------------

def _http(respuesta: httpx.Response | Exception):
    def manejador(request):
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_gemini_extrae_texto_y_manda_llave_en_cabecera():
    vistos = {}

    def manejador(request):
        vistos["url"], vistos["llave"] = str(request.url), request.headers.get("x-goog-api-key")
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"a":1}'}]}}]})

    c = ClienteGemini("LLAVE", "modelo-x", httpx.Client(transport=httpx.MockTransport(manejador)))
    assert c.generar_json("s", "u") == '{"a":1}'
    assert vistos["url"].endswith("/models/modelo-x:generateContent") and vistos["llave"] == "LLAVE"
    assert "LLAVE" not in vistos["url"]  # la llave nunca va en la URL


@pytest.mark.parametrize("resp", [
    httpx.Response(500, json={}),
    httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),  # HTTP 200, fallo de negocio
    httpx.TimeoutException("lento"),
])
def test_gemini_errores_se_vuelven_errorllm(resp):
    with pytest.raises(ErrorLLM):
        ClienteGemini("k", "m", _http(resp)).generar_json("s", "u")


def test_respaldo_groq_cuando_falla_el_principal():
    principal = ClienteGemini("k", "m", _http(httpx.Response(503, json={})))
    respaldo = ClienteGroq("k2", "m2", _http(httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})))
    c = ClienteConRespaldo(principal, respaldo)
    assert c.generar_json("s", "u") == "{}" and c.nombre == "groq"


def test_crear_cliente_sin_configuracion_devuelve_none():
    assert crear_cliente({}) is None
    assert crear_cliente({"LLM_PROVIDER": "gemini", "LLM_API_KEY": "k", "LLM_MODEL": "m"}).nombre == "gemini"


# --- triage de punta a punta ---------------------------------------------------------

class LLMFalso:
    nombre = "falso"

    def __init__(self, respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def generar_json(self, sistema, usuario):
        self.llamadas.append(usuario)
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


TEXTO = "No llega agua a mi domicilio desde hace dos semanas, los vecinos igual."


def test_triage_valido_cuando_llm_coincide():
    llm = LLMFalso([json.dumps({"resumen": "Sin agua desde hace dos semanas en la zona.", "categoria": "sin_agua", "riesgo": False})])
    salida, det = triage(TEXTO, llm)
    assert salida.categoria == "sin_agua" and salida.valido and salida.prioridad == 2
    assert det["acuerdo_llm_modelo"] is True


def test_triage_reintenta_una_vez_si_json_invalido():
    llm = LLMFalso(["no es json", json.dumps({"resumen": "Sin agua en la zona.", "categoria": "sin_agua"})])
    salida, det = triage(TEXTO, llm)
    assert salida.valido and det["llm"]["intentos"] == 2


def test_triage_desacuerdo_gana_el_modelo_y_no_es_valido():
    llm = LLMFalso([json.dumps({"resumen": "Problema de cobro.", "categoria": "facturacion"})])
    salida, det = triage(TEXTO, llm)
    assert salida.categoria == "sin_agua" and salida.valido is False and det["categoria_llm"] == "facturacion"


def test_triage_sin_llm_responde_con_respaldo_y_no_valido():
    salida, det = triage(TEXTO, None)
    assert salida.valido is False and salida.resumen and salida.categoria == "sin_agua"
    assert det["llm"]["errores"] == ["sin proveedor de LLM configurado"]


def test_triage_error_de_proveedor_no_reintenta():
    llm = LLMFalso([ErrorLLM("HTTP 503")])
    salida, det = triage(TEXTO, llm)
    assert salida.valido is False and det["llm"]["intentos"] == 1


def test_triage_no_manda_datos_personales_al_llm():
    llm = LLMFalso([json.dumps({"resumen": "Sin agua.", "categoria": "sin_agua"})])
    triage(TEXTO + " Mi cel es 4421234567 y mi correo ana@x.mx", llm)
    assert "4421234567" not in llm.llamadas[0] and "ana@x.mx" not in llm.llamadas[0]


@pytest.mark.parametrize("malo", ["", "   ", "hola", "x" * 2001])
def test_triage_rechaza_entradas_invalidas(malo):
    with pytest.raises(ValidationError):
        triage(malo, None)
