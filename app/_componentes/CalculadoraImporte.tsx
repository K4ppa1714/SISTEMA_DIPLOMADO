"use client";

import { useState, type FormEvent } from "react";

import { llamarApi } from "./cliente-api.ts";

// Mismos tipos que api/_lib/tarifas.py (CONTRATOS §5).
const TIPOS = [
  "domestico_medio", "domestico_economico", "domestico_alto", "domestico_apoyo", "domestico_rural",
  "comercial", "industrial", "beneficencia", "pecuaria", "publico_concesionado", "publico_oficial",
];

interface Importe {
  periodo: string;
  consumo_facturado: number;
  agua: number;
  alcantarillado: number;
  saneamiento: number;
  subtotal: number;
  iva: number;
  total: number;
}

const mxn = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });

/** GET /api/importe: el cálculo lo hace Python con el tarifario CEA (T-03). */
export default function CalculadoraImporte() {
  const [tipo, setTipo] = useState(TIPOS[0]);
  const [consumo, setConsumo] = useState("18");
  const [alc, setAlc] = useState(true);
  const [san, setSan] = useState(true);
  const [res, setRes] = useState<{ datos?: Importe; error?: string } | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function calcular(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    const q = new URLSearchParams({ tipo_tarifa: tipo, consumo_m3: consumo, alcantarillado: String(alc), saneamiento: String(san) });
    const r = await llamarApi<Importe>(`/api/importe?${q}`);
    setRes(r.ok ? { datos: r.datos } : { error: r.mensaje });
    setEnviando(false);
  }

  return (
    <form className="formulario formulario-rejilla" onSubmit={calcular}>
      <div>
        <label htmlFor="tipo">Tipo de tarifa</label>
        <select id="tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          {TIPOS.map((t) => (
            <option key={t} value={t}>
              {t.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="consumo">Consumo (m³)</label>
        <input id="consumo" type="number" min={0} step="0.1" inputMode="decimal" required value={consumo} onChange={(e) => setConsumo(e.target.value)} />
      </div>
      <fieldset>
        <legend>Servicios</legend>
        <label className="casilla">
          <input type="checkbox" checked={alc} onChange={(e) => setAlc(e.target.checked)} /> Alcantarillado
        </label>
        <label className="casilla">
          <input type="checkbox" checked={san} onChange={(e) => setSan(e.target.checked)} /> Saneamiento
        </label>
      </fieldset>
      <button type="submit" disabled={enviando}>
        {enviando ? "Calculando…" : "Calcular importe"}
      </button>
      <div aria-live="polite" className="ancho">
        {res?.error ? <p className="aviso aviso-error">{res.error}</p> : null}
        {res?.datos ? (
          <dl className="respuesta-api">
            <div>
              <dt>Consumo facturado</dt>
              <dd>{res.datos.consumo_facturado} m³</dd>
            </div>
            <div>
              <dt>Agua</dt>
              <dd>{mxn.format(res.datos.agua)}</dd>
            </div>
            <div>
              <dt>Alcantarillado</dt>
              <dd>{mxn.format(res.datos.alcantarillado)}</dd>
            </div>
            <div>
              <dt>Saneamiento</dt>
              <dd>{mxn.format(res.datos.saneamiento)}</dd>
            </div>
            <div>
              <dt>IVA</dt>
              <dd>{mxn.format(res.datos.iva)}</dd>
            </div>
            <div>
              <dt>Total ({res.datos.periodo})</dt>
              <dd className="total">{mxn.format(res.datos.total)}</dd>
            </div>
          </dl>
        ) : null}
      </div>
    </form>
  );
}
