"""Evaluación del LLM en el triage (T-12, bloque L).

Uso (con .env: LLM_PROVIDER, LLM_MODEL, LLM_API_KEY y opcionalmente GROQ_*):
    python -m pipeline.src.nlp.evaluar_llm            # → pipeline/artefactos/resultados/llm.json
    python -m pipeline.src.nlp.evaluar_llm --subir    # además publica en analitica.resultados

Textos: los de PRUEBA de T-14 (división por texto único, semilla 42), para no
evaluar el LLM sobre lo que vio el clasificador al entrenar. Métricas declaradas:
- formato válido: el LLM devolvió JSON que pasa la validación Pydantic (resumen,
  categoría del catálogo, riesgo) en algún intento;
- reintentos: intentos extra que hicieron falta;
- acuerdo LLM–modelo: la categoría del LLM coincide con la del clasificador;
- exactitud del LLM y del sistema contra la etiqueta real de la simulación;
- latencia p50/p95 por texto (incluye el respaldo si el principal falla).
"""
from __future__ import annotations

import argparse
import time

FUENTE = "pipeline/src/nlp/evaluar_llm.py · api/_lib/triage.py · textos de prueba de T-14"


def evaluar(textos: list[str], reales: list[str], cliente, pausa_s: float = 0.0, triage_fn=None) -> tuple[dict, list[dict]]:
    if triage_fn is None:
        from api._lib.triage import triage as triage_fn
    filas = []
    for texto, real in zip(textos, reales):
        t0 = time.perf_counter()
        salida, d = triage_fn(texto, cliente)
        ms = round((time.perf_counter() - t0) * 1000)
        llm = d.get("llm") or {}
        filas.append({"real": real, "sistema": salida.categoria, "llm": d.get("categoria_llm"),
                      "formato_valido": d.get("categoria_llm") is not None,
                      "intentos": llm.get("intentos", 0), "proveedor": llm.get("proveedor"),
                      "acuerdo": d.get("acuerdo_llm_modelo"), "valido": salida.valido, "ms": ms})
        if pausa_s:
            time.sleep(pausa_s)
    n = len(filas)
    ok = [f for f in filas if f["formato_valido"]]
    lat = sorted(f["ms"] for f in filas)
    pct = lambda q: lat[min(n - 1, int(round(q * (n - 1))))] if n else None
    proveedores = {}
    for f in ok:
        proveedores[f["proveedor"]] = proveedores.get(f["proveedor"], 0) + 1
    m = {
        "textos": n,
        "formato_valido": round(len(ok) / n, 4) if n else None,
        "reintentos_promedio": round(sum(max(0, f["intentos"] - 1) for f in ok) / len(ok), 3) if ok else None,
        "acuerdo_llm_modelo": round(sum(bool(f["acuerdo"]) for f in ok) / len(ok), 4) if ok else None,
        "exactitud_llm": round(sum(f["llm"] == f["real"] for f in ok) / len(ok), 4) if ok else None,
        "exactitud_sistema": round(sum(f["sistema"] == f["real"] for f in filas) / n, 4) if n else None,
        "salida_marcada_valida": round(sum(f["valido"] for f in filas) / n, 4) if n else None,
        "latencia_p50_ms": pct(0.5), "latencia_p95_ms": pct(0.95),
        "proveedores": ", ".join(f"{k}: {v}" for k, v in proveedores.items()) or "ninguno",
    }
    return m, filas


def payloads(m: dict) -> list[dict]:
    return [{"clave": "triage_validacion", "payload": {
        "tipo": "metrica", "titulo": "LLM en el triage: formato, acuerdo con el modelo y latencia",
        "filas": [{"indicador": k.replace("_", " "), "valor": v} for k, v in m.items()],
        "conclusion": (f"Sobre {m['textos']} textos de prueba, el LLM devolvió JSON válido en {m['formato_valido']:.0%} y coincidió "
                       f"con el clasificador en {m['acuerdo_llm_modelo']:.0%}; la categoría final la da el clasificador y el LLM "
                       f"solo redacta el resumen y señala riesgo." if m["formato_valido"] and m["acuerdo_llm_modelo"] is not None
                       else "El LLM no respondió en esta corrida; el triage siguió funcionando con el clasificador y valido=false."),
        "fuente": FUENTE}}]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--subir", action="store_true")
    ap.add_argument("--pausa", type=float, default=4.5, help="segundos entre llamadas (límite gratuito)")
    a = ap.parse_args()
    from api._lib.llm import crear_cliente
    from pipeline.src.nlp.clasificador import cargar_quejas, dividir_por_texto_unico, textos_unicos

    cliente = crear_cliente()
    if cliente is None:
        raise SystemExit("Faltan LLM_PROVIDER, LLM_MODEL y LLM_API_KEY en el entorno.")
    _, prueba = dividir_por_texto_unico(textos_unicos(cargar_quejas()))
    m, _ = evaluar(list(prueba["descripcion"]), list(prueba["categoria"]), cliente, a.pausa)
    from pipeline.src.data.publicar import guardar, subir
    ruta = guardar("llm", payloads(m))
    print(m, "→", ruta)
    if a.subir:
        subir(ruta)


if __name__ == "__main__":
    main()
