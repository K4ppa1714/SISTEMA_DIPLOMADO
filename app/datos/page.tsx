import type { Metadata } from "next";

import PaginaModulos from "../_componentes/PaginaModulos.tsx";

export const revalidate = 300;
export const metadata: Metadata = { title: "Datos y EDA" };

export default function Pagina() {
  return (
    <PaginaModulos
      pagina="/datos"
      titulo="Datos, exploración y estadística"
      intro={
        <p>
          Qué datos se usaron, cómo se limpiaron y qué muestran: distribuciones de consumo e importe, cartera vencida y quejas, y las
          pruebas estadísticas que sostienen las conclusiones. Todo se calcula en <code>pipeline/</code> (Python) y se publica en
          Supabase; esta página solo lo presenta.
        </p>
      }
    />
  );
}
