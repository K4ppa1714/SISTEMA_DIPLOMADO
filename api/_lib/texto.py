"""Normalización y tokenización para la API (copia exacta de pipeline/src/nlp/texto.py).

Se duplica porque Vercel no empaqueta pipeline/ (.vercelignore). Una prueba
(pipeline/tests/test_triage.py) verifica que ambas versiones den lo mismo
sobre todas las quejas; si alguien cambia una sin la otra, la prueba falla.
"""
from __future__ import annotations

import re
import unicodedata

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
    texto = texto.replace("ñ", "\0")
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin.replace("\0", "ñ")


def normalizar(texto: str | None) -> str:
    if texto is None:
        return ""
    texto = str(texto)
    if texto.strip().lower() in {"", "nan"}:
        return ""
    texto = quitar_acentos(texto.lower())
    texto = _NO_ALFANUMERICO.sub(" ", texto)
    return _ESPACIOS.sub(" ", texto).strip()


def tokenizar(texto: str | None) -> list[str]:
    return [t for t in normalizar(texto).split() if len(t) > 1 and t not in PALABRAS_VACIAS]
