// Catálogo de módulos de analitica.resultados (CONTRATOS §2.2) y la página donde se muestran.
// Las descripciones dicen QUÉ técnica es y PARA QUÉ; los números salen siempre de Supabase.

export interface Modulo {
  id: string;
  nombre: string;
  bloque: string; // bloque de la rúbrica
  que: string;
  pagina: string;
}

export const MODULOS: Modulo[] = [
  { id: "pipeline", nombre: "Pipeline de datos", bloque: "A", pagina: "/datos",
    que: "Limpieza de la simulación: nulos, retrocesos de medidor, medidores mudos y columnas prohibidas." },
  { id: "eda", nombre: "Análisis exploratorio", bloque: "B", pagina: "/datos",
    que: "Distribuciones de consumo e importe, cartera y quejas por segmento." },
  { id: "estadistica", nombre: "Estadística inferencial", bloque: "C", pagina: "/datos",
    que: "Pruebas de hipótesis, intervalos de confianza y correlación." },
  { id: "series", nombre: "Series de tiempo", bloque: "D", pagina: "/temporal",
    que: "Tendencia, estacionalidad, media móvil, autocorrelación, cambio de régimen y pronóstico." },
  { id: "fourier", nombre: "Transformada de Fourier", bloque: "O", pagina: "/temporal",
    que: "Espectro del consumo horario, frecuencias dominantes y filtrado." },
  { id: "wavelets", nombre: "Wavelets (DWT)", bloque: "P", pagina: "/temporal",
    que: "Energía por nivel, reconstrucción y detección de fugas contra el flujo mínimo nocturno." },
  { id: "ml", nombre: "Modelos de pago tardío", bloque: "E, F, H", pagina: "/modelos",
    que: "Comparación de modelos con prueba temporal, umbral, errores por segmento y predicción por lotes." },
  { id: "clustering", nombre: "Segmentación", bloque: "G", pagina: "/modelos",
    que: "K-means y PCA sobre el comportamiento de consumo y pago." },
  { id: "dl", nombre: "Aprendizaje profundo", bloque: "I", pagina: "/modelos",
    que: "Red neuronal (MLP) contra el mejor modelo clásico." },
  { id: "nlp", nombre: "NLP clásico de quejas", bloque: "J", pagina: "/quejas",
    que: "TF-IDF + regresión logística para la categoría, con prueba por texto único." },
  { id: "embeddings", nombre: "Embeddings", bloque: "K", pagina: "/quejas",
    que: "Búsqueda de quejas similares: precision@5 por representación." },
  { id: "llm", nombre: "LLM", bloque: "L", pagina: "/asistente",
    que: "Triage de quejas con salida JSON validada." },
  { id: "rag_eval", nombre: "Evaluación del RAG", bloque: "M", pagina: "/asistente",
    que: "Recall@k y MRR sobre preguntas validadas por una persona." },
  { id: "agente_eval", nombre: "Evaluación del agente", bloque: "N", pagina: "/asistente",
    que: "Selección de herramientas y éxito de tareas de varios pasos." },
];

export const PAGINAS = [
  { ruta: "/", nombre: "Inicio" },
  { ruta: "/datos", nombre: "Datos y EDA" },
  { ruta: "/temporal", nombre: "Temporal" },
  { ruta: "/modelos", nombre: "Modelos" },
  { ruta: "/quejas", nombre: "Quejas" },
  { ruta: "/asistente", nombre: "Asistente IA" },
  { ruta: "/resultados", nombre: "Resultados" },
] as const;

export function modulosDe(pagina: string): Modulo[] {
  return MODULOS.filter((m) => m.pagina === pagina);
}
