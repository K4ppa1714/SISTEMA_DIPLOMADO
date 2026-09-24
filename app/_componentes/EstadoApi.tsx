"use client";

import { useEffect, useState } from "react";

import { llamarApi } from "./cliente-api.ts";

interface Salud {
  ok: boolean;
  supabase: boolean;
  llm: boolean;
  version: string;
}

/** Muestra GET /api/salud: confirma en vivo que la función de Python responde. */
export default function EstadoApi() {
  const [estado, setEstado] = useState<{ cargando: true } | { cargando: false; salud?: Salud; error?: string }>({ cargando: true });

  useEffect(() => {
    let vivo = true;
    llamarApi<Salud>("/api/salud", undefined, 10000).then((r) => {
      if (vivo) setEstado(r.ok ? { cargando: false, salud: r.datos } : { cargando: false, error: r.mensaje });
    });
    return () => {
      vivo = false;
    };
  }, []);

  if (estado.cargando) return <p className="estado-api">Consultando /api/salud…</p>;
  if (estado.error || !estado.salud) {
    return (
      <p className="estado-api estado-mal" role="status">
        API de Python: sin respuesta ({estado.error})
      </p>
    );
  }
  const s = estado.salud;
  return (
    <ul className="estado-api" role="status" aria-label="Estado de la API">
      <li className={s.ok ? "estado-bien" : "estado-mal"}>API {s.version}: {s.ok ? "operando" : "incompleta"}</li>
      <li className={s.supabase ? "estado-bien" : "estado-mal"}>Supabase: {s.supabase ? "responde" : "sin conexión"}</li>
      <li className={s.llm ? "estado-bien" : "estado-mal"}>LLM: {s.llm ? "configurado" : "sin configurar"}</li>
    </ul>
  );
}
