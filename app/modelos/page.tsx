import type { Metadata } from "next";

import CalculadoraImporte from "../_componentes/CalculadoraImporte.tsx";
import PaginaModulos from "../_componentes/PaginaModulos.tsx";

export const revalidate = 300;
export const metadata: Metadata = { title: "Modelos" };

export default function Pagina() {
  return (
    <PaginaModulos
      pagina="/modelos"
      titulo="Modelos de pago tardío"
      intro={
        <p>
          ¿Qué recibos no se pagarán a tiempo? Se comparan modelos con separación temporal (nada del futuro entra al entrenamiento), se
          elige el umbral y se revisan los errores por segmento. Las predicciones se calculan por lotes en Python y se guardan en{" "}
          <code>analitica.predicciones_pago</code>; la API no carga scikit-learn.
        </p>
      }
    >
      <section className="modulo" aria-labelledby="t-importe">
        <div className="modulo-cabecera">
          <h2 id="t-importe">Calculadora de importe (tarifario CEA)</h2>
          <span className="bloque">API · Python</span>
        </div>
        <p className="modulo-que">
          Llama a <code>GET /api/importe</code>, que usa <code>api/_lib/tarifas.py</code>: las reglas del recibo portadas de Odoo.
        </p>
        <CalculadoraImporte />
      </section>
    </PaginaModulos>
  );
}
