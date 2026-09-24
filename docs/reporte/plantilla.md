# Operaguas Analítica — Reporte técnico

**Diplomado de Python y Análisis de Datos · Universidad Marista · 2026**
**Equipo:** Emilio Rico Hernández y Andrés. **Entrega:** 25 de septiembre de 2026.
**URL pública:** {{var:url_app}} · **Repositorio:** https://github.com/K4ppa1714/SISTEMA_DIPLOMADO

> Este documento se genera con `python docs/reporte/generar.py`. Todo número viene de
> `analitica.resultados` (o de `pipeline/artefactos/resultados/*.json`), producido por código con semilla 42.
> Los párrafos marcados **VALIDAR** son interpretaciones que una persona del equipo confirmó.

## 1. Resumen ejecutivo

Operaguas, organismo operador de agua de Huimilpan, necesita tres cosas: anticipar qué recibos no se
pagarán a tiempo, detectar consumos anómalos (fugas) y atender las quejas más rápido. Construimos una capa de
análisis e IA sobre una **simulación declarada** que reproduce la estructura de su sistema sin datos personales:
un pipeline en Python que limpia, analiza y modela; una base en Supabase que guarda resultados, predicciones e
índice semántico; y una aplicación web (Next.js + FastAPI en Vercel) con módulos de datos, modelos, señales y un
asistente con triage, RAG y agente.

Hallazgos principales:
- Cobranza: {{c:estadistica/pruebas_hipotesis}}
- Modelo de pago tardío: {{c:ml/comparacion_modelos}}
- Fugas: {{c:wavelets/deteccion_fugas}}
- Quejas: {{c:nlp/clasificacion_metricas}}

## 2. Problema

El organismo factura mensualmente a cerca de quinientas tomas (en la simulación, {{c:eda/resumen_datos}})
y conoce el atraso solo después de que ocurre. Las fugas se detectan por queja del usuario o por inspección, y las
quejas se clasifican a mano. **Usuario:** dirección y área de atención de Operaguas.

## 3. Objetivo general

Dar a la dirección y al área de atención una herramienta desplegada que priorice la cobranza, señale tomas con
probable fuga y agilice la atención de quejas, con métodos medidos y reproducibles.

## 4. Objetivos específicos

1. Construir un pipeline reproducible de limpieza con reglas explícitas contra la fuga de información.
2. Describir el comportamiento de consumo, cartera y quejas, y probar hipótesis con estadística inferencial.
3. Predecir el pago tardío por recibo con validación temporal y compararlo contra líneas base.
4. Analizar la serie de consumo en el tiempo y en frecuencia (Fourier y wavelets) para detectar fugas.
5. Clasificar quejas y encontrar quejas similares (NLP clásico contra embeddings).
6. Ofrecer un asistente con LLM: triage estructurado, RAG con fuentes y un agente con herramientas.

## 5. Fuente y descripción de los datos

Simulación declarada con la estructura del sistema de Operaguas (tarifas por tipo de ocupante, privadas, ciclo
mensual de lectura y facturación, catálogo de quejas); los valores son supuestos. No contiene datos personales.
El generador original no se conservó: la simulación **no puede regenerarse idéntica**; la reproducibilidad del
proyecto parte de los CSV versionados en `data/simulados/` y de `pipeline/run_all.py` (decisión T-00c).

{{t:eda/resumen_datos}}

Columnas prohibidas como variables (fuga de datos o parámetros ocultos del generador): `fecha_pago`,
`dias_atraso`, `pagado`, `saldo_pendiente`, `propension_mora`, `consumo_base` y `tiene_fuga` (solo validación).

## 6. Arquitectura

{{var:diagrama}}

- `pipeline/` (Python, fuera de Vercel): limpieza, EDA, estadística, series, FFT, DWT, ML, DL, NLP e índice RAG.
  Escribe resultados (`analitica.resultados`), predicciones por lotes y embeddings.
- Supabase: esquemas `raw`, `analitica`, `rag`, `agente`, `eval`; RLS en todas las tablas; `anon` solo lee.
- `api/` (FastAPI en Vercel): solo lo que depende de la pregunta del usuario (triage, RAG, agente, importe, salud).
- `app/` (Next.js): presenta; un solo componente dibuja cualquier resultado.

## 7. Ingeniería de datos

Pasos del pipeline (`pipeline/src/data/limpieza.py`), con su efecto medido:

{{t:pipeline/informe_calidad}}

Decisiones: los duplicados de lectura se resuelven conservando la más reciente; las lecturas nulas y los retrocesos
de medidor se **marcan y no se imputan**; los importes se recalculan con el tarifario CEA real (T-03); un recibo
vencido y sin pagar a la fecha de corte cuenta como tardío y los recibos con vencimiento posterior quedan fuera del
entrenamiento (censura).

{{f:eda/calidad_lecturas}}

## 8. Análisis exploratorio (EDA)

{{f:eda/consumo_por_tarifa}}
{{f:eda/consumo_mensual}}
{{f:eda/importe_domestico}}
{{f:eda/tardio_por_segmento}}
{{f:eda/cartera_mensual}}
{{f:eda/quejas_por_categoria}}

**VALIDAR (Emilio):** la cartera tardía se concentra en tomas no domiciliadas; la domiciliación es la palanca de
cobranza más clara que muestran los datos. El consumo doméstico tiene estacionalidad anual visible, que se analiza
en la sección 10.

## 9. Estadística

Hipótesis definidas antes de ver los resultados: **H1** el consumo doméstico difiere entre privadas;
**H2** pagar tarde depende de estar domiciliado.

{{t:estadistica/pruebas_hipotesis}}
{{t:estadistica/ic95_tardio}}
{{t:estadistica/correlacion_spearman}}

**VALIDAR (Emilio):** la privada no explica el consumo doméstico (H1 no se rechaza), así que la zona no sirve para
fijar metas de consumo; la domiciliación sí se asocia con puntualidad (H2), con un efecto moderado. Significancia no
implica causalidad: es posible que quien domicilia ya fuera buen pagador.

## 10. Series temporales

{{f:series/consumo_mensual_descomposicion}}
{{f:series/prediccion_mensual}}
{{f:series/consumo_diario_movil}}
{{f:series/autocorrelacion_rezagos}}
{{t:series/cambio_regimen}}

## 11. Feature engineering

Cada variable se conoce el día en que se emite el recibo; el historial de pagos usa solo recibos ya vencidos
(el vencimiento del recibo anterior ocurre antes o el mismo día de la emisión del siguiente).

{{var:tabla_features}}

## 12. Machine learning

Separación temporal (prueba = 4 últimos periodos con etiqueta), validación cruzada temporal por periodo,
líneas base, tres modelos en `Pipeline` y un ensamble. El modelo se elige por PR-AUC en validación, nunca en prueba.

{{t:ml/comparacion_modelos}}
{{f:ml/comparacion_pr_auc}}
{{t:ml/matriz_confusion}}
{{f:ml/importancia_variables}}
{{t:ml/errores_por_segmento}}

Análisis de errores (T-09):

{{f:ml/curva_umbral}}
{{f:ml/calibracion}}
{{t:ml/perfil_errores}}
{{t:ml/predicciones_resumen}}

**VALIDAR (Emilio):** el modelo sirve para ordenar la cobranza (el decil de mayor riesgo concentra la mayor tasa
real de atraso), no para anunciar una probabilidad exacta. Sus fallas son los "atrasos nuevos" de tomas sin
historial de atraso; ninguna variable disponible al emitir el recibo los anticipa.

## 13. Deep learning

{{var:pendiente_T08}}

## 14. NLP y embeddings

{{t:nlp/clasificacion_metricas}}
{{f:nlp/f1_por_categoria}}
{{t:nlp/matriz_confusion}}
{{t:nlp/palabras_clave}}
{{t:nlp/prioridad_desde_texto}}
{{f:embeddings/similitud_precision5}}

**VALIDAR (Andrés):** el clasificador sirve para enrutar quejas; la métrica honesta es la de texto único. La prioridad
debe venir de reglas de negocio o de una persona, no del texto.

## 15. LLM

{{var:pendiente_T12}}

## 16. RAG

{{var:pendiente_T11_T16}}

## 17. Agentes

{{var:pendiente_T15}}

## 18. Fourier

{{f:fourier/espectro}}
{{t:fourier/frecuencias_dominantes}}
{{f:fourier/reconstruccion_filtrada}}

Un pico espectral indica una periodicidad de la señal, no su causa.

## 19. Wavelets

{{f:wavelets/energia_por_nivel}}
{{f:wavelets/descomposicion_ejemplo}}
{{t:wavelets/deteccion_fugas}}
{{t:wavelets/sensibilidad_umbral}}
{{t:wavelets/anomalias_vs_quejas}}

## 20. Evaluación integral

| Componente | Métrica principal | Resultado |
|---|---|---|
| Pago tardío | PR-AUC en prueba temporal | {{c:ml/comparacion_modelos}} |
| Fugas | precisión / recall por toma | {{c:wavelets/deteccion_fugas}} |
| Quejas | F1 macro por texto único | {{c:nlp/clasificacion_metricas}} |
| Similitud | precision@5 | {{c:embeddings/similitud_precision5}} |
| RAG | Recall@k y MRR (solo casos validados) | {{c:rag_eval/metricas}} |
| Agente | Tool Selection Accuracy y éxito de tareas | {{c:agente_eval/metricas}} |

## 21. Despliegue

Un solo proyecto de Vercel (cuenta de Emilio, plan gratuito) sirve la app Next.js y la API FastAPI en la misma URL.
Los secretos viven solo en variables de entorno de Vercel. El pipeline pesado corre fuera de Vercel y deja sus
resultados en Supabase. URL: {{var:url_app}}.

## 22. Limitaciones

- Datos simulados: los resultados muestran el método, no el comportamiento real de Huimilpan; el generador no se conservó.
- Las probabilidades del modelo de pago están infladas por el balanceo de clases: se usan como puntaje de riesgo.
- Las fugas simuladas son escalones limpios; en datos reales habrá ruido y fugas graduales.
- Plan gratuito de Gemini: límites diarios bajos y uso del contenido por Google (aceptable solo con datos simulados).
- El corpus del RAG es pequeño; faltan la NOM-127, el contrato tipo y las preguntas frecuentes del portal.

## 23. Conclusiones

**VALIDAR (Emilio y Andrés):** el valor del proyecto está en conectar cada método con una decisión de Operaguas:
a quién cobrar primero (modelo de pago), dónde revisar una fuga (flujo nocturno y wavelets) y cómo enrutar una
queja (clasificador + triage). Las métricas se midieron con separación temporal o por texto único para no
sobreestimarlas.

## 24. Trabajo futuro

- Probar con datos reales anonimizados de Operaguas y recalibrar el modelo de pago (calibración isotónica).
- Integrar la lista de riesgo a la cobranza y medir el efecto con un piloto A/B.
- Telemetría en más tomas y detección de fugas graduales.
- Ampliar el corpus del RAG con documentos oficiales.

## Tabla de trazabilidad

{{var:trazabilidad}}
