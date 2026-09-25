// Formato de `payload` de analitica.resultados (docs/CONTRATOS.md §2.4) y su validación.
// Lógica pura (sin React ni red) para poder probarla con `node --test`.
// Regla 7: el front solo presenta; los únicos cálculos aquí son de dibujo
// (escalas, marcas de eje) y el respaldo de cuartiles acordado en #38/#40.

export const TIPOS = ["linea", "barras", "dispersion", "histograma", "caja", "tabla", "texto", "metrica"] as const;
export type Tipo = (typeof TIPOS)[number];

export type Valor = number | string | boolean | null;
export type Fila = Record<string, Valor>;

export interface Eje {
  etiqueta?: string;
  valores?: (number | string)[];
}

export interface SerieXY {
  nombre: string;
  valores: (number | null)[];
}

/** Dispersión: cada serie trae sus propios x (p. ej. PC1) y valores (PC2). */
export interface SerieDispersion {
  nombre: string;
  x: number[];
  valores: number[];
}

export interface SerieCaja {
  nombre: string;
  n?: number;
  min: number;
  q1: number;
  mediana: number;
  q3: number;
  max: number;
  atipicos: number[];
}

interface Base {
  titulo: string;
  conclusion: string;
  fuente: string;
  filas?: Fila[];
}

export type Payload =
  | (Base & { tipo: "linea" | "barras" | "histograma"; x: Eje; y: Eje; series: SerieXY[] })
  | (Base & { tipo: "dispersion"; x: Eje; y: Eje; series: SerieDispersion[] })
  | (Base & { tipo: "caja"; y: Eje; series: SerieCaja[] })
  | (Base & { tipo: "tabla"; filas: Fila[] })
  | (Base & { tipo: "metrica"; filas: { indicador: string; valor: Valor }[] })
  | (Base & { tipo: "texto" });

export interface Resultado {
  modulo: string;
  clave: string;
  version: string;
  validado_por?: string | null;
  payload: unknown;
}

export type Validacion = { ok: true; payload: Payload } | { ok: false; motivo: string };

const esObjeto = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const esTexto = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0;
const esNumero = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function filasValidas(v: unknown): v is Fila[] {
  return Array.isArray(v) && v.every(esObjeto);
}

/** Valida la forma mínima para dibujar. Un payload mal armado devuelve el motivo, nunca lanza. */
export function validarPayload(p: unknown): Validacion {
  if (!esObjeto(p)) return { ok: false, motivo: "el payload no es un objeto" };
  const tipo = p.tipo;
  if (typeof tipo !== "string" || !(TIPOS as readonly string[]).includes(tipo)) {
    return { ok: false, motivo: `tipo desconocido: ${String(tipo)}` };
  }
  for (const campo of ["titulo", "conclusion", "fuente"] as const) {
    if (!esTexto(p[campo])) return { ok: false, motivo: `falta «${campo}»` };
  }
  if (p.filas !== undefined && !filasValidas(p.filas)) return { ok: false, motivo: "«filas» debe ser una lista de objetos" };

  switch (tipo as Tipo) {
    case "dispersion": {
      // Dos formas: series[].x propio (resultado clustering/pca_segmentos) o x.valores numérico común.
      if (!Array.isArray(p.series) || p.series.length === 0) return { ok: false, motivo: "falta «series»" };
      const comun = esObjeto(p.x) && Array.isArray(p.x.valores) ? p.x.valores : null;
      const series: SerieDispersion[] = [];
      for (const s of p.series) {
        if (!esObjeto(s) || !Array.isArray(s.valores)) return { ok: false, motivo: "cada serie necesita «valores»" };
        const xs = Array.isArray(s.x) ? s.x : comun;
        if (!xs) return { ok: false, motivo: `la serie «${String(s.nombre)}» no trae «x»` };
        if (xs.length !== s.valores.length) return { ok: false, motivo: `la serie «${String(s.nombre)}» tiene x y valores de distinto largo` };
        if (!xs.every(esNumero) || !s.valores.every(esNumero)) return { ok: false, motivo: `la serie «${String(s.nombre)}» tiene valores no numéricos` };
        series.push({ nombre: String(s.nombre ?? "serie"), x: xs as number[], valores: s.valores as number[] });
      }
      return { ok: true, payload: { ...(p as object), x: esObjeto(p.x) ? p.x : {}, y: esObjeto(p.y) ? p.y : {}, series } as unknown as Payload };
    }
    case "linea":
    case "barras":
    case "histograma": {
      const x = p.x, series = p.series;
      if (!esObjeto(x) || !Array.isArray(x.valores) || x.valores.length === 0) return { ok: false, motivo: "falta x.valores" };
      if (!Array.isArray(series) || series.length === 0) return { ok: false, motivo: "falta «series»" };
      for (const s of series) {
        if (!esObjeto(s) || !Array.isArray(s.valores)) return { ok: false, motivo: "cada serie necesita «valores»" };
        if (s.valores.length !== x.valores.length) {
          return { ok: false, motivo: `la serie «${String(s.nombre)}» tiene ${s.valores.length} valores y x tiene ${x.valores.length}` };
        }
        if (!s.valores.every((v) => v === null || esNumero(v))) return { ok: false, motivo: `la serie «${String(s.nombre)}» tiene valores no numéricos` };
      }
      return { ok: true, payload: { ...(p as object), y: esObjeto(p.y) ? p.y : {} } as unknown as Payload };
    }
    case "caja": {
      if (!Array.isArray(p.series) || p.series.length === 0) return { ok: false, motivo: "falta «series»" };
      const series: SerieCaja[] = [];
      for (const s of p.series) {
        if (!esObjeto(s)) return { ok: false, motivo: "serie de caja inválida" };
        const c = normalizarCaja(s);
        if (!c) return { ok: false, motivo: `la serie «${String(s.nombre)}» no trae cuartiles ni valores` };
        series.push(c);
      }
      return { ok: true, payload: { ...(p as object), y: esObjeto(p.y) ? p.y : {}, series } as unknown as Payload };
    }
    case "tabla":
      if (!filasValidas(p.filas) || p.filas.length === 0) return { ok: false, motivo: "la tabla no trae «filas»" };
      return { ok: true, payload: p as unknown as Payload };
    case "metrica": {
      if (filasValidas(p.filas) && p.filas.length > 0) {
        if (!p.filas.every((f) => esTexto(f.indicador) && "valor" in f)) return { ok: false, motivo: "cada fila de métrica necesita «indicador» y «valor»" };
        return { ok: true, payload: p as unknown as Payload };
      }
      if ("valor" in p) {
        const filas = [{ indicador: p.titulo as string, valor: p.valor as Valor }];
        return { ok: true, payload: { ...(p as object), filas } as unknown as Payload };
      }
      return { ok: false, motivo: "la métrica no trae «valor» ni «filas»" };
    }
    case "texto":
      return { ok: true, payload: p as unknown as Payload };
  }
}

/** Cuartiles precalculados (#38) o, como respaldo, calculados de `valores` (percentil lineal = numpy). */
export function normalizarCaja(s: Record<string, unknown>): SerieCaja | null {
  const nombre = String(s.nombre ?? "serie");
  const claves = ["min", "q1", "mediana", "q3", "max"] as const;
  if (claves.every((k) => esNumero(s[k]))) {
    const atipicos = Array.isArray(s.atipicos) ? s.atipicos.filter(esNumero) : [];
    return {
      nombre, n: esNumero(s.n) ? s.n : undefined,
      min: s.min as number, q1: s.q1 as number, mediana: s.mediana as number, q3: s.q3 as number, max: s.max as number,
      atipicos,
    };
  }
  if (Array.isArray(s.valores)) {
    const v = s.valores.filter(esNumero).sort((a, b) => a - b);
    if (v.length === 0) return null;
    const q1 = percentil(v, 25), q3 = percentil(v, 75), iqr = q3 - q1;
    const dentro = v.filter((x) => x >= q1 - 1.5 * iqr && x <= q3 + 1.5 * iqr);
    return {
      nombre, n: v.length, q1, q3, mediana: percentil(v, 50),
      min: dentro[0], max: dentro[dentro.length - 1],
      atipicos: v.filter((x) => x < q1 - 1.5 * iqr || x > q3 + 1.5 * iqr).slice(0, 50),
    };
  }
  return null;
}

/** Percentil con interpolación lineal (igual que numpy.percentile por defecto). `ordenados` ascendente. */
export function percentil(ordenados: number[], p: number): number {
  if (ordenados.length === 1) return ordenados[0];
  const pos = (p / 100) * (ordenados.length - 1);
  const i = Math.floor(pos), f = pos - i;
  return i + 1 < ordenados.length ? ordenados[i] + f * (ordenados[i + 1] - ordenados[i]) : ordenados[i];
}

/** Marcas "bonitas" para un eje (1, 2, 2.5, 5 × 10^k). */
export function marcas(min: number, max: number, cuantas = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0];
  if (min === max) {
    const d = Math.abs(min) || 1;
    min -= d / 2;
    max += d / 2;
  }
  const bruto = (max - min) / Math.max(1, cuantas);
  const pot = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * pot).find((s) => s >= bruto) ?? 10 * pot;
  const ini = Math.floor(min / paso) * paso, fin = Math.ceil(max / paso) * paso;
  const salida: number[] = [];
  for (let v = ini; v <= fin + paso / 2; v += paso) salida.push(Number(v.toPrecision(12)));
  return salida;
}

const fmt = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 2 });
const fmtChico = new Intl.NumberFormat("es-MX", { maximumSignificantDigits: 3 });

export function formatear(v: Valor | undefined): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "sí" : "no";
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return "—";
    return Math.abs(v) > 0 && Math.abs(v) < 0.01 ? fmtChico.format(v) : fmt.format(v);
  }
  return v;
}

/** Nombre legible de un identificador (sin_agua → sin agua). */
export function legible(s: string): string {
  return s.replace(/_/g, " ");
}
