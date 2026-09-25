// Componente ÚNICO que dibuja cualquier payload de analitica.resultados (CONTRATOS §2.4, T-13).
// Server Component: SVG puro, sin librerías de gráficas ni JavaScript en el navegador.
// Un payload mal armado se muestra como tarjeta de error y no rompe la página.
import type { ReactNode } from "react";

import {
  formatear,
  legible,
  marcas,
  validarPayload,
  type Fila,
  type Payload,
  type Resultado as FilaResultado,
  type SerieCaja,
  type SerieDispersion,
  type SerieXY,
} from "../_lib/payload.ts";

const W = 480; // ancho lógico del SVG; se escala al contenedor
const M = { arriba: 16, derecha: 18, abajo: 56, izquierda: 70 };
const COLORES = 6;

export default function Resultado({ r }: { r: FilaResultado }) {
  const v = validarPayload(r.payload);
  if (!v.ok) {
    return (
      <article className="tarjeta tarjeta-error" aria-label={`Resultado ${r.modulo}/${r.clave} con formato inválido`}>
        <header className="tarjeta-cabecera">
          <h3>{r.clave ? legible(r.clave) : "Resultado"}</h3>
          <Insignias r={r} />
        </header>
        <p>No se puede dibujar este resultado: {v.motivo}.</p>
        <p className="fuente">
          Origen: <code>{r.modulo}/{r.clave}</code>
        </p>
      </article>
    );
  }
  const p = v.payload;
  return (
    <article className="tarjeta" id={`${r.modulo}-${r.clave}`}>
      <header className="tarjeta-cabecera">
        <h3>{p.titulo}</h3>
        <Insignias r={r} />
      </header>
      <Cuerpo p={p} />
      <p className="conclusion">{p.conclusion}</p>
      {p.tipo !== "tabla" && p.tipo !== "metrica" && p.filas && p.filas.length > 0 ? (
        <details className="detalle-datos">
          <summary>Ver datos ({p.filas.length} filas)</summary>
          <Tabla filas={p.filas} />
        </details>
      ) : null}
      <p className="fuente">
        Fuente: <code>{p.fuente}</code>
      </p>
    </article>
  );
}

function Insignias({ r }: { r: FilaResultado }) {
  return (
    <span className="insignias">
      <span className="insignia" title="Versión del resultado">
        {r.version}
      </span>
      {r.validado_por ? (
        <span className="insignia insignia-ok" title="Conclusión validada por una persona del equipo">
          validado: {r.validado_por}
        </span>
      ) : (
        <span className="insignia insignia-pendiente" title="Conclusión pendiente de validación humana">
          sin validar
        </span>
      )}
    </span>
  );
}

function Cuerpo({ p }: { p: Payload }) {
  switch (p.tipo) {
    case "linea":
      return <Lineas x={p.x.valores ?? []} series={p.series} etiquetaX={p.x.etiqueta} etiquetaY={p.y.etiqueta} titulo={p.titulo} />;
    case "dispersion":
      return <Dispersion series={p.series} etiquetaX={p.x.etiqueta} etiquetaY={p.y.etiqueta} titulo={p.titulo} />;
    case "barras":
      return <BarrasHorizontales x={p.x.valores ?? []} series={p.series} etiquetaY={p.y.etiqueta} titulo={p.titulo} />;
    case "histograma":
      return <Histograma x={p.x.valores ?? []} serie={p.series[0]} etiquetaX={p.x.etiqueta} etiquetaY={p.y.etiqueta} titulo={p.titulo} />;
    case "caja":
      return <Cajas series={p.series} etiqueta={p.y.etiqueta} titulo={p.titulo} />;
    case "tabla":
      return <Tabla filas={p.filas} />;
    case "metrica":
      return (
        <dl className="metricas">
          {p.filas.map((f, i) => (
            <div key={i} className="metrica">
              <dt>{f.indicador}</dt>
              <dd>{formatear(f.valor)}</dd>
            </div>
          ))}
        </dl>
      );
    case "texto":
      return null;
  }
}

// ------------------------------------------------------------------ piezas SVG
function Svg({ alto, titulo, children }: { alto: number; titulo: string; children: ReactNode }) {
  return (
    <div className="grafica">
      <svg viewBox={`0 0 ${W} ${alto}`} role="img" aria-label={titulo} preserveAspectRatio="xMidYMid meet">
        {children}
      </svg>
    </div>
  );
}

function Leyenda({ nombres }: { nombres: string[] }) {
  if (nombres.length < 2) return null;
  return (
    <ul className="leyenda" aria-label="Series">
      {nombres.map((n, i) => (
        <li key={n + i}>
          <span className={`muestra-color c${(i % COLORES) + 1}`} aria-hidden /> {legible(n)}
        </li>
      ))}
    </ul>
  );
}

function EjeY({ ticks, y, x0, x1, etiqueta, alto }: { ticks: number[]; y: (v: number) => number; x0: number; x1: number; etiqueta?: string; alto: number }) {
  return (
    <g className="eje">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x0} x2={x1} y1={y(t)} y2={y(t)} className="rejilla" />
          <text x={x0 - 6} y={y(t)} dy="0.32em" textAnchor="end">
            {formatearEje(t)}
          </text>
        </g>
      ))}
      {etiqueta ? (
        <text className="titulo-eje" transform={`translate(12 ${alto / 2}) rotate(-90)`} textAnchor="middle">
          {etiqueta}
        </text>
      ) : null}
    </g>
  );
}

function indicesEtiqueta(n: number, max = 6): number[] {
  if (n <= max) return Array.from({ length: n }, (_, i) => i);
  const paso = (n - 1) / (max - 1);
  return Array.from({ length: max }, (_, i) => Math.round(i * paso));
}

function Dispersion({ series, etiquetaX, etiquetaY, titulo }: { series: SerieDispersion[]; etiquetaX?: string; etiquetaY?: string; titulo: string }) {
  const alto = 320;
  const xs = series.flatMap((s) => s.x), ys = series.flatMap((s) => s.valores);
  const tx = marcas(Math.min(...xs), Math.max(...xs)), ty = marcas(Math.min(...ys), Math.max(...ys));
  const [x0, x1, y0, y1] = [tx[0], tx[tx.length - 1], ty[0], ty[ty.length - 1]];
  const px = (v: number) => M.izquierda + ((v - x0) / (x1 - x0 || 1)) * (W - M.izquierda - M.derecha);
  const py = (v: number) => alto - M.abajo - ((v - y0) / (y1 - y0 || 1)) * (alto - M.arriba - M.abajo);
  return (
    <>
      <Svg alto={alto} titulo={titulo}>
        <EjeY ticks={ty} y={py} x0={M.izquierda} x1={W - M.derecha} etiqueta={etiquetaY} alto={alto} />
        <g className="eje">
          {tx.map((t) => (
            <g key={t}>
              <line x1={px(t)} x2={px(t)} y1={M.arriba} y2={alto - M.abajo} className="rejilla" />
              <text x={px(t)} y={alto - M.abajo + 18} textAnchor="middle">
                {formatearEje(t)}
              </text>
            </g>
          ))}
          {etiquetaX ? (
            <text className="titulo-eje" x={(M.izquierda + W - M.derecha) / 2} y={alto - 8} textAnchor="middle">
              {etiquetaX}
            </text>
          ) : null}
        </g>
        {series.map((s, si) => (
          <g key={s.nombre + si} className={`serie c${(si % COLORES) + 1}`}>
            {s.valores.map((v, i) => (
              <circle key={i} cx={px(s.x[i])} cy={py(v)} r={3} className="punto punto-disp">
                <title>{`${legible(s.nombre)}: (${formatear(s.x[i])}, ${formatear(v)})`}</title>
              </circle>
            ))}
          </g>
        ))}
      </Svg>
      <Leyenda nombres={series.map((s) => `${s.nombre} (n = ${s.valores.length})`)} />
    </>
  );
}

function Lineas({ x, series, etiquetaX, etiquetaY, titulo, soloPuntos = false }: {
  x: (number | string)[]; series: SerieXY[]; etiquetaX?: string; etiquetaY?: string; titulo: string; soloPuntos?: boolean;
}) {
  const alto = 300;
  const todos = series.flatMap((s) => s.valores).filter((v): v is number => v !== null);
  const ticks = marcas(Math.min(0, ...todos), Math.max(...todos));
  const [y0, y1] = [ticks[0], ticks[ticks.length - 1]];
  const px = (i: number) => M.izquierda + (x.length === 1 ? 0.5 : i / (x.length - 1)) * (W - M.izquierda - M.derecha);
  const py = (v: number) => alto - M.abajo - ((v - y0) / (y1 - y0 || 1)) * (alto - M.arriba - M.abajo);
  const puntosVisibles = soloPuntos || x.length <= 40;
  return (
    <>
      <Svg alto={alto} titulo={titulo}>
        <EjeY ticks={ticks} y={py} x0={M.izquierda} x1={W - M.derecha} etiqueta={etiquetaY} alto={alto} />
        <g className="eje">
          {indicesEtiqueta(x.length).map((i) => (
            <text key={i} x={px(i)} y={alto - M.abajo + 18} textAnchor="middle">
              {typeof x[i] === "number" ? formatearEje(x[i] as number) : String(x[i])}
            </text>
          ))}
          {etiquetaX ? (
            <text className="titulo-eje" x={(M.izquierda + W - M.derecha) / 2} y={alto - 8} textAnchor="middle">
              {etiquetaX}
            </text>
          ) : null}
        </g>
        {series.map((s, si) => {
          const segmentos: string[] = [];
          let actual = "";
          s.valores.forEach((v, i) => {
            if (v === null) {
              if (actual) segmentos.push(actual);
              actual = "";
            } else actual += `${actual ? "L" : "M"}${px(i).toFixed(1)},${py(v).toFixed(1)}`;
          });
          if (actual) segmentos.push(actual);
          const clase = `c${(si % COLORES) + 1}`;
          return (
            <g key={s.nombre + si} className={`serie ${clase}`}>
              {!soloPuntos && segmentos.map((d, k) => <path key={k} d={d} className="trazo" />)}
              {puntosVisibles &&
                s.valores.map((v, i) =>
                  v === null ? null : (
                    <circle key={i} cx={px(i)} cy={py(v)} r={soloPuntos ? 3.5 : 2.5} className="punto">
                      <title>{`${legible(s.nombre)} · ${String(x[i])}: ${formatear(v)}`}</title>
                    </circle>
                  ),
                )}
            </g>
          );
        })}
      </Svg>
      <Leyenda nombres={series.map((s) => s.nombre)} />
    </>
  );
}

function BarrasHorizontales({ x, series, etiquetaY, titulo }: { x: (number | string)[]; series: SerieXY[]; etiquetaY?: string; titulo: string }) {
  const banda = 18 * series.length + 10;
  const izq = 130;
  const alto = M.arriba + banda * x.length + 40;
  const todos = series.flatMap((s) => s.valores).filter((v): v is number => v !== null);
  const ticks = marcas(Math.min(0, ...todos), Math.max(0, ...todos), 4);
  const [v0, v1] = [ticks[0], ticks[ticks.length - 1]];
  const pv = (v: number) => izq + ((v - v0) / (v1 - v0 || 1)) * (W - izq - M.derecha - 40);
  const base = alto - 40;
  return (
    <>
      <Svg alto={alto} titulo={titulo}>
        <g className="eje">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={pv(t)} x2={pv(t)} y1={M.arriba} y2={base} className="rejilla" />
              <text x={pv(t)} y={base + 16} textAnchor="middle">
                {formatearEje(t)}
              </text>
            </g>
          ))}
          {etiquetaY ? (
            <text className="titulo-eje" x={(izq + W) / 2} y={alto - 4} textAnchor="middle">
              {etiquetaY}
            </text>
          ) : null}
        </g>
        {x.map((cat, i) => {
          const y = M.arriba + i * banda;
          return (
            <g key={String(cat) + i}>
              <text className="etiqueta-cat" x={izq - 8} y={y + banda / 2 - 2} dy="0.32em" textAnchor="end">
                {recortar(legible(String(cat)), 18)}
              </text>
              {series.map((s, si) => {
                const v = s.valores[i];
                if (v === null) return null;
                const a = pv(Math.min(0, v)), b = pv(Math.max(0, v));
                const yy = y + 3 + si * 18;
                return (
                  <g key={si} className={`serie c${(si % COLORES) + 1}`}>
                    <rect x={a} y={yy} width={Math.max(1, b - a)} height={15} rx={2} className="barra">
                      <title>{`${legible(String(cat))}${series.length > 1 ? ` · ${legible(s.nombre)}` : ""}: ${formatear(v)}`}</title>
                    </rect>
                    <text className="valor-barra" x={b + 4} y={yy + 7.5} dy="0.32em">
                      {formatear(v)}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </Svg>
      <Leyenda nombres={series.map((s) => s.nombre)} />
    </>
  );
}

function Histograma({ x, serie, etiquetaX, etiquetaY, titulo }: { x: (number | string)[]; serie: SerieXY; etiquetaX?: string; etiquetaY?: string; titulo: string }) {
  const alto = 300;
  const vals = serie.valores.map((v) => v ?? 0);
  const ticks = marcas(0, Math.max(...vals));
  const y1 = ticks[ticks.length - 1];
  const ancho = (W - M.izquierda - M.derecha) / x.length;
  const py = (v: number) => alto - M.abajo - (v / (y1 || 1)) * (alto - M.arriba - M.abajo);
  return (
    <Svg alto={alto} titulo={titulo}>
      <EjeY ticks={ticks} y={py} x0={M.izquierda} x1={W - M.derecha} etiqueta={etiquetaY} alto={alto} />
      <g className="serie c1">
        {vals.map((v, i) => (
          <rect key={i} x={M.izquierda + i * ancho + 0.5} y={py(v)} width={Math.max(1, ancho - 1)} height={alto - M.abajo - py(v)} className="barra">
            <title>{`${String(x[i])}: ${formatear(v)}`}</title>
          </rect>
        ))}
      </g>
      <g className="eje">
        {indicesEtiqueta(x.length, 4).map((i) => (
          <text key={i} x={M.izquierda + (i + 0.5) * ancho} y={alto - M.abajo + 18} textAnchor="middle">
            {String(x[i])}
          </text>
        ))}
        {etiquetaX ? (
          <text className="titulo-eje" x={(M.izquierda + W - M.derecha) / 2} y={alto - 8} textAnchor="middle">
            {etiquetaX}
          </text>
        ) : null}
      </g>
    </Svg>
  );
}

function Cajas({ series, etiqueta, titulo }: { series: SerieCaja[]; etiqueta?: string; titulo: string }) {
  const banda = 44, izq = 120;
  const alto = M.arriba + banda * series.length + 44;
  const todos = series.flatMap((s) => [s.min, s.max, ...s.atipicos]);
  const ticks = marcas(Math.min(...todos), Math.max(...todos), 5);
  const [v0, v1] = [ticks[0], ticks[ticks.length - 1]];
  const pv = (v: number) => izq + ((v - v0) / (v1 - v0 || 1)) * (W - izq - M.derecha);
  const base = alto - 44;
  return (
    <Svg alto={alto} titulo={titulo}>
      <g className="eje">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pv(t)} x2={pv(t)} y1={M.arriba} y2={base} className="rejilla" />
            <text x={pv(t)} y={base + 16} textAnchor="middle">
              {formatearEje(t)}
            </text>
          </g>
        ))}
        {etiqueta ? (
          <text className="titulo-eje" x={(izq + W) / 2} y={alto - 6} textAnchor="middle">
            {etiqueta}
          </text>
        ) : null}
      </g>
      {series.map((s, i) => {
        const cy = M.arriba + i * banda + banda / 2;
        return (
          <g key={s.nombre + i} className="serie c1">
            <text className="etiqueta-cat" x={izq - 8} y={cy} dy="0.32em" textAnchor="end">
              {recortar(legible(s.nombre), 16)}
            </text>
            <line x1={pv(s.min)} x2={pv(s.q1)} y1={cy} y2={cy} className="bigote" />
            <line x1={pv(s.q3)} x2={pv(s.max)} y1={cy} y2={cy} className="bigote" />
            <line x1={pv(s.min)} x2={pv(s.min)} y1={cy - 7} y2={cy + 7} className="bigote" />
            <line x1={pv(s.max)} x2={pv(s.max)} y1={cy - 7} y2={cy + 7} className="bigote" />
            <rect x={pv(s.q1)} y={cy - 12} width={Math.max(1, pv(s.q3) - pv(s.q1))} height={24} className="caja" rx={2}>
              <title>{`${legible(s.nombre)}${s.n ? ` (n = ${formatear(s.n)})` : ""} · Q1 ${formatear(s.q1)} · mediana ${formatear(s.mediana)} · Q3 ${formatear(s.q3)}`}</title>
            </rect>
            <line x1={pv(s.mediana)} x2={pv(s.mediana)} y1={cy - 12} y2={cy + 12} className="mediana" />
            {s.atipicos.map((a, k) => (
              <circle key={k} cx={pv(a)} cy={cy} r={2.2} className="atipico" />
            ))}
          </g>
        );
      })}
    </Svg>
  );
}

const compacto = new Intl.NumberFormat("es-MX", { notation: "compact", maximumFractionDigits: 1 });

/** Marcas de eje: 800 mil en lugar de 800,000 para que no se encimen. */
function formatearEje(v: number): string {
  return Math.abs(v) >= 10000 ? compacto.format(v) : formatear(v);
}

function recortar(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

// ------------------------------------------------------------------ tabla
export function Tabla({ filas }: { filas: Fila[] }) {
  const columnas = Array.from(new Set(filas.flatMap((f) => Object.keys(f))));
  return (
    <div className="tabla-contenedor" tabIndex={0} role="region" aria-label="Tabla de datos">
      <table>
        <thead>
          <tr>
            {columnas.map((c) => (
              <th key={c} scope="col">
                {legible(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i}>
              {columnas.map((c) => (
                <td key={c} className={typeof f[c] === "number" ? "num" : undefined}>
                  {formatear(f[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
