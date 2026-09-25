"""Genera los notebooks 08, 09 y 10 (dueño: Claude-A) a partir del código.

Mismas reglas que _generar.py: sin lógica propia ni números escritos a mano; llaman a
pipeline/src y api/_lib, dibujan cada payload y terminan con "Conclusiones" calculadas.
Las evaluaciones que requieren llaves (LLM/embeddings) o el índice del RAG se leen de
pipeline/artefactos/resultados/*.json cuando ya se corrieron; si no, el notebook lo dice.

Uso:
    python pipeline/notebooks/_generar_a.py
    jupyter nbconvert --to notebook --execute --inplace pipeline/notebooks/0[89]_*.ipynb pipeline/notebooks/10_*.ipynb
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _generar import PREAMBULO, code, guardar, md  # noqa: E402

LEER_RESULTADO = '''import json
def resultado(modulo, clave):
    """Payload publicado por el evaluador (pipeline/artefactos/resultados/<modulo>.json) o None."""
    ruta = raiz / "pipeline" / "artefactos" / "resultados" / f"{modulo}.json"
    if not ruta.exists():
        return None
    return next((f["payload"] for f in json.loads(ruta.read_text(encoding="utf-8")) if f["clave"] == clave), None)'''

NB = {
    "08_embeddings.ipynb": [
        md("""# 08 · Embeddings y búsqueda semántica de quejas (T-14, bloque K)

**Dónde:** `pipeline/src/nlp/similitud.py`. **Por qué:** cuando llega una queja nueva, el área de atención quiere
ver quejas parecidas ya atendidas (reutilizar la respuesta o detectar un brote en una zona).
**Cómo:** se comparan tres representaciones con la MISMA división por texto único del clasificador (un texto
nunca se encuentra a sí mismo): TF-IDF (coincidencia de palabras), LSA (SVD truncado de TF-IDF, densa) y,
si hay acceso a Hugging Face, Sentence-Transformers multilingüe. **Métrica:** precision@5 (de las 5 quejas más
parecidas, qué fracción es de la misma categoría). **Datos:** `data/simulados/quejas.csv` (simulación declarada)."""),
        code(PREAMBULO),
        code("""from pipeline.src.nlp.similitud import comparar
filas = comparar()          # intenta Sentence-Transformers; si no hay red lo reporta sin inventar
pd.DataFrame(filas)"""),
        md("""## Resultado publicado (embeddings/similitud_precision5)

El mismo cálculo que corre `pipeline/src/nlp/resultados.py` y que se ve en la página **Quejas** de la app."""),
        code("""from pipeline.src.nlp.resultados import construir_payloads
piezas = {p["clave"]: p["payload"] for p in construir_payloads()}
dibujar(piezas["similitud_precision5"])"""),
        md("""## Frente a TF-IDF

TF-IDF solo encuentra quejas que comparten palabras; una representación densa puede acercar sinónimos
("no llega agua" / "sin servicio"). La comparación se hace con la misma métrica y los mismos textos."""),
        code("""ejecutadas = [f for f in filas if f.get("ejecutado")]
mejor = max(ejecutadas, key=lambda f: f["precision_at_5"])
no_ejecutadas = [f for f in filas if not f.get("ejecutado")]
print(f"Mejor representación: {mejor['representacion']} (precision@5 = {mejor['precision_at_5']:.3f}).")
for f in ejecutadas:
    print(f"- {f['representacion']}: {f['precision_at_5']:.3f} con {f['dimension']} dimensiones")
for f in no_ejecutadas:
    print(f"- {f['representacion']}: NO ejecutado ({f.get('motivo', 'sin motivo')})")"""),
        md("## Conclusiones"),
        code("""tfidf = next(f for f in filas if f["representacion"] == "TF-IDF")
top = max(f["precision_at_5"] for f in ejecutadas)
empatadas = [f["representacion"] for f in ejecutadas if abs(f["precision_at_5"] - top) < 5e-4]
if len(empatadas) > 1:
    print(f"1. Con división por texto único, {' y '.join(empatadas)} empatan en precision@5 = {top:.3f}: la representación densa (LSA) no mejora a TF-IDF en quejas cortas con vocabulario repetitivo.")
else:
    otras = ", ".join(f"{f['representacion']} {f['precision_at_5']:.3f}" for f in ejecutadas if f is not mejor)
    print(f"1. Con división por texto único, la mejor representación es {mejor['representacion']} (precision@5 = {mejor['precision_at_5']:.3f}) frente a {otras}.")
print("2. La métrica mide si las quejas parecidas son de la misma categoría: sirve para sugerir respuestas y detectar brotes, no para decidir la prioridad.")
print("3. " + ("Sentence-Transformers no se pudo ejecutar en este entorno; se reporta como pendiente y no se inventa su resultado." if no_ejecutadas else "Sentence-Transformers se ejecutó con el mismo protocolo."))
print("4. Los embeddings de Gemini (768 dimensiones) se usan en el RAG (notebook 09), no en esta comparación.")"""),
    ],
    "09_rag_evaluacion.ipynb": [
        md("""# 09 · RAG: corpus, fragmentos, índice y evaluación del retriever (T-11 y T-16, bloque M)

**Dónde:** `pipeline/src/rag/corpus.py` (corpus y chunking), `pipeline/src/rag/indexar.py` (embeddings + pgvector),
`api/_lib/rag.py` (consulta con umbral y fuentes), `pipeline/src/rag/evaluar.py` (métricas).
**Por qué:** el área de atención responde preguntas sobre tarifas y reglas del recibo; el RAG responde **solo** con
los documentos y dice cuándo no hay evidencia. **Cómo:** documentos → fragmentos de 900 caracteres con solape de
150 → embeddings Gemini de 768 dimensiones → `rag.buscar_fragmentos` (Top-k por coseno) → umbral de evidencia →
LLM que debe citar los fragmentos. **Datos:** tarifario CEA 2026-T3 (`api/_lib/tarifas_cea.csv`), reglas del
recibo portadas de Odoo y la documentación de los datos simulados. Sin datos personales."""),
        code(PREAMBULO),
        code(LEER_RESULTADO),
        code("""from pipeline.src.rag.corpus import construir_corpus, TAMANO, SOLAPE
docs = construir_corpus()
resumen = pd.DataFrame([{"titulo": d.titulo, "tipo": d.tipo, "fragmentos": len(d.fragmentos),
                         "caracteres": len(d.texto)} for d in docs])
print(f"{len(docs)} documentos · {resumen['fragmentos'].sum()} fragmentos · tamaño {TAMANO}, solape {SOLAPE}")
resumen"""),
        md("## Distribución del tamaño de los fragmentos"),
        code("""import matplotlib.pyplot as plt
largos = [len(f) for d in docs for f in d.fragmentos]
fig, ax = plt.subplots(figsize=(9, 3.5))
ax.hist(largos, bins=15)
ax.set_title("Tamaño de los fragmentos del corpus")
ax.set_xlabel("Caracteres por fragmento"); ax.set_ylabel("Fragmentos")
plt.show()
print(f"Mediana {pd.Series(largos).median():.0f} caracteres; máximo {max(largos)} (límite {TAMANO}).")"""),
        md("""## Ejemplo de fragmento (con metadatos que se guardan en `rag.fragmentos`)"""),
        code("""from pipeline.src.rag.indexar import filas
documentos, fragmentos = filas(docs)
ej = fragmentos[0]
print({k: v for k, v in ej.items() if k != "contenido"})
print(ej["contenido"][:600])"""),
        md("""## Control de alucinaciones (diseño de `api/_lib/rag.py`)

1. Si ninguna similitud supera el umbral, `evidencia=false` y **no se llama al LLM**.
2. El LLM recibe solo los fragmentos numerados y debe responder `SIN_EVIDENCIA` si no bastan.
3. La salida se valida con Pydantic y debe citar al menos un fragmento existente; si no, se responde de forma extractiva."""),
        code("""from api._lib.rag import UMBRAL_SIMILITUD, SIN_EVIDENCIA, responder

class EmbeddingFijo:            # solo para demostrar el flujo sin llaves: NO es una métrica
    def embeber(self, textos): return [[1.0] + [0.0] * 767 for _ in textos]

sin_fuentes = lambda v, k: [{"fragmento_id": "x", "documento_id": "y", "titulo": "otro tema", "contenido": "…", "similitud": 0.2}]
salida, detalle = responder("¿Quién ganó el mundial?", 5, EmbeddingFijo(), sin_fuentes, llm=None)
print(f"umbral = {UMBRAL_SIMILITUD}; evidencia = {salida.evidencia}; respuesta: {salida.respuesta}")"""),
        md("""## Preguntas de evaluación (T-16a)

Borrador en `docs/eval/rag_preguntas_borrador.csv`; **solo las validadas por una persona** entran a la métrica."""),
        code("""from pipeline.src.rag.evaluar import cargar_preguntas
todas = cargar_preguntas(incluir_sin_validar=True)
validadas = cargar_preguntas()
print(f"{len(todas)} preguntas en el borrador · {sum(not p['con_evidencia'] for p in todas)} sin evidencia esperada · {len(validadas)} validadas")"""),
        md("## Resultado: Recall@k, MRR y abstención (rag_eval)"),
        code("""p = resultado("rag_eval", "recall_mrr")
if p:
    dibujar(p)
else:
    print("PENDIENTE: aún no se corre `python -m pipeline.src.rag.evaluar` (requiere el índice en rag.fragmentos y preguntas validadas).")"""),
        md("## Conclusiones"),
        code("""print(f"1. El corpus tiene {len(docs)} documentos y {resumen['fragmentos'].sum()} fragmentos; cada fragmento guarda fuente, tipo y tamaño para citarlo.")
print(f"2. El umbral de evidencia ({UMBRAL_SIMILITUD}) hace que una pregunta fuera del corpus responda sin evidencia sin llamar al LLM.")
if p:
    print("3. " + p["conclusion"])
else:
    print(f"3. La métrica del retriever está pendiente: faltan el índice y la validación de {len(todas)} preguntas; no se reporta un número sin correrla.")
print("4. La app muestra las fuentes de cada respuesta (título, fragmento y similitud) en la página Asistente IA.")"""),
    ],
    "10_agente_evaluacion.ipynb": [
        md("""# 10 · Agente con herramientas: diseño, validación y evaluación (T-15 y T-16, bloque N)

**Dónde:** `api/_lib/agente/herramientas.py` (herramientas y esquemas), `api/_lib/agente/agente.py` (router y
dispatcher), `pipeline/src/agents/evaluar.py` (métricas). **Por qué:** una consulta real del área de atención suele
necesitar varios datos ("¿cuánto debe esta toma y pagará a tiempo?"). **Cómo:** en cada turno el LLM elige UNA
herramienta con argumentos en JSON; el dispatcher valida la decisión y los argumentos (Pydantic), ejecuta, mide el
tiempo y devuelve la observación; máximo 5 pasos; cada paso se registra en `agente.log`. **Datos:** Supabase
(`raw.recibos`, `analitica.predicciones_pago`, resultados de series) y el tarifario CEA."""),
        code(PREAMBULO),
        code(LEER_RESULTADO),
        code("""from api._lib.agente.herramientas import HERRAMIENTAS
pd.DataFrame([{"herramienta": h.nombre, "descripcion": h.descripcion,
               "argumentos": ", ".join(h.esquema()["argumentos"]), "obligatorios": ", ".join(h.esquema()["obligatorios"])}
              for h in HERRAMIENTAS.values()])"""),
        md("""## Validación y manejo de errores del dispatcher

Para mostrar el mecanismo **sin gastar cuota del LLM** se usa un LLM guionizado (decisiones fijas) y datos de
ejemplo. Esto demuestra la validación, no mide al agente: la métrica real está al final."""),
        code("""import json
from api._lib.agente.agente import ejecutar_agente, MAX_PASOS
from api._lib.agente.herramientas import Contexto

class DatosEjemplo:
    def recibos(self, id_toma, n):
        return [{"periodo": "2026-09", "fecha_vencimiento": "2026-09-20", "total_pagar": 700.5, "pagado": False, "pago_tardio": None}] if id_toma == "TEJEMPLO01" else []
    def predicciones(self, id_toma, periodo):
        return [{"periodo": "2026-09", "prob_pago_tardio": 0.8, "clase_predicha": True, "modelo": "regresion_logistica", "version": "v1"}] if id_toma == "TEJEMPLO01" else []
    def resultados(self, modulo):
        return []

class Guion:
    nombre = "guion"
    def __init__(self, decisiones): self.d = list(decisiones)
    def generar_json(self, sistema, usuario): return json.dumps(self.d.pop(0))

ctx = Contexto(datos=DatosEjemplo())
bitacora = []
salida, detalle = ejecutar_agente(
    "¿Cuánto debe la toma TEJEMPLO01 y pagará tarde?", None,
    Guion([{"accion": "herramienta", "herramienta": "calcular_importe", "argumentos": {"tipo_tarifa": "lunar", "consumo_m3": 5}},
           {"accion": "herramienta", "herramienta": "estado_cuenta", "argumentos": {"id_toma": "TEJEMPLO01"}},
           {"accion": "herramienta", "herramienta": "predecir_pago", "argumentos": {"id_toma": "TEJEMPLO01"}},
           {"accion": "responder", "respuesta": "Debe 700.50 y está en riesgo de pagar tarde."}]),
    ctx, bitacora.append)
pd.DataFrame([{"paso": b["paso"], "herramienta": b["herramienta"], "error": b["error"], "ms": b["ms"]} for b in bitacora])"""),
        code("""print("Respuesta:", salida.respuesta)
print("Errores de herramienta:", detalle["errores_herramienta"], "· decisiones inválidas:", detalle["decisiones_invalidas"])
limite, _ = ejecutar_agente("repite", None, Guion([{"accion": "herramienta", "herramienta": "estado_cuenta", "argumentos": {"id_toma": "TEJEMPLO01"}}] * 7), ctx)
print(f"Con un LLM que nunca responde, el agente se detiene en {len(limite.pasos)} pasos (límite {MAX_PASOS}): {limite.respuesta[:80]}…")"""),
        md("""## Casos de evaluación (T-16b)

Borrador en `docs/eval/agente_casos_borrador.csv` con la(s) herramienta(s) esperada(s); **solo los validados por
Andrés** cuentan. La evaluación llama a la URL pública (donde viven las llaves) con `python -m pipeline.src.agents.evaluar`."""),
        code("""from pipeline.src.agents.evaluar import cargar_casos
casos = cargar_casos(incluir_sin_validar=True)
print(f"{len(casos)} casos · {sum(c['multipaso'] for c in casos)} multipaso · {len(cargar_casos())} validados")
pd.Series([h for c in casos for h in c["esperadas"]]).value_counts().rename("veces esperada")"""),
        md("## Resultado: Tool Selection Accuracy y éxito de tareas (agente_eval)"),
        code("""p = resultado("agente_eval", "tool_selection")
if p:
    dibujar(p)
else:
    print("PENDIENTE: aún no se corre `python -m pipeline.src.agents.evaluar` (requiere casos validados y /api/agente desplegado).")"""),
        md("## Conclusiones"),
        code("""print(f"1. El agente tiene {len(HERRAMIENTAS)} herramientas con argumentos validados; un argumento inválido vuelve al LLM como observación y no rompe la respuesta.")
print(f"2. El límite de {MAX_PASOS} pasos se cumple aunque el LLM nunca decida responder, y cada paso queda en agente.log con su tiempo.")
print(f"3. Hay {len(casos)} casos de evaluación ({sum(c['multipaso'] for c in casos)} de varios pasos) escritos antes de correr al agente.")
print("4. " + (p["conclusion"] if p else "La Tool Selection Accuracy está pendiente de la validación humana de los casos; no se reporta un número sin correrla."))"""),
    ],
}

if __name__ == "__main__":
    for nombre, celdas in NB.items():
        guardar(nombre, celdas)
