// Lectura de analitica.resultados_vigentes (solo en el servidor de Next).
// PostgREST de Supabase con la llave pública (anon/publishable): RLS solo permite SELECT.
// Requiere el esquema `analitica` en "Exposed schemas" de la Data API.
import "server-only";

import type { Resultado } from "./payload.ts";

export const REVALIDAR_S = 300; // las páginas se regeneran como máximo cada 5 minutos (ISR)

export type Lectura =
  | { ok: true; filas: Resultado[]; origen: "supabase" | "muestra" }
  | { ok: false; motivo: string };

/**
 * Devuelve los resultados vigentes de los módulos pedidos, ordenados por módulo y clave.
 * Nunca lanza: un fallo de red o de configuración regresa `ok: false` con un motivo para mostrar.
 * RESULTADOS_MUESTRA=1 (solo desarrollo) usa app/_lib/muestra.json, copia de
 * pipeline/artefactos/resultados/*.json generada por el pipeline.
 */
export async function leerResultados(modulos: string[]): Promise<Lectura> {
  if (process.env.RESULTADOS_MUESTRA === "1") {
    const muestra = (await import("./muestra.json")).default as Resultado[];
    return { ok: true, origen: "muestra", filas: muestra.filter((r) => modulos.includes(r.modulo)) };
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const llave = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();
  if (!url || !llave) {
    return { ok: false, motivo: "Falta configurar NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY en Vercel." };
  }

  const params = new URLSearchParams({
    select: "modulo,clave,version,validado_por,payload",
    modulo: `in.(${modulos.join(",")})`,
    order: "modulo.asc,clave.asc",
  });
  try {
    const r = await fetch(`${url.replace(/\/$/, "")}/rest/v1/resultados_vigentes?${params}`, {
      headers: { apikey: llave, "Accept-Profile": "analitica" },
      next: { revalidate: REVALIDAR_S },
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) {
      return { ok: false, motivo: `Supabase respondió HTTP ${r.status}. Revisa que «analitica» esté en Exposed schemas.` };
    }
    const datos: unknown = await r.json();
    if (!Array.isArray(datos)) return { ok: false, motivo: "Supabase no devolvió una lista de resultados." };
    return { ok: true, origen: "supabase", filas: datos as Resultado[] };
  } catch {
    return { ok: false, motivo: "No se pudo conectar con Supabase para leer los resultados. Intenta de nuevo en unos minutos." };
  }
}
