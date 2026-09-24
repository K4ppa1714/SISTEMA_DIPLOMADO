// Llamadas del navegador a /api/* con manejo uniforme de errores (CONTRATOS §3).
// Distingue fallo HTTP, error de negocio {"error": {...}} y respuesta que no es JSON.

export type RespuestaApi<T> = { ok: true; datos: T } | { ok: false; mensaje: string };

export async function llamarApi<T>(ruta: string, init?: RequestInit, esperaMs = 25000): Promise<RespuestaApi<T>> {
  let r: Response;
  try {
    r = await fetch(ruta, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
      signal: AbortSignal.timeout(esperaMs),
    });
  } catch (e) {
    const tiempo = e instanceof DOMException && e.name === "TimeoutError";
    return { ok: false, mensaje: tiempo ? "La API tardó demasiado en responder. Intenta de nuevo." : "No hay conexión con la API." };
  }
  let cuerpo: unknown;
  try {
    cuerpo = await r.json();
  } catch {
    return { ok: false, mensaje: `La API respondió HTTP ${r.status} sin un JSON válido.` };
  }
  const err = (cuerpo as { error?: { mensaje?: string } } | null)?.error;
  if (!r.ok || err) {
    return { ok: false, mensaje: err?.mensaje ?? `La API respondió HTTP ${r.status}.` };
  }
  return { ok: true, datos: cuerpo as T };
}
