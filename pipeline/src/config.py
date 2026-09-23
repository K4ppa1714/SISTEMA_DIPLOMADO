"""Configuración común del pipeline."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DATOS_SIMULADOS = RAIZ / "data" / "simulados"
ARTEFACTOS = RAIZ / "pipeline" / "artefactos"

SEMILLA = 42

# Fecha de corte: último pago registrado en la simulación.
# Recibos con vencimiento posterior quedan fuera del entrenamiento (censura).
FECHA_CORTE = "2026-09-01"

# Columnas que NUNCA entran como variables (fuga de datos o parámetros ocultos del generador).
COLUMNAS_PROHIBIDAS = {
    "fecha_pago", "dias_atraso", "pagado", "saldo_pendiente",  # se conocen después del pago
    "propension_mora", "consumo_base",                          # parámetros del generador
    "tiene_fuga",                                               # etiqueta de validación
}
