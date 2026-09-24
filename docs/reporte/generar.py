"""Genera el reporte técnico (T-20) a partir de docs/reporte/plantilla.md.

Marcadores de la plantilla:
  {{c:modulo/clave}}  conclusión del payload
  {{t:modulo/clave}}  tabla (filas) del payload + conclusión
  {{f:modulo/clave}}  figura PNG del payload (docs/reporte/figuras/) + conclusión
  {{var:nombre}}      texto calculado aquí (features, trazabilidad, URL, etc.)

Fuente de los resultados, en este orden:
  1. Supabase (analitica.resultados_vigentes) si hay SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY;
  2. los JSON de pipeline/artefactos/resultados/*.json.
Ningún número se escribe a mano: todos salen de los payloads.

Uso:
    python docs/reporte/generar.py            # escribe reporte_tecnico.md y reporte_tecnico.html
PDF: abrir el HTML en Chrome e imprimir, o
    chrome --headless --print-to-pdf=docs/reporte/reporte_tecnico.pdf docs/reporte/reporte_tecnico.html
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ))

FIGURAS = AQUI / "figuras"
URL_APP = os.environ.get("URL_APP", "(pendiente de despliegue)")


def cargar_resultados() -> dict[str, dict]:
    url, llave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    res: dict[str, dict] = {}
    if url and llave:
        from supabase import create_client

        filas = (create_client(url, llave).schema("analitica").table("resultados_vigentes")
                 .select("modulo,clave,payload,version").execute().data)
        for f in filas:
            res[f"{f['modulo']}/{f['clave']}"] = f["payload"]
        print(f"{len(res)} resultados desde Supabase")
        return res
    rutas = sorted((RAIZ / "pipeline" / "artefactos" / "resultados").glob("*.json"))
    rutas.append(RAIZ / "pipeline" / "artefactos" / "nlp_resultados.json")  # T-14 guarda aquí nlp y embeddings
    for ruta in [r for r in rutas if r.exists()]:
        for f in json.loads(ruta.read_text(encoding="utf-8")):
            res[f"{f['modulo']}/{f['clave']}"] = f["payload"]
    print(f"{len(res)} resultados desde JSON locales (sin credenciales de Supabase)")
    return res


def tabla_md(filas: list[dict]) -> str:
    if not filas:
        return ""
    cols = list(dict.fromkeys(k for f in filas for k in f))
    fmt = lambda v: f"{v:.4g}" if isinstance(v, float) else ("" if v is None else str(v))
    lineas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lineas += ["| " + " | ".join(fmt(f.get(c)) for c in cols) + " |" for f in filas]
    return "\n".join(lineas)


def figura(clave: str, payload: dict) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from pipeline.notebooks import graficas

    FIGURAS.mkdir(exist_ok=True)
    nombre = clave.replace("/", "__") + ".png"
    plt.show = lambda: (plt.savefig(FIGURAS / nombre, dpi=130, bbox_inches="tight"), plt.close("all"))
    # En el reporte la conclusión va como pie de figura; dibujada dentro se encima con las etiquetas del eje.
    original, graficas._conclusion = graficas._conclusion, lambda fig, p: None
    try:
        graficas.dibujar(payload)
    finally:
        graficas._conclusion = original
    return f"![{payload['titulo']}](figuras/{nombre})"


def _trazabilidad() -> str:
    """Tabla de docs/trazabilidad.md (bloque → código → notebook → resultado → página → métrica)."""
    texto = (RAIZ / "docs" / "trazabilidad.md").read_text(encoding="utf-8")
    return texto[texto.find("| Bloque"):].strip()


def variables() -> dict[str, str]:
    from pipeline.src.features.variables import JUSTIFICACION

    features = tabla_md([{"variable": k, "justificación": v} for k, v in JUSTIFICACION.items()])
    tareas = (RAIZ / "docs" / "TAREAS.md").read_text(encoding="utf-8")
    bloque = tareas[tareas.find("## Bloque → tarea"):]
    return {
        "url_app": URL_APP,
        "diagrama": "![Arquitectura](../capturas/arquitectura.png)\n\nFuente del diagrama: `docs/arquitectura.md` (mermaid).",
        "tabla_features": features,
        "trazabilidad": _trazabilidad(),
        "pendiente_T08": "PENDIENTE: resultados de T-08 (Claude-A).",
        "pendiente_T12": "PENDIENTE: métricas del triage (formato válido %, acuerdo LLM/modelo) de T-16.",
        "pendiente_T11_T16": "PENDIENTE: índice RAG y Recall@k/MRR de T-16.",
        "pendiente_T15": "PENDIENTE: agente (T-15) y su evaluación (T-16).",
    }


def generar() -> Path:
    res = cargar_resultados()
    vars_ = variables()
    faltan: list[str] = []

    def reemplazar(m: re.Match) -> str:
        tipo, ref = m.group(1), m.group(2)
        if tipo == "var":
            return vars_.get(ref, f"⚠ variable {ref}")
        p = res.get(ref)
        if p is None:
            faltan.append(ref)
            return f"⚠ PENDIENTE: `{ref}`"
        if tipo == "c":
            return p["conclusion"]
        if tipo == "t" or p.get("tipo") in ("tabla", "metrica", "texto"):  # sin gráfica: se muestra como tabla
            return f"**{p['titulo']}**\n\n{tabla_md(p.get('filas', []))}\n\n*{p['conclusion']}*"
        return f"{figura(ref, p)}\n\n*{p['conclusion']}*"

    texto = re.sub(r"\{\{(c|t|f|var):([^}]+)\}\}", reemplazar, (AQUI / "plantilla.md").read_text(encoding="utf-8"))
    if faltan:
        texto += "\n\n---\n**Resultados pendientes:** " + ", ".join(sorted(set(faltan)))
    md = AQUI / "reporte_tecnico.md"
    md.write_text(texto, encoding="utf-8")
    try:
        import markdown

        cuerpo = markdown.markdown(texto, extensions=["tables"])
    except ImportError:
        cuerpo = "<pre>" + html.escape(texto) + "</pre>"
    (AQUI / "reporte_tecnico.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Operaguas Analítica — Reporte técnico</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:auto;line-height:1.45;font-size:11pt}"
        "table{border-collapse:collapse;font-size:9pt}td,th{border:1px solid #bbb;padding:3px 6px}"
        "img{max-width:100%}h2{border-bottom:1px solid #ccc;page-break-after:avoid}</style>" + cuerpo,
        encoding="utf-8")
    print(f"escrito {md} ({len(set(faltan))} resultados pendientes)")
    return md


if __name__ == "__main__":
    generar()
