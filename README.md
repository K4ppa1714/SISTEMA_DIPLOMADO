# Operaguas Analítica

Proyecto final del **Diplomado de Python y Análisis de Datos** — Universidad Marista, 2026.

> Estado: en construcción. Entrega: viernes 25 de septiembre de 2026.
> Este README se completa en la tarea T-21 con los 18 puntos que exige el PDF (`docs/RUBRICA.md`).

## 1. Integrantes

- Emilio Rico Hernández
- Andrés

## 2. Problema

Operaguas de Huimilpan, organismo operador de agua, necesita (1) anticipar qué recibos no se pagarán a tiempo, (2) detectar consumos anómalos como fugas o cortes y (3) atender más rápido las quejas de los usuarios.

## 3. Objetivo

Construir una aplicación desplegada en la nube que integre análisis de datos, estadística, series de tiempo, machine learning, deep learning, NLP, LLM, RAG, agentes, Fourier y Wavelets para apoyar esas tres decisiones.

## 4. Arquitectura

```
data/simulados ──▶ pipeline/ (Python) ──▶ Supabase (analitica, rag, agente)
                                              ▲
                  app/ (Next.js) ──▶ api/ (FastAPI) ──▶ LLM
                  └────────── un solo proyecto de Vercel ──────────┘
```

Detalle en `CLAUDE.md` y `docs/CONTRATOS.md`.

## 5–18. Pendientes (T-21)

Stack tecnológico · fuente de datos · módulos · modelos · métricas · Fourier/Wavelets · LLM/RAG/Agentes · instrucciones de desarrollo · variables de entorno · enlace a la app · capturas · limitaciones · trabajo futuro.

## Fuente de datos

Simulación declarada que reproduce la estructura del sistema de Operaguas, sin datos personales. Ver `data/README.md`.

## Cómo trabajamos

- `CLAUDE.md`: contexto, reglas y propiedad de carpetas.
- `docs/RUBRICA.md`: lo que se califica.
- `docs/TAREAS.md`: tareas, responsables y estado.
- `docs/COMUNICACION.md`: coordinación entre integrantes y sus asistentes de IA.
- `docs/DECISIONES.md`: decisiones tomadas.

## Uso de IA en el desarrollo

El proyecto se desarrolla con asistencia de Claude (Anthropic) en dos sesiones coordinadas, una por integrante. Cada integrante valida las conclusiones, las métricas y los conjuntos de evaluación antes de que entren al reporte. Cada PR indica si se generó con asistencia de IA. Detalle en `docs/COMUNICACION.md`.
