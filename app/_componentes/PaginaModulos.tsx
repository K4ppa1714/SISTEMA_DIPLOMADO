// Sección de una página con los resultados vigentes de uno o varios módulos.
import type { ReactNode } from "react";

import { modulosDe, type Modulo } from "../_lib/modulos.ts";
import { leerResultados } from "../_lib/resultados.ts";
import Resultado from "./Resultado.tsx";

export default async function PaginaModulos({ pagina, titulo, intro, children }: {
  pagina: string;
  titulo: string;
  intro: ReactNode;
  children?: ReactNode;
}) {
  const modulos = modulosDe(pagina);
  const lectura = await leerResultados(modulos.map((m) => m.id));
  return (
    <>
      <header className="encabezado-pagina">
        <h1>{titulo}</h1>
        <div className="intro">{intro}</div>
        {modulos.length > 1 ? (
          <nav className="indice" aria-label="Módulos de esta página">
            {modulos.map((m) => (
              <a key={m.id} href={`#m-${m.id}`}>
                {m.nombre}
              </a>
            ))}
          </nav>
        ) : null}
      </header>
      {children}
      {!lectura.ok ? (
        <div className="aviso aviso-error" role="alert">
          <strong>No se pudieron leer los resultados.</strong> {lectura.motivo}
        </div>
      ) : (
        <>
          {lectura.origen === "muestra" ? (
            <div className="aviso">Modo de desarrollo: resultados de muestra (RESULTADOS_MUESTRA=1), no de Supabase.</div>
          ) : null}
          {modulos.map((m) => (
            <SeccionModulo key={m.id} m={m} filas={lectura.filas.filter((r) => r.modulo === m.id)} />
          ))}
        </>
      )}
    </>
  );
}

function SeccionModulo({ m, filas }: { m: Modulo; filas: Parameters<typeof Resultado>[0]["r"][] }) {
  return (
    <section className="modulo" id={`m-${m.id}`} aria-labelledby={`t-${m.id}`}>
      <div className="modulo-cabecera">
        <h2 id={`t-${m.id}`}>{m.nombre}</h2>
        <span className="bloque" title="Bloque de la rúbrica">
          Bloque {m.bloque}
        </span>
      </div>
      <p className="modulo-que">{m.que}</p>
      {filas.length === 0 ? (
        <p className="vacio">Todavía no hay resultados publicados para este módulo.</p>
      ) : (
        <div className="rejilla-tarjetas">
          {filas.map((r) => (
            <Resultado key={`${r.modulo}/${r.clave}`} r={r} />
          ))}
        </div>
      )}
    </section>
  );
}
