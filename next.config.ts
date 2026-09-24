import type { NextConfig } from "next";

// /api/* lo atiende FastAPI (api/index.py). Patrón de la plantilla oficial
// "Next.js + FastAPI Starter" de Vercel:
// - desarrollo: Next reenvía a uvicorn en 127.0.0.1:8000 (`npm run api:dev`);
// - producción: Next reenvía a la función Python /api (api/index.py) y FastAPI
//   recibe la ruta original (/api/salud, /api/triage, ...).
// HIPÓTESIS hasta el primer despliegue en la Vercel de Emilio: verificar con
// GET /api/salud y GET /api/no-existe (debe dar 404 en español desde FastAPI).
const enDesarrollo = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  // Evita que `next dev` genere AGENTS.md/CLAUDE.md y pise el CLAUDE.md del proyecto.
  agentRules: false,
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: enDesarrollo ? "http://127.0.0.1:8000/api/:path*" : "/api/",
      },
    ];
  },
};

export default nextConfig;
