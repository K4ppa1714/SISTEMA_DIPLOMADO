import type { Metadata } from "next";

import PaginaModulos from "../_componentes/PaginaModulos.tsx";

export const revalidate = 300;
export const metadata: Metadata = { title: "Quejas" };

export default function Pagina() {
  return (
    <PaginaModulos
      pagina="/quejas"
      titulo="Quejas: clasificación y similitud"
      intro={
        <p>
          Atender más rápido empieza por saber de qué trata cada queja. Un clasificador TF-IDF + regresión logística asigna la
          categoría; se evalúa separando por <strong>texto único</strong> para no inflar la métrica con textos repetidos. Los
          embeddings buscan quejas parecidas.
        </p>
      }
    />
  );
}
