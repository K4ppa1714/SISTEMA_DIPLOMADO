"""Formato único de error de la API (CONTRATOS §3): {"error": {"codigo", "mensaje"}} en español."""
from __future__ import annotations


class ErrorApi(Exception):
    """Error de negocio con código HTTP, código corto y mensaje para el usuario."""

    def __init__(self, http: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.http, self.codigo, self.mensaje = http, codigo, mensaje


def cuerpo_error(codigo: str, mensaje: str) -> dict:
    return {"error": {"codigo": codigo, "mensaje": mensaje}}


_TRADUCCIONES = {
    "missing": "es obligatorio",
    "string_too_short": "es demasiado corto",
    "string_too_long": "es demasiado largo",
    "string_type": "debe ser texto",
    "int_parsing": "debe ser un número entero",
    "int_type": "debe ser un número entero",
    "float_parsing": "debe ser un número",
    "bool_parsing": "debe ser true o false",
    "greater_than_equal": "es menor que el mínimo permitido",
    "less_than_equal": "es mayor que el máximo permitido",
    "json_invalid": "no es JSON válido",
    "model_attributes_type": "debe ser un objeto JSON",
    "dict_type": "debe ser un objeto JSON",
}


def mensaje_validacion(errores: list[dict]) -> str:
    """Convierte los errores de Pydantic en una frase en español (sin exponer valores recibidos)."""
    partes = []
    for e in errores[:3]:
        campo = ".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "query")) or "cuerpo"
        tipo = e.get("type", "")
        if tipo == "value_error":
            # Mensajes propios de los validadores (ya en español): "Value error, <mensaje>".
            texto = str(e.get("msg", "")).removeprefix("Value error, ")
        else:
            texto = _TRADUCCIONES.get(tipo, "no es válido")
        partes.append(f"«{campo}» {texto}")
    return "Revisa los datos enviados: " + "; ".join(partes) + "."
