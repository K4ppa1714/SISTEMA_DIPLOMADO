import Link from "next/link";

import EstadoApi from "./_componentes/EstadoApi.tsx";
import { MODULOS, PAGINAS } from "./_lib/modulos.ts";
import { leerResultados } from "./_lib/resultados.ts";

export const revalidate = 300;

export default async function Inicio() {
  const lectura = await leerResultados(MODULOS.map((m) => m.id));
  const porModulo = new Map<string, { n: number; validados: number; versiones: Set<string> }>();
  if (lectura.ok) {
    for (const r of lectura.filas) {
      const e = porModulo.get(r.modulo) ?? { n: 0, validados: 0, versiones: new Set<string>() };
      e.n += 1;
      if (r.validado_por) e.validados += 1;
      e.versiones.add(r.version);
      porModulo.set(r.modulo, e);
    }
  }
  return (
    <>
      <header className="encabezado-pagina">
        <h1>Operaguas Analítica</h1>
        <div className="intro">
          <p>
            Capa de análisis de datos e IA para un organismo operador de agua. Responde tres preguntas de la dirección y del área de
            atención de Operaguas de Huimilpan:
          </p>
          <ol className="preguntas">
            <li>
              <strong>¿Qué recibos no se pagarán a tiempo?</strong> → <Link href="/modelos">Modelos</Link>
            </li>
            <li>
              <strong>¿Dónde hay consumos anómalos (fugas, cortes)?</strong> → <Link href="/temporal">Temporal</Link>
            </li>
            <li>
              <strong>¿Cómo atender más rápido las quejas?</strong> → <Link href="/quejas">Quejas</Link> y{" "}
              <Link href="/asistente">Asistente IA</Link>
            </li>
          </ol>
          <p className="nota">
            Todo el cálculo está en Python: el pipeline publica los resultados en Supabase y la API (FastAPI) atiende lo que depende de
            cada pregunta. Los datos son una simulación declarada, sin datos personales.
          </p>
        </div>
        <EstadoApi />
      </header>

      <section className="modulo" aria-labelledby="t-estado">
        <div className="modulo-cabecera">
          <h2 id="t-estado">Estado de los módulos</h2>
        </div>
        {!lectura.ok ? (
          <div className="aviso aviso-error" role="alert">
            <strong>No se pudieron leer los resultados.</strong> {lectura.motivo}
          </div>
        ) : (
          <div className="tabla-contenedor" tabIndex={0} role="region" aria-label="Estado de los módulos">
            <table>
              <thead>
                <tr>
                  <th scope="col">Módulo</th>
                  <th scope="col">Bloque</th>
                  <th scope="col">Resultados</th>
                  <th scope="col">Versión</th>
                  <th scope="col">Validados</th>
                  <th scope="col">Página</th>
                </tr>
              </thead>
              <tbody>
                {MODULOS.map((m) => {
                  const e = porModulo.get(m.id);
                  const pagina = PAGINAS.find((p) => p.ruta === m.pagina);
                  return (
                    <tr key={m.id} className={e ? undefined : "apagado"}>
                      <th scope="row">{m.nombre}</th>
                      <td>{m.bloque}</td>
                      <td className="num">{e?.n ?? 0}</td>
                      <td>{e ? [...e.versiones].sort().join(", ") : "pendiente"}</td>
                      <td className="num">{e ? `${e.validados} de ${e.n}` : "—"}</td>
                      <td>
                        <Link href={e ? `${m.pagina}#m-${m.id}` : m.pagina}>{pagina?.nombre}</Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
