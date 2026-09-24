"""Limpieza y tokenización de quejas (bloque J).

Funciones puras, sin red. Se usan igual en el entrenamiento (pipeline) y,
si se porta, en la API: la misma limpieza en ambos lados evita el sesgo
entre entrenamiento y uso.
"""
from __future__ import annotations

import re
import unicodedata

# Palabras vacías del español. Lista corta y explícita (sklearn no trae una en
# español). Se conservan a propósito negaciones y palabras de intensidad
# ("no", "sin", "nada", "muy", "poca") porque cambian el sentido de una queja:
# "sin agua" y "con agua" no son lo mismo.
PALABRAS_VACIAS = frozenset(
    """
    a al algo algunas algunos ante antes aqui asi aun cada como con contra cual
    cuando de del desde donde dos e el ella ellas ellos en entre era eran es esa
    esas ese eso esos esta estaba estan estas este esto estos fue fueron ha han
    hasta hay he la las le les lo los me mi mis nos nuestra nuestro o os para pero
    por porque que se ser si sobre su sus te tambien tengo tiene tienen todo todos
    tu tus un una unas uno unos y ya yo
    """.split()
)

_NO_ALFANUMERICO = re.compile(r"[^a-z0-9ñ\s]")
_ESPACIOS = re.compile(r"\s+")


def quitar_acentos(texto: str) -> str:
    """Quita acentos pero conserva la ñ (no es un acento: es otra letra)."""
    texto = texto.replace("ñ", "\0")
    sin = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sin.replace("\0", "ñ")


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin acentos, sin puntuación y con espacios simples.

    `None` o texto vacío devuelven "" (nunca "None" ni "nan").
    """
    if texto is None:
        return ""
    texto = str(texto)
    if texto.strip().lower() in {"", "nan"}:
        return ""
    texto = quitar_acentos(texto.lower())
    texto = _NO_ALFANUMERICO.sub(" ", texto)
    return _ESPACIOS.sub(" ", texto).strip()


def tokenizar(texto: str | None) -> list[str]:
    """Normaliza y separa en palabras, sin palabras vacías ni tokens de 1 letra."""
    return [t for t in normalizar(texto).split() if len(t) > 1 and t not in PALABRAS_VACIAS]
