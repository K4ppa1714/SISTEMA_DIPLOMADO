"""Pruebas de T-15 (agente). Sin red: LLM guionizado y datos falsos."""
import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from api import index  # noqa: E402
from api._lib import dependencias  # noqa: E402
from api._lib.agente.agente import MAX_PASOS, ejecutar_agente  # noqa: E402
from api._lib.agente.herramientas import HERRAMIENTAS, Contexto  # noqa: E402
from api._lib.llm import ErrorLLM  # noqa: E402
from api._lib.tarifas import calcular_importe  # noqa: E402


class DatosFalsos:
    def recibos(self, id_toma, n):
        if id_toma != "T95A557D58C":
            return []
        return [{"periodo": "2026-09", "fecha_vencimiento": "2026-09-20", "total_pagar": 700.5, "pagado": False, "pago_tardio": None},
                {"periodo": "2026-08", "fecha_vencimiento": "2026-08-20", "total_pagar": 650.0, "pagado": True, "pago_tardio": True}]

    def predicciones(self, id_toma, periodo):
        filas = [{"periodo": "2026-08", "prob_pago_tardio": 0.9088, "clase_predicha": True, "modelo": "regresion_logistica", "version": "v1"},
                 {"periodo": "2026-09", "prob_pago_tardio": 0.9021, "clase_predicha": True, "modelo": "regresion_logistica", "version": "v1"}]
        if id_toma != "T95A557D58C":
            return []
        return [f for f in filas if periodo in (None, f["periodo"])]

    def resultados(self, modulo):
        return [{"clave": "espectro", "payload": {"titulo": "Espectro", "conclusion": "El ciclo de 24 h domina."}}] if modulo == "fourier" else []


class LlmGuion:
    """Devuelve las decisiones en orden; registra lo que recibió."""
    nombre = "guion"

    def __init__(self, decisiones):
        self.decisiones, self.recibidos = list(decisiones), []

    def generar_json(self, sistema, usuario):
        self.recibidos.append(usuario)
        d = self.decisiones.pop(0)
        if isinstance(d, Exception):
            raise d
        return d if isinstance(d, str) else json.dumps(d)


def ctx():
    return Contexto(datos=DatosFalsos(), buscar_documentos=lambda p, k: {"respuesta": "10 % del agua", "evidencia": True, "fuentes": []})


def herr(nombre, **args):
    return {"accion": "herramienta", "herramienta": nombre, "argumentos": args}


def resp(texto):
    return {"accion": "responder", "respuesta": texto}


def test_catalogo_tiene_las_cinco_herramientas_del_contrato():
    assert set(HERRAMIENTAS) == {"estado_cuenta", "calcular_importe", "predecir_pago", "buscar_documentos", "analizar_serie"}
    for h in HERRAMIENTAS.values():
        e = h.esquema()
        assert e["descripcion"] and isinstance(e["argumentos"], dict)


def test_tarea_multipaso_usa_dos_herramientas_y_registra():
    llm = LlmGuion([herr("estado_cuenta", id_toma="T95A557D58C"), herr("predecir_pago", id_toma="T95A557D58C", periodo="2026-09"),
                    resp("Debe 700.50 y tiene 90 % de probabilidad de pagar tarde.")])
    bitacora = []
    s, d = ejecutar_agente("¿Cuánto debe la toma T95A557D58C y pagará a tiempo en 2026-09?", None, llm, ctx(), bitacora.append)
    assert [p.herramienta for p in s.pasos] == ["estado_cuenta", "predecir_pago"]
    assert s.pasos[0].resultado["adeudo_total"] == 700.5
    assert s.pasos[1].resultado["predicciones"][0]["prob_pago_tardio"] == 0.9021
    assert [b["paso"] for b in bitacora] == [1, 2] and all(b["error"] is None for b in bitacora)
    assert "PASO 1: estado_cuenta" in llm.recibidos[1]  # la observación vuelve al LLM
    assert isinstance(s.sesion, uuid.UUID)


def test_calcular_importe_coincide_con_tarifas():
    llm = LlmGuion([herr("calcular_importe", tipo_tarifa="domestico medio", consumo_m3=15, alcantarillado=True, saneamiento=True), resp("ok")])
    s, _ = ejecutar_agente("¿Cuánto paga una casa de tarifa media con 15 m3?", None, llm, ctx())
    assert s.pasos[0].resultado["total"] == calcular_importe("domestico_medio", 15, True, True)["total"]


def test_argumentos_invalidos_vuelven_como_observacion_y_se_corrigen():
    llm = LlmGuion([herr("calcular_importe", tipo_tarifa="lunar", consumo_m3=10),
                    herr("calcular_importe", tipo_tarifa="comercial", consumo_m3=10), resp("listo")])
    bitacora = []
    s, d = ejecutar_agente("importe comercial 10 m3", None, llm, ctx(), bitacora.append)
    assert "error" in s.pasos[0].resultado and "total" in s.pasos[1].resultado
    assert d["errores_herramienta"] == 1 and bitacora[0]["error"] == "argumentos inválidos" and bitacora[0]["resultado"] is None


def test_herramienta_inexistente_y_json_invalido_cuentan_como_decisiones_invalidas():
    llm = LlmGuion(["esto no es json", herr("borrar_todo"), resp("No puedo hacer eso.")])
    s, d = ejecutar_agente("borra la base", None, llm, ctx())
    assert d["decisiones_invalidas"] == 2 and s.respuesta == "No puedo hacer eso."


def test_dato_inexistente_no_rompe():
    llm = LlmGuion([herr("estado_cuenta", id_toma="TNOEXISTE01"), resp("No encontré recibos de esa toma.")])
    s, d = ejecutar_agente("estado de cuenta de TNOEXISTE01", None, llm, ctx())
    assert "No hay recibos" in s.pasos[0].resultado["error"] and d["errores_herramienta"] == 1


def test_limite_de_pasos():
    llm = LlmGuion([herr("analizar_serie", analisis="fourier")] * (MAX_PASOS + 2))
    s, d = ejecutar_agente("analiza la serie una y otra vez", None, llm, ctx())
    assert len(s.pasos) == MAX_PASOS and d["limite_alcanzado"] and "límite" in s.respuesta


def test_falla_del_llm_devuelve_respuesta_clara():
    s, d = ejecutar_agente("hola agente", None, LlmGuion([ErrorLLM("HTTP 429")]), ctx())
    assert "No pude consultar" in s.respuesta and s.pasos == []


def test_sin_llm():
    s, _ = ejecutar_agente("hola agente", None, None, ctx())
    assert "falta configurar el LLM" in s.respuesta


def test_datos_personales_no_llegan_al_llm():
    llm = LlmGuion([resp("ok")])
    ejecutar_agente("mi correo es ana@ejemplo.com y mi teléfono 4421234567", None, llm, ctx())
    assert "ana@ejemplo.com" not in llm.recibidos[0] and "4421234567" not in llm.recibidos[0]


def test_ruta_api_agente_sin_supabase_503(monkeypatch):
    for v in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(v, raising=False)
    dependencias.limpiar_cache()
    r = TestClient(index.app, raise_server_exceptions=False).post("/api/agente", json={"mensaje": "hola agente"})
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "supabase_no_configurado"


def test_ruta_api_agente_contrato(monkeypatch):
    import api._lib.agente.herramientas as h
    monkeypatch.setattr(dependencias, "cliente_supabase", lambda: object())
    monkeypatch.setattr(dependencias, "cliente_embeddings", lambda: None)
    monkeypatch.setattr(dependencias, "cliente_llm", lambda: LlmGuion([herr("predecir_pago", id_toma="T95A557D58C"), resp("Riesgo alto.")]))
    monkeypatch.setattr(h, "DatosSupabase", lambda _: DatosFalsos())
    import api._lib.agente.agente as ag
    monkeypatch.setattr(ag, "registrador_supabase", lambda _: (lambda fila: None))
    r = TestClient(index.app).post("/api/agente", json={"mensaje": "¿La toma T95A557D58C pagará tarde?"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == {"respuesta", "pasos", "sesion"} and d["pasos"][0]["herramienta"] == "predecir_pago"
    assert set(d["pasos"][0]) == {"herramienta", "argumentos", "resultado", "ms"}


@pytest.mark.parametrize("cuerpo", [{"mensaje": "ab"}, {"mensaje": "hola", "sesion": "no-es-uuid"}, {}])
def test_ruta_api_agente_entrada_invalida(cuerpo):
    r = TestClient(index.app).post("/api/agente", json=cuerpo)
    assert r.status_code == 422 and r.json()["error"]["codigo"] == "entrada_invalida"


# ------------------------------------------------------------------ evaluación (T-16)
def test_evaluador_calcula_tsa_y_exito_con_api_simulada():
    import httpx
    from pipeline.src.agents.evaluar import cargar_casos, evaluar, payloads

    casos = cargar_casos(incluir_sin_validar=True)
    assert len(casos) == 30 and sum(c["multipaso"] for c in casos) == 10

    def api(req):
        consulta = json.loads(req.content)["mensaje"]
        caso = next(c for c in casos if c["consulta"] == consulta)
        usadas = caso["esperadas"] if "T95A557D58C" in consulta else ["calcular_importe"]
        return httpx.Response(200, json={"respuesta": "ok", "sesion": str(uuid.uuid4()),
                                         "pasos": [{"herramienta": u, "argumentos": {}, "resultado": {}, "ms": 1} for u in usadas]})

    filas = evaluar("https://x", casos, pausa_s=0, http=httpx.Client(transport=httpx.MockTransport(api)))
    esperados = sum(1 for c in casos if "T95A557D58C" in c["consulta"] or set(c["esperadas"]) == {"calcular_importe"})
    p = payloads(filas, True)
    tsa = p[0]["payload"]["filas"][1]["valor"]
    assert tsa == round(esperados / 30, 4)
    assert "EXPLORATORIO" in p[0]["payload"]["titulo"]


def test_sin_casos_validados_no_se_calcula():
    from pipeline.src.agents.evaluar import cargar_casos
    assert cargar_casos() == []  # el borrador aún no tiene validado_por
