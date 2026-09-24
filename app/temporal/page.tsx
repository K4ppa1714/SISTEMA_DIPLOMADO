import type { Metadata } from "next";

import PaginaModulos from "../_componentes/PaginaModulos.tsx";

export const revalidate = 300;
export const metadata: Metadata = { title: "Temporal y espectral" };

export default function Pagina() {
  return (
    <PaginaModulos
      pagina="/temporal"
      titulo="Series de tiempo, Fourier y Wavelets"
      intro={
        <p>
          El consumo tiene ritmos (día, semana, año) y rupturas (fugas, cortes). Las series de tiempo describen la tendencia y la
          estacionalidad; Fourier encuentra los periodos dominantes del consumo horario; la transformada Wavelet localiza en el tiempo
          los cambios de energía que delatan una fuga.
        </p>
      }
    />
  );
}
