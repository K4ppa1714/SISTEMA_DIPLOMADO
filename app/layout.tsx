import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import Navegacion from "./_componentes/Navegacion.tsx";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Operaguas Analítica", template: "%s · Operaguas Analítica" },
  description:
    "Análisis de datos e IA sobre una simulación declarada de Operaguas de Huimilpan: pago tardío, fugas y quejas. Proyecto final del Diplomado de Python y Análisis de Datos.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f8fa" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1419" },
  ],
};

export default function RaizLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es-MX">
      <body>
        <a className="saltar" href="#contenido">
          Saltar al contenido
        </a>
        <header className="barra">
          <div className="barra-interior">
            <a className="marca" href="/">
              <span aria-hidden>💧</span> Operaguas Analítica
            </a>
            <Navegacion />
          </div>
        </header>
        <main id="contenido" className="contenido">
          {children}
        </main>
        <footer className="pie">
          <p>
            Datos: <strong>simulación declarada</strong> con la estructura de Operaguas de Huimilpan, sin datos personales. No es el
            sistema en producción de Operaguas.
          </p>
          <p>Proyecto final · Diplomado de Python y Análisis de Datos · Universidad Marista, 2026.</p>
        </footer>
      </body>
    </html>
  );
}
