import type { Metadata } from "next";
import Link from "next/link";

import Resultado from "../_componentes/Resultado.tsx";
import { MODULOS } from "../_lib/modulos.ts";
import { leerResultados } from "../_lib/resultados.ts";

export const revalidate = 300;
export const metadata: Metadata = { title: "Resultados" };

// Resultado principal de cada bloque: el que responde la pregunta del bloque.
const PRINCIPALES: { modulo: string; clave: string; pregunta: string }[] = [
  { modulo: "ml", clave: "comparacion_modelos", pregunta: "¿Qué modelo anticipa mejor el pago tardío y contra qué línea base?" },
  { modulo: "ml", clave: "predicciones_resumen", pregunta: "¿Cuántos recibos por vencer están en riesgo?" },
  { modulo: "wavelets", clave: "deteccion_fugas", pregunta: "¿Qué tan bien se detectan las fugas en la telemetría?" },
  { modulo: "fourier", clave: "frecuencias_dominantes", pregunta: "¿Qué ciclos tiene el consumo?" },
  { modulo: "series", clave: "prediccion_mensual", pregunta: "¿Se puede pronosticar el consumo mensual?" },
  { modulo: "estadistica", clave: "pruebas_hipotesis", pregunta: "¿Qué hipótesis se sostienen con los datos?" },
  { modulo: "clustering", clave: "segmentos_perfil", pregunta: "¿Qué grupos de tomas existen?" },
  { modulo: "dl", clave: "mlp_vs_gb", pregunta: "¿Mejora una red neuronal al modelo clásico?" },
  { modulo: "nlp", clave: "clasificacion_metricas", pregunta: "¿Se puede clasificar una queja por su texto?" },
  { modulo: "embeddings", clave: "similitud_precision5", pregunta: "¿Qué representación encuentra mejor las quejas parecidas?" },
  { modulo: "llm", clave: "triage_validacion", pregunta: "¿El LLM respeta el formato y coincide con el clasificador?" },
  { modulo: "rag_eval", clave: "recall_mrr", pregunta: "¿El buscador del RAG encuentra el documento correcto?" },
  { modulo: "agente_eval", clave: "tool_selection", pregunta: "¿El agente elige las herramientas correctas?" },
];

const GLOSARIO: [string, string][] = [
  ["PR-AUC", "Área bajo la curva precisión–recall. Útil cuando la clase positiva (pagar tarde) es minoritaria; la línea base es la tasa de positivos."],
  ["ROC-AUC", "Probabilidad de que el modelo ordene un positivo por encima de un negativo; 0.5 es azar."],
  ["Precisión / Recall / F1", "De los marcados, cuántos eran reales / de los reales, cuántos se marcaron / su media armónica."],
  ["Separación temporal", "Se entrena con el pasado y se prueba con meses posteriores: nada del futuro entra al modelo."],
  ["Silhouette", "Qué tan separados están los grupos de K-means (−1 a 1); cerca de 0 indica grupos traslapados."],
  ["MAE", "Error absoluto medio del pronóstico, en las unidades de la serie (m³)."],
  ["R²", "Proporción de la variación que explica una reconstrucción o un modelo (1 = perfecta)."],
  ["F1 macro", "Promedio del F1 de cada categoría de queja, sin que las categorías grandes dominen."],
  ["precision@5", "De las 5 quejas más parecidas que devuelve el buscador, cuántas son de la misma categoría."],
  ["Recall@k / MRR", "Si el documento correcto aparece entre los k primeros / promedio de 1 ÷ su posición."],
  ["Abstención correcta", "Preguntas sin respuesta en los documentos a las que el RAG respondió «sin evidencia» en vez de inventar."],
  ["Tool Selection Accuracy", "Casos en los que el agente llamó exactamente las herramientas esperadas por una persona."],
];

export default async function Pagina() {
  const lectura = await leerResultados(MODULOS.map((m) => m.id));
  const filas = lectura.ok ? lectura.filas : [];
  return (
    <>
      <header className="encabezado-pagina">
        <h1>Resultados</h1>
        <div className="intro">
          <p>
            El resultado principal de cada bloque, con la pregunta que responde. El detalle está en la página de cada módulo. Todas las
            cifras se calculan en Python y se leen de Supabase; las marcadas «sin validar» esperan la revisión de una persona.
          </p>
        </div>
      </header>
      {!lectura.ok ? (
        <div className="aviso aviso-error" role="alert">
          <strong>No se pudieron leer los resultados.</strong> {lectura.motivo}
        </div>
      ) : null}
      <div className="rejilla-tarjetas">
        {PRINCIPALES.map((p) => {
          const r = filas.find((f) => f.modulo === p.modulo && f.clave === p.clave);
          const m = MODULOS.find((x) => x.id === p.modulo);
          return (
            <div key={`${p.modulo}/${p.clave}`} className="principal">
              <p className="pregunta-resultado">
                <span className="bloque">Bloque {m?.bloque}</span> {p.pregunta}{" "}
                {m ? <Link href={`${m.pagina}#m-${m.id}`}>ver módulo</Link> : null}
              </p>
              {r ? <Resultado r={r} /> : <p className="vacio">Pendiente: todavía no se publica {p.modulo}/{p.clave}.</p>}
            </div>
          );
        })}
      </div>
      <section className="modulo" aria-labelledby="t-glosario">
        <div className="modulo-cabecera">
          <h2 id="t-glosario">Cómo leer las métricas</h2>
        </div>
        <dl className="glosario">
          {GLOSARIO.map(([t, d]) => (
            <div key={t}>
              <dt>{t}</dt>
              <dd>{d}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}
