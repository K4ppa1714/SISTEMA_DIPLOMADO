# Requisitos de calificación

Resumen fiel del PDF "Proyecto Final — Diplomado de Python y Análisis de
Datos" (Universidad Marista, 2026). **Es la vara con la que se mide cada
tarea.** Si una tarea no produce la evidencia que aquí se pide, no está
terminada. La columna "Tarea" remite a `docs/TAREAS.md`.

## Regla principal: integración real

Cada componente debe: (1) resolver una necesidad real del proyecto,
(2) estar conectado al flujo general, (3) tener justificación técnica,
(4) producir un resultado observable, (5) incluir métrica, prueba o
evidencia, y (6) documentarse en el README y en el reporte técnico.

No basta escribir "se utilizó RAG": hay que mostrar **dónde, por qué, cómo,
con qué datos y con qué resultado**.

## Requisitos por bloque

| Bloque | Pts | Mínimos obligatorios | Evidencia esperada | Tarea |
|---|---|---|---|---|
| Problema y objetivos | 5 | Problema, usuario, objetivo general y específicos, valor | Claridad, utilidad y coherencia | T-01, T-20 |
| A. Python, datos, Pandas | 7 | Carga desde fuente; Pandas; inspección de estructura y tipos; nulos; duplicados; atípicos con razonamiento; transformación; `merge`/`join`; dataset final reproducible | Sección **"Pipeline de Datos"** en la app o el reporte: de dónde llegan los datos y cómo se transforman | T-04 |
| B. EDA y visualización | 6 | Descriptivos, distribuciones, relaciones, segmentaciones, patrones, conclusiones | **Dashboard** en la app; gráficas funcionales, etiquetadas y útiles | T-05, T-13 |
| C. Estadística | 5 | Combinación razonada de: media/mediana/varianza/desv. estándar, IC, correlación, comparación de grupos, prueba de hipótesis, valor p, distribuciones, incertidumbre | Cada prueba dice **qué hipótesis evalúa y qué significa el resultado**; si no, no se acepta | T-05 |
| D. Series de tiempo | 6* | Orden temporal correcto, tendencia, estacionalidad, ventanas móviles, rezagos, cambios de régimen, predicción o ciclos | Módulo temporal | T-06 |
| E. Feature Engineering | *(con D)* | Variables temporales, lags, rolling, ratios, agregaciones, codificación, texto, energía Wavelet, componentes espectrales, embeddings | El reporte **justifica cada grupo de features** | T-07 |
| F. ML supervisado | 8 | Separación train/test, **baseline**, **al menos dos modelos comparados**, métricas apropiadas (MAE, RMSE, R², Accuracy, Precision, Recall, F1), interpretación, **análisis de errores** | Tabla comparativa y análisis de errores | T-07, T-09 |
| G. ML no supervisado | 4 | Clustering, PCA o estructura latente | Explicar **qué utilidad tiene** en el problema | T-08 |
| H. Pipelines y ensembles | 5 | `Pipeline` de sklearn o equivalente, validación cruzada, **prevención de data leakage**, comparación, **al menos un ensemble** (o justificar por qué no) | Buenas prácticas visibles en el código | T-07 |
| I. Deep Learning | 5 | Un modelo de DL relacionado con el problema (MLP, red de clasificación/regresión, etc.) | **Implementarlo, evaluarlo y compararlo** contra un modelo clásico; no tiene que ganar | T-08 |
| J. NLP clásico | 6* | Limpieza, tokenización, TF-IDF, sentimiento, clasificación de texto, palabras clave o similitud | Métrica o salida | T-14 |
| K. Embeddings y Transformers | *(con J)* | Embeddings, Sentence Transformers o Transformers, similitud o búsqueda semántica | **Comparación o explicación frente a TF-IDF** | T-14 |
| L. LLM | 5 | Tarea real (resumen, clasificación, generación estructurada, etc.); control de **prompt, formato, alucinaciones, errores y validación de salida** | Respuestas estructuradas; si se usa Ollama, debe estar desplegado en la nube | T-12 |
| M. RAG | 8 | Documentos, chunking, embeddings, índice/vector store, consulta, Top-k, contexto, respuesta con LLM, **fuentes o metadatos**, **comportamiento sin evidencia** | **Al menos una métrica del retriever**: Recall@k, Precision@k o MRR | T-11, T-16 |
| N. Agentes y Tool Calling | 7 | Agente o router que decide entre herramientas; definición clara de tools, argumentos estructurados, validación, dispatcher, logging, manejo de errores, **límite de pasos**, **al menos una tarea multi-step** | **Tool Selection Accuracy** en un conjunto de pruebas y **éxito de tareas** | T-15, T-16 |
| O. Fourier | 5 | Señal en el tiempo, FFT, espectro, frecuencias dominantes, conversión frecuencia–periodo, interpretación de al menos un ciclo, filtrado o reconstrucción | Un pico espectral **no se interpreta como causalidad**: solo qué periodicidad sugiere | T-06 |
| P. Wavelets | 6 | PyWavelets; selección de wavelet; DWT o CWT; aproximaciones; detalles; varios niveles; energía por nivel; reconstrucción; interpretación multirresolución | Se valora: anomalías, denoising, features, comparación de señales, localización de eventos | T-06 |
| Arquitectura e integración | 5 | Solución modular y explicable | **Diagrama de arquitectura**; conexión real entre componentes | T-21 |
| Despliegue en la nube | 5 | URL pública; no depender de localhost; secretos en variables de entorno; sin llaves en el repo; dependencias reproducibles (`requirements.txt`); BD remota si hay persistencia; manejo de errores de red; tiempo de respuesta razonable | URL estable durante la evaluación | T-10, T-19 |
| Documentación y repositorio | 4 | Repo ordenado, reproducible, commits claros, README de 18 puntos | — | T-21 |
| Demo y presentación | 3 | Claridad, dominio y funcionamiento sobre la URL | — | T-24, T-25 |

\* D+E comparten 6 puntos; J+K comparten 6 puntos. Los criterios suman 105
aunque el PDF dice "TOTAL 100": pendiente de aclarar con el profesor.

## Penalizaciones

| Situación | Penalización |
|---|---|
| App no desplegada públicamente | hasta −30 |
| Uso superficial de técnicas solo para "cumplir" | hasta −20 |
| URL no funciona durante la evaluación | hasta −15 |
| API keys o contraseñas expuestas en GitHub | hasta −15 |
| Repositorio incompleto o no accesible | hasta −10 |
| No existe README reproducible | hasta −8 |
| Métricas inventadas o no reproducibles | **el apartado vale 0** |
| Plagio o código ajeno presentado como propio | normativa académica (por eso se declara el uso de IA) |

## Interfaz mínima (la app)

Pantalla inicial; descripción del problema; navegación clara; módulo de
datos/EDA; módulo de modelos; módulo temporal/espectral; módulo de IA
generativa; módulo de resultados; mensajes claros de error; **identificación
de fuentes en RAG**; explicación de métricas. Debe poder usarla alguien que
no desarrolló el proyecto.

## README obligatorio (18 puntos)

1 nombre · 2 integrantes · 3 problema · 4 objetivo · 5 arquitectura ·
6 stack · 7 fuente de datos · 8 módulos · 9 modelos · 10 métricas ·
11 Fourier/Wavelets · 12 LLM/RAG/Agentes · 13 instrucciones de desarrollo ·
14 variables de entorno · 15 enlace a la app desplegada · 16 capturas ·
17 limitaciones · 18 trabajo futuro. (+ sección "Uso de IA en el desarrollo").

## Reporte técnico en PDF (24 secciones)

1 resumen ejecutivo · 2 problema · 3 objetivo general · 4 objetivos
específicos · 5 fuente y descripción de datos · 6 arquitectura · 7 ingeniería
de datos · 8 EDA · 9 estadística · 10 series temporales · 11 feature
engineering · 12 machine learning · 13 deep learning · 14 NLP y embeddings ·
15 LLM · 16 RAG · 17 agentes · 18 Fourier · 19 Wavelets · 20 evaluación
integral · 21 despliegue · 22 limitaciones · 23 conclusiones · 24 trabajo
futuro. Incluye la **tabla de trazabilidad** (tema → dónde se aplicó →
evidencia).

## Entregables (si falta uno, la entrega está incompleta)

1 URL pública · 2 repositorio completo · 3 README profesional · 4 reporte
técnico PDF · 5 presentación · 6 video demo con la app desplegada ·
7 dataset o instrucciones reproducibles · 8 modelos o mecanismo reproducible ·
9 resultados y métricas · 10 diagrama de arquitectura · 11 tabla de
trazabilidad.

## Presentación (orden sugerido)

Problema real → usuario → arquitectura → datos → hallazgos → modelo → IA →
series/señales → **demostración en vivo con la URL** → métricas →
conclusiones. Centrada en el producto, no en leer definiciones.

## Criterio de excelencia

"No será el que utilice más librerías, sino el que conecte mejor los métodos
con un problema real, mida correctamente sus resultados y entregue una
experiencia funcional, reproducible y desplegada." Rasgos: problema bien
definido, datos reales o simulación justificada, arquitectura limpia,
interfaz usable, modelos comparados, métricas correctas, interpretación
crítica, RAG con fuentes, agentes con herramientas útiles, análisis temporal y
espectral coherente, Wavelets con propósito, despliegue estable, excelente
documentación, demo convincente.

Regla final: se evalúa que el equipo pueda explicar **qué hizo + por qué lo
hizo + cómo lo midió + qué valor produce**.
