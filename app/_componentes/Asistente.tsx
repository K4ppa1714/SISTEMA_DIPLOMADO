"use client";

import { useState, type FormEvent } from "react";

import { llamarApi } from "./cliente-api.ts";

const NOMBRE_PRIORIDAD = ["baja", "normal", "alta", "urgente"];

interface Triage {
  resumen: string;
  categoria: string;
  prioridad: number;
  valido: boolean;
}

interface Rag {
  respuesta: string;
  evidencia: boolean;
  fuentes: { titulo: string; fragmento: string; similitud: number }[];
}

/** POST /api/triage: resumen, categoría y prioridad de una queja (T-12). */
export function FormTriage() {
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [res, setRes] = useState<{ datos?: Triage; error?: string } | null>(null);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setRes(null);
    const r = await llamarApi<Triage>("/api/triage", { method: "POST", body: JSON.stringify({ texto }) });
    setRes(r.ok ? { datos: r.datos } : { error: r.mensaje });
    setEnviando(false);
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <label htmlFor="queja">Texto de la queja</label>
      <textarea
        id="queja"
        rows={4}
        maxLength={2000}
        required
        minLength={5}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        placeholder="Ej.: Desde ayer no llega agua a la colonia y hay adultos mayores en casa."
      />
      <p className="ayuda">No escribas nombres, teléfonos ni domicilios: la API oculta correos y números largos antes de enviarlo al LLM.</p>
      <button type="submit" disabled={enviando || texto.trim().length < 5}>
        {enviando ? "Clasificando…" : "Clasificar queja"}
      </button>
      <div aria-live="polite">
        {res?.error ? <p className="aviso aviso-error">{res.error}</p> : null}
        {res?.datos ? (
          <dl className="respuesta-api">
            <div>
              <dt>Categoría (modelo TF-IDF de T-14)</dt>
              <dd>{res.datos.categoria.replace(/_/g, " ")}</dd>
            </div>
            <div>
              <dt>Prioridad (reglas declaradas)</dt>
              <dd>
                {res.datos.prioridad} · {NOMBRE_PRIORIDAD[res.datos.prioridad] ?? "—"}
              </dd>
            </div>
            <div className="ancho">
              <dt>Resumen</dt>
              <dd>{res.datos.resumen}</dd>
            </div>
            <div className="ancho">
              <dt>¿Salida validada?</dt>
              <dd>
                {res.datos.valido
                  ? "Sí: el LLM respondió JSON válido y su categoría coincide con la del modelo."
                  : "No: el LLM no respondió, su salida no pasó la validación o no coincidió con el modelo. El resumen puede ser el texto recortado."}
              </dd>
            </div>
          </dl>
        ) : null}
      </div>
    </form>
  );
}

/** POST /api/rag: respuesta con fuentes o "sin evidencia" (T-11). */
export function FormRag() {
  const [pregunta, setPregunta] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [res, setRes] = useState<{ datos?: Rag; error?: string } | null>(null);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setRes(null);
    const r = await llamarApi<Rag>("/api/rag", { method: "POST", body: JSON.stringify({ pregunta, k: 5 }) });
    setRes(r.ok ? { datos: r.datos } : { error: r.mensaje });
    setEnviando(false);
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <label htmlFor="pregunta">Pregunta sobre tarifas, recibos o el proyecto</label>
      <input
        id="pregunta"
        type="text"
        maxLength={500}
        minLength={3}
        required
        value={pregunta}
        onChange={(e) => setPregunta(e.target.value)}
        placeholder="Ej.: ¿Qué porcentaje se cobra por alcantarillado?"
      />
      <button type="submit" disabled={enviando || pregunta.trim().length < 3}>
        {enviando ? "Buscando…" : "Preguntar"}
      </button>
      <div aria-live="polite">
        {res?.error ? <p className="aviso aviso-error">{res.error}</p> : null}
        {res?.datos ? (
          <div className="respuesta-api">
            <p className={res.datos.evidencia ? "" : "sin-evidencia"}>{res.datos.respuesta}</p>
            {res.datos.fuentes.length > 0 ? (
              <ol className="fuentes">
                {res.datos.fuentes.map((f, i) => (
                  <li key={i}>
                    <strong>{f.titulo}</strong> <span className="similitud">similitud {f.similitud.toFixed(2)}</span>
                    <blockquote>{f.fragmento.length > 400 ? f.fragmento.slice(0, 399) + "…" : f.fragmento}</blockquote>
                  </li>
                ))}
              </ol>
            ) : null}
          </div>
        ) : null}
      </div>
    </form>
  );
}
