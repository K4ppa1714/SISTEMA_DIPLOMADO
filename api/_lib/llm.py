"""Capa de proveedor de LLM por HTTP (httpx), sin SDKs pesados.

Proveedores (decisión #49, pendiente de registro D-11 por Emilio):
- gemini: REST `models.generateContent`
  (https://ai.google.dev/api/generate-content). Cabecera `x-goog-api-key`,
  `generationConfig.responseMimeType = "application/json"`, texto en
  `candidates[0].content.parts[0].text`.
- groq (respaldo): API compatible con OpenAI
  (https://console.groq.com/docs/structured-outputs). `Authorization: Bearer`,
  `response_format = {"type": "json_object"}`.

Variables de entorno (nunca en el repo): LLM_PROVIDER, LLM_MODEL, LLM_API_KEY,
GROQ_API_KEY, GROQ_MODEL. El modelo no se fija en código: sale de LLM_MODEL.

Éxito HTTP ≠ éxito de negocio: un 200 sin texto o con bloqueo de seguridad
se trata como error (ErrorLLM), igual que un 4xx/5xx o un timeout.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

TIMEOUT_S = 20.0
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"


class ErrorLLM(Exception):
    """Falla del proveedor: red, HTTP, respuesta vacía o bloqueada. El mensaje no incluye la llave."""


@dataclass
class ClienteGemini:
    api_key: str
    modelo: str
    http: httpx.Client | None = None
    nombre: str = "gemini"

    def generar_json(self, sistema: str, usuario: str) -> str:
        cuerpo = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": usuario}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        datos = _post(self.http, URL_GEMINI.format(modelo=self.modelo), cuerpo, {"x-goog-api-key": self.api_key})
        try:
            return datos["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            motivo = (datos.get("promptFeedback") or {}).get("blockReason") if isinstance(datos, dict) else None
            raise ErrorLLM(f"gemini: respuesta sin texto{f' (bloqueo: {motivo})' if motivo else ''}") from None


@dataclass
class ClienteGroq:
    api_key: str
    modelo: str
    http: httpx.Client | None = None
    nombre: str = "groq"

    def generar_json(self, sistema: str, usuario: str) -> str:
        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        datos = _post(self.http, URL_GROQ, cuerpo, {"Authorization": f"Bearer {self.api_key}"})
        try:
            texto = datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ErrorLLM("groq: respuesta sin texto") from None
        if not texto:
            raise ErrorLLM("groq: respuesta vacía")
        return texto


@dataclass
class ClienteConRespaldo:
    """Intenta el principal; si falla con ErrorLLM, usa el respaldo. Registra cuál respondió."""
    principal: object
    respaldo: object | None = None
    ultimo: str = ""

    @property
    def nombre(self) -> str:
        return self.ultimo or getattr(self.principal, "nombre", "llm")

    def generar_json(self, sistema: str, usuario: str) -> str:
        try:
            texto = self.principal.generar_json(sistema, usuario)
            self.ultimo = self.principal.nombre
            return texto
        except ErrorLLM:
            if self.respaldo is None:
                raise
            texto = self.respaldo.generar_json(sistema, usuario)
            self.ultimo = self.respaldo.nombre
            return texto


def _post(http: httpx.Client | None, url: str, cuerpo: dict, cabeceras: dict) -> dict:
    cliente = http or httpx.Client(timeout=TIMEOUT_S)
    try:
        r = cliente.post(url, json=cuerpo, headers=cabeceras, timeout=TIMEOUT_S)
    except httpx.TimeoutException:
        raise ErrorLLM("tiempo de espera agotado con el proveedor de LLM") from None
    except httpx.HTTPError as exc:
        raise ErrorLLM(f"error de red con el proveedor de LLM: {type(exc).__name__}") from None
    finally:
        if http is None:
            cliente.close()
    if r.status_code != 200:
        raise ErrorLLM(f"el proveedor de LLM respondió HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise ErrorLLM("el proveedor de LLM no devolvió JSON") from None


def crear_cliente(entorno: dict | None = None, http: httpx.Client | None = None):
    """Construye el cliente desde variables de entorno. Devuelve None si falta configuración."""
    env = os.environ if entorno is None else entorno
    proveedor = (env.get("LLM_PROVIDER") or "").strip().lower()
    llave, modelo = env.get("LLM_API_KEY"), env.get("LLM_MODEL")
    principal = None
    if llave and modelo:
        if proveedor == "gemini":
            principal = ClienteGemini(llave, modelo, http)
        elif proveedor == "groq":
            principal = ClienteGroq(llave, modelo, http)
    respaldo = None
    if proveedor != "groq" and env.get("GROQ_API_KEY") and env.get("GROQ_MODEL"):
        respaldo = ClienteGroq(env["GROQ_API_KEY"], env["GROQ_MODEL"], http)
    if principal is None:
        return respaldo  # puede ser None: el triage funciona sin LLM y lo marca como no válido
    return ClienteConRespaldo(principal, respaldo)
