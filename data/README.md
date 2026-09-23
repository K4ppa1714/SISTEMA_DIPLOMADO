# Datos

`simulados/` contiene la **simulación declarada** de Andrés (ver `simulados/LEEME.txt`): reproduce la estructura del sistema de Operaguas, con valores supuestos. **No hay datos personales.**

| Archivo | Filas | Uso |
|---|---|---|
| tomas.csv | 480 | Padrón: privada, tarifa, domiciliación |
| lecturas.csv | 14,486 | Lecturas mensuales con suciedad a propósito |
| recibos.csv | 14,400 | Emisión, vencimiento, pago; objetivo `pago_tardio` |
| telemetria.csv | 115,200 | Volumen horario de 40 tomas (bloques O y P) |
| quejas.csv | 1,400 | Texto libre y categoría (bloques J–L) |
| dataset_final.csv | 14,400 | Tabla de análisis ya procesada |

**Reglas (propuesta #5):**
- Nunca como variables: `fecha_pago`, `dias_atraso`, `pagado`, `saldo_pendiente`, `propension_mora`, `consumo_base`, `tiene_fuga` (ver `pipeline/src/config.py`).
- Quejas: separar entrenamiento y prueba por **texto único** (331 textos distintos en 1,400 quejas).
- Recibos vencidos y sin pagar cuentan como tardíos; periodos con vencimiento posterior a `FECHA_CORTE` quedan fuera del entrenamiento.
- Pendiente: agregar el generador `generar_datos.py` (lo tiene Andrés) para que la simulación sea reproducible y documentar sus supuestos.
