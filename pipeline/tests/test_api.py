"""Pruebas de T-10 (api/index.py). Sin red: Supabase y el LLM se simulan o se desactivan."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from api import index  # noqa: E402
from api._lib import dependencias, salud  # noqa: E402
from api._lib.errores import mensaje_validacion  # noqa: E402

VARIABLES = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
             "LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "EMBEDDINGS_MODEL", "EMBEDDINGS_DIM", "GROQ_API_KEY", "GROQ_MODEL")


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for v in VARIABLES:
        monkeypatch.delenv(v, raising=False)
    dependencias.limpiar_cache()
    yield
    dependencias.limpiar_cache()


@pytest.fixture
def cliente():
    return TestClient(index.app, raise_server_exceptions=False)


def _es_error(r, http, codigo):
    assert r.status_code == http, r.text
    cuerpo = r.json()
    assert set(cuerpo) == {"error"} and set(cuerpo["error"]) == {"codigo", "mensaje"}
    assert cuerpo["error"]["codigo"] == codigo
    return cuerpo["error"]["mensaje"]


# ------------------------------------------------------------------ salud
def test_salud_sin_configuracion_responde_200_y_falso(cliente):
    r = cliente.get("/api/salud")
    assert r.status_code == 200
    assert r.json() == {"ok": False, "supabase": False, "llm": False, "version": "v1"}


def test_salud_lee_resultados_vigentes_con_cabecera_de_esquema(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ejemplo.supabase.co")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "llave-de-prueba")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "x")
    vistas = []

    def responder(req: httpx.Request):
        vistas.append(req)
        return httpx.Response(200, json=[{"modulo": "eda"}])

    r = salud.revisar_salud(httpx.Client(transport=httpx.MockTransport(responder)))
    assert r == {"ok": True, "supabase": True, "llm": True, "version": "v1"}
    req = vistas[0]
    assert req.url.path == "/rest/v1/resultados_vigentes"
    assert req.headers["Accept-Profile"] == "analitica"


@pytest.mark.parametrize("respuesta", [httpx.Response(401, json={"message": "no"}), httpx.Response(200, json={"x": 1})])
def test_salud_http_o_negocio_fallido_es_falso(monkeypatch, respuesta):
    monkeypatch.setenv("SUPABASE_URL", "https://ejemplo.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "llave")
    http = httpx.Client(transport=httpx.MockTransport(lambda _: respuesta))
    assert salud.supabase_responde(http) is False


def test_salud_timeout_es_falso(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://ejemplo.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "llave")

    def caer(_):
        raise httpx.ConnectTimeout("sin red")

    assert salud.supabase_responde(httpx.Client(transport=httpx.MockTransport(caer))) is False


# ------------------------------------------------------------------ errores
def test_ruta_inexistente_404_en_espanol(cliente):
    msg = _es_error(cliente.get("/api/no-existe"), 404, "no_encontrado")
    assert "no existe" in msg


def test_metodo_incorrecto_405(cliente):
    _es_error(cliente.get("/api/triage"), 405, "metodo_no_permitido")


def test_json_mal_formado_422(cliente):
    _es_error(cliente.post("/api/triage", content="{no-json", headers={"content-type": "application/json"}),
              422, "entrada_invalida")


def test_mensaje_validacion_no_expone_valores():
    m = mensaje_validacion([{"loc": ("body", "texto"), "type": "string_too_short", "input": "secreto@correo.mx"}])
    assert "texto" in m and "secreto" not in m


# ------------------------------------------------------------------ triage
def test_triage_sin_llm_devuelve_contrato_y_no_valido(cliente):
    r = cliente.post("/api/triage", json={"texto": "Hay una fuga de agua en la calle desde ayer y se está desperdiciando"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == {"resumen", "categoria", "prioridad", "valido"}
    assert 0 <= d["prioridad"] <= 3
    assert d["valido"] is False  # sin proveedor configurado nunca se marca como válido
    assert d["resumen"]


def test_triage_texto_corto_422(cliente):
    _es_error(cliente.post("/api/triage", json={"texto": "ab"}), 422, "entrada_invalida")


def test_triage_sin_campo_422(cliente):
    msg = _es_error(cliente.post("/api/triage", json={}), 422, "entrada_invalida")
    assert "texto" in msg


# ------------------------------------------------------------------ rag
def test_rag_sin_embeddings_503_claro(cliente):
    msg = _es_error(cliente.post("/api/rag", json={"pregunta": "¿Cuánto cuesta el m3 doméstico?"}), 503, "rag_no_configurado")
    assert "EMBEDDINGS_MODEL" in msg


def test_rag_k_fuera_de_rango_422(cliente):
    _es_error(cliente.post("/api/rag", json={"pregunta": "tarifa doméstica", "k": 50}), 422, "entrada_invalida")


def test_rag_sin_evidencia_no_llama_al_llm(cliente, monkeypatch):
    class EmbFalso:
        def embeber(self, textos):
            return [[0.1] * 768 for _ in textos]

    class LlmQueNoDebeUsarse:
        nombre = "falso"

        def generar_json(self, *_):
            raise AssertionError("no debe llamarse sin evidencia")

    monkeypatch.setattr(dependencias, "cliente_embeddings", lambda: EmbFalso())
    monkeypatch.setattr(dependencias, "cliente_supabase", lambda: object())
    monkeypatch.setattr(dependencias, "cliente_llm", lambda: LlmQueNoDebeUsarse())
    import api._lib.rag as rag
    monkeypatch.setattr(rag, "buscar_en_supabase", lambda _: (lambda v, k: [
        {"fragmento_id": "f1", "documento_id": "d1", "titulo": "Otro tema", "contenido": "x", "similitud": 0.2}]))
    r = cliente.post("/api/rag", json={"pregunta": "¿Quién ganó el mundial?", "k": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["evidencia"] is False and d["fuentes"] == []


def test_rag_falla_de_red_502_sin_detalle(cliente, monkeypatch):
    class EmbQueFalla:
        def embeber(self, textos):
            raise httpx.ConnectError("sin red")

    monkeypatch.setattr(dependencias, "cliente_embeddings", lambda: EmbQueFalla())
    monkeypatch.setattr(dependencias, "cliente_supabase", lambda: object())
    msg = _es_error(cliente.post("/api/rag", json={"pregunta": "tarifa doméstica"}), 502, "rag_no_disponible")
    assert "ConnectError" not in msg


# ------------------------------------------------------------------ importe
def test_importe_coincide_con_tarifas(cliente):
    from api._lib.tarifas import calcular_importe

    r = cliente.get("/api/importe", params={"tipo_tarifa": "domestico_medio", "consumo_m3": 18,
                                            "alcantarillado": "true", "saneamiento": "true"})
    assert r.status_code == 200, r.text
    esperado = calcular_importe("domestico_medio", 18, True, True)
    assert r.json()["total"] == esperado["total"]
    assert {"consumo_facturado", "agua", "alcantarillado", "saneamiento", "iva", "total"} <= set(r.json())


def test_importe_tarifa_inexistente_422(cliente):
    msg = _es_error(cliente.get("/api/importe", params={"tipo_tarifa": "lunar", "consumo_m3": 5}), 422, "entrada_invalida")
    assert "lunar" in msg


def test_importe_consumo_negativo_422(cliente):
    _es_error(cliente.get("/api/importe", params={"tipo_tarifa": "comercial", "consumo_m3": -1}), 422, "entrada_invalida")
