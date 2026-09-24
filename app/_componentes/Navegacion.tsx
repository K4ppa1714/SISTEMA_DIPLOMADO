"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { PAGINAS } from "../_lib/modulos.ts";

export default function Navegacion() {
  const ruta = usePathname();
  return (
    <nav aria-label="Secciones" className="nav">
      <ul>
        {PAGINAS.map((p) => (
          <li key={p.ruta}>
            <Link href={p.ruta} aria-current={ruta === p.ruta ? "page" : undefined}>
              {p.nombre}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
