import type { Metadata } from "next";

import { FormAgente, FormRag, FormTriage } from "../_componentes/Asistente.tsx";
import PaginaModulos from "../_componentes/PaginaModulos.tsx";

export const revalidate = 300;
export const metadata: Metadata = { title: "Asistente IA" };

export default function Pagina() {
  return (
    <PaginaModulos
      pagina="/asistente"
      titulo="Asistente IA"
      intro={
        <p>
          Tres herramientas sobre la API de Python: el <strong>triage</strong> resume y prioriza una queja (el LLM solo redacta; la
          categoría la da el modelo de NLP y la prioridad, reglas declaradas) y el <strong>asistente de documentos</strong> (RAG)
          responde con fuentes o dice que no encontró evidencia, sin inventar. El <strong>agente</strong> decide qué herramientas usar
          (hasta 5 pasos) y muestra cada paso.
        </p>
      }
    >
      <section className="modulo" aria-labelledby="t-triage">
        <div className="modulo-cabecera">
          <h2 id="t-triage">Triage de quejas</h2>
          <span className="bloque">POST /api/triage</span>
        </div>
        <FormTriage />
      </section>
      <section className="modulo" aria-labelledby="t-rag">
        <div className="modulo-cabecera">
          <h2 id="t-rag">Preguntar a los documentos (RAG)</h2>
          <span className="bloque">POST /api/rag</span>
        </div>
        <FormRag />
      </section>
      <section className="modulo" aria-labelledby="t-agente">
        <div className="modulo-cabecera">
          <h2 id="t-agente">Agente con herramientas</h2>
          <span className="bloque">POST /api/agente · Bloque N</span>
        </div>
        <FormAgente />
      </section>
    </PaginaModulos>
  );
}
