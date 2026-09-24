"""Corpus del RAG (bloque M): documentos + fragmentación.

Solo entran documentos que existen de verdad (nada redactado "para el RAG"):
1. Tarifario CEA (api/_lib/tarifas_cea.csv, T-03): un documento por tipo de tarifa
   del periodo vigente, convertido a texto desde la tabla.
2. Reglas de cálculo del recibo: la documentación de api/_lib/tarifas.py (T-03),
   portada de Odoo de Operaguas.
3. Diccionario de la simulación: data/simulados/LEEME.txt y data/README.md.
4. Documentos externos o de Operaguas en pipeline/src/rag/documentos/*.md, con
   cabecera `titulo/tipo/fuente/url`. PENDIENTES: NOM-127-SSA1-2021, contrato tipo y
   preguntas frecuentes del portal (los aporta Andrés; sin datos personales).

Chunking: por párrafos, hasta TAMANO caracteres con SOLAPE de contexto, para que
cada fragmento se entienda solo y quepa varias veces en el prompt.
"""
from __future__ import annotations

import ast
import csv
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.src.config import RAIZ

TAMANO = 900
SOLAPE = 150
ESPACIO_UUID = uuid.UUID("5f2d7c0e-3a1b-4c55-9d0e-6f7a8b9c0d1e")  # fijo: IDs deterministas
DIR_DOCUMENTOS = Path(__file__).with_name("documentos")
TIPOS = {"tarifa", "regla", "norma", "contrato", "faq", "datos"}
NOMBRES_TARIFA = {
    "domestico_apoyo": "Doméstica de apoyo", "domestico_economico": "Doméstica económica",
    "domestico_medio": "Doméstica media", "domestico_alto": "Doméstica alta",
    "domestico_rural": "Doméstica rural", "comercial": "Comercial", "industrial": "Industrial",
    "publico_oficial": "Pública u oficial", "beneficencia": "Beneficencia",
}


@dataclass
class Documento:
    titulo: str
    tipo: str
    fuente: str
    texto: str
    url: str | None = None
    fragmentos: list[str] = field(default_factory=list)

    @property
    def documento_id(self) -> str:
        return str(uuid.uuid5(ESPACIO_UUID, f"{self.fuente}::{self.titulo}"))

    def fragmento_id(self, orden: int) -> str:
        return str(uuid.uuid5(ESPACIO_UUID, f"{self.documento_id}::{orden}"))


# ── fragmentación ───────────────────────────────────────────────────────────────

def fragmentar(texto: str, tamano: int = TAMANO, solape: int = SOLAPE) -> list[str]:
    """Agrupa párrafos hasta `tamano`; un párrafo más largo se corta por oraciones.

    Cada fragmento nuevo arranca con la cola (≤ `solape` caracteres) del anterior.
    """
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    piezas: list[str] = []
    for p in parrafos:
        if len(p) <= tamano:
            piezas.append(p)
        else:
            actual = ""
            for oracion in re.split(r"(?<=[.;:])\s+|\n", p):
                if actual and len(actual) + len(oracion) + 1 > tamano:
                    piezas.append(actual)
                    actual = ""
                actual = f"{actual} {oracion}".strip()
            if actual:
                piezas.append(actual)
    fragmentos: list[str] = []
    actual = ""
    for pieza in piezas:
        if actual and len(actual) + len(pieza) + 2 > tamano:
            fragmentos.append(actual)
            cola = actual[-solape:]
            cola = cola[cola.find(" ") + 1:] if " " in cola else cola
            actual = f"{cola}\n\n{pieza}" if solape else pieza
        else:
            actual = f"{actual}\n\n{pieza}" if actual else pieza
    if actual:
        fragmentos.append(actual)
    return fragmentos


# ── fuentes ─────────────────────────────────────────────────────────────────────

def documentos_tarifario(ruta: Path | None = None, periodo: str = "2026-T3") -> list[Documento]:
    ruta = ruta or RAIZ / "api" / "_lib" / "tarifas_cea.csv"
    if not ruta.exists():
        return []
    tabla: dict[str, list[tuple[int, float]]] = {}
    with ruta.open(encoding="utf-8") as fh:
        for f in csv.DictReader(fh):
            if f["periodo"] == periodo:
                tabla.setdefault(f["tipo_tarifa"], []).append((int(f["consumo_m3"]), float(f["importe_agua"])))
    docs = []
    for tipo, filas in sorted(tabla.items()):
        filas.sort()
        nombre = NOMBRES_TARIFA.get(tipo, tipo)
        bloques = []
        for i in range(0, len(filas), 10):
            tramo = filas[i:i + 10]
            valores = "; ".join(f"{m} m³ = ${v:,.2f}" for m, v in tramo)
            bloques.append(
                f"Tarifa {nombre} ({tipo}), periodo {periodo}, importe de agua potable antes de "
                f"alcantarillado, saneamiento e IVA, de {tramo[0][0]} a {tramo[-1][0]} m³: {valores}."
            )
        maximo = filas[-1][0]
        bloques.append(f"Si el consumo de la tarifa {nombre} supera {maximo} m³ se cobra el importe de {maximo} m³ "
                       f"(${filas[-1][1]:,.2f}), según api/_lib/tarifas.py.")
        docs.append(Documento(f"Tarifario CEA {periodo}: {nombre}", "tarifa", "api/_lib/tarifas_cea.csv",
                              "\n\n".join(bloques)))
    return docs


def documento_reglas(ruta: Path | None = None) -> list[Documento]:
    ruta = ruta or RAIZ / "api" / "_lib" / "tarifas.py"
    if not ruta.exists():
        return []
    texto = ast.get_docstring(ast.parse(ruta.read_text(encoding="utf-8"))) or ""
    return [Documento("Reglas de cálculo del recibo de agua", "regla", "api/_lib/tarifas.py", texto)] if texto else []


def documentos_datos() -> list[Documento]:
    docs = []
    for rel, titulo in [("data/simulados/LEEME.txt", "Descripción de los datos simulados"),
                        ("data/README.md", "Reglas de uso de los datos simulados")]:
        ruta = RAIZ / rel
        if ruta.exists():
            docs.append(Documento(titulo, "datos", rel, ruta.read_text(encoding="utf-8")))
    return docs


def documentos_externos(directorio: Path = DIR_DOCUMENTOS) -> list[Documento]:
    """Lee .md con cabecera 'clave: valor' hasta la primera línea '---'."""
    docs = []
    for ruta in sorted(directorio.glob("*.md")):
        cabecera, _, cuerpo = ruta.read_text(encoding="utf-8").partition("\n---\n")
        meta = dict(l.split(":", 1) for l in cabecera.splitlines() if ":" in l)
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        faltan = {"titulo", "tipo", "fuente"} - meta.keys()
        if faltan or meta["tipo"] not in TIPOS:
            raise ValueError(f"{ruta.name}: cabecera incompleta o tipo inválido ({sorted(faltan)})")
        docs.append(Documento(meta["titulo"], meta["tipo"], meta["fuente"], cuerpo.strip(), meta.get("url") or None))
    return docs


def construir_corpus() -> list[Documento]:
    docs = documentos_tarifario() + documento_reglas() + documentos_datos() + documentos_externos()
    for d in docs:
        d.fragmentos = fragmentar(d.texto)
    return [d for d in docs if d.fragmentos]
