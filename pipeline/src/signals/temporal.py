"""T-06 — Series de tiempo (bloque D), Fourier (bloque O) y Wavelets (bloque P).

Problema de negocio que atiende: (2) detectar consumos anómalos (fugas) y
entender los ciclos de consumo para planear la operación.

Datos:
- Serie mensual: consumo promedio por toma en `dataset` (30 periodos, 2024-04 a 2026-09).
- Serie horaria: `telemetria.csv` (40 tomas × 2,880 horas, 2026-05-05 a 2026-09-01).

Reglas del proyecto que se respetan aquí:
- Todo número de una conclusión se calcula en este módulo (regla 5).
- `tiene_fuga` es etiqueta de VALIDACIÓN: nunca entra al detector; solo se usa
  para medir si acierta (COLUMNAS_PROHIBIDAS).
- El umbral del detector se fija SIN mirar etiquetas: percentil 99.5 del
  puntaje en el periodo de referencia (primeros 21 días, anteriores a la
  primera fuga simulada). La sensibilidad a ese umbral se reporta aparte.
- Un pico espectral solo dice qué periodicidad hay, no su causa.

Uso:
    from pipeline.src.signals.temporal import ejecutar
    r = ejecutar()   # dict con listas de {"clave", "payload"} por módulo + tablas
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pywt
from scipy import stats
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import acf

from pipeline.src.config import SEMILLA
from pipeline.src.data.limpieza import ejecutar as limpiar

FUENTE = "pipeline/src/signals/temporal.py"

WAVELET = "db4"          # soporte compacto y 4 momentos nulos: separa nivel base de ciclos suaves
NIVEL = 5                # 2^5 = 32 h: el nivel A5 queda por encima del ciclo diario (24 h)
DIAS_REFERENCIA = 21     # primeras 3 semanas (antes de la primera fuga simulada)
VENTANA_H = 72           # ventana móvil del puntaje (3 días)
PERCENTIL_UMBRAL = 99.5  # umbral no supervisado sobre el periodo de referencia
HORAS_SOSTENIDAS = 24    # una alarma exige 24 h seguidas sobre el umbral
HORAS_NOCHE = (2, 3, 4)  # flujo mínimo nocturno (método clásico de comparación)
MESES_PRUEBA = 6

# Escala aproximada de cada nivel de la DWT con datos horarios
ESCALAS = {"D1": "2–4 h", "D2": "4–8 h", "D3": "8–16 h", "D4": "16–32 h (ciclo diario)",
           "D5": "32–64 h", "A5": "> 64 h (nivel base)"}


def _r(x: float, d: int = 2) -> float:
    return float(round(float(x), d))


# ============================================================ carga
def cargar() -> dict[str, pd.DataFrame]:
    tablas, _ = limpiar()
    tele = tablas["telemetria"].sort_values(["id_toma", "marca_tiempo"]).reset_index(drop=True)
    return {"dataset": tablas["dataset"], "telemetria": tele, "quejas": tablas["quejas"]}


def serie_mensual(dataset: pd.DataFrame) -> pd.Series:
    s = dataset.groupby("periodo")["consumo_m3"].mean().sort_index()
    s.index = pd.PeriodIndex(s.index, freq="M")
    return s


def serie_horaria_total(tele: pd.DataFrame) -> pd.Series:
    return tele.groupby("marca_tiempo")["volumen_m3"].sum().sort_index().asfreq("h")


# ============================================================ D. series de tiempo
def descomposicion(s: pd.Series) -> dict:
    d = seasonal_decompose(s.to_numpy(), model="additive", period=12, extrapolate_trend="freq")
    est = pd.Series(d.seasonal[:12], index=[p.month for p in s.index[:12]]).sort_index()
    pico, valle = int(est.idxmax()), int(est.idxmin())
    tend = d.trend
    cambio = tend[-1] - tend[0]
    return {"clave": "consumo_mensual_descomposicion", "payload": {
        "tipo": "linea",
        "titulo": "Consumo mensual promedio por toma: tendencia y estacionalidad",
        "x": {"etiqueta": "Periodo", "valores": [str(p) for p in s.index]},
        "y": {"etiqueta": "Consumo (m³ por toma)"},
        "series": [
            {"nombre": "Observado", "valores": list(s.to_numpy())},
            {"nombre": "Tendencia (media móvil 12 meses)", "valores": list(tend)},
            {"nombre": "Estacionalidad + nivel medio", "valores": list(d.seasonal + s.mean())},
        ],
        "conclusion": (f"Descomposición aditiva con periodo 12: el mes más alto es {pico} "
                       f"(+{_r(est.max())} m³ sobre la tendencia) y el más bajo {valle} "
                       f"({_r(est.min())} m³). La tendencia cambia {_r(cambio)} m³ en "
                       f"{len(s)} meses: la estacionalidad domina, no el crecimiento."),
        "fuente": FUENTE,
    }}


def prediccion_mensual(s: pd.Series) -> dict:
    y = s.to_numpy()
    tr, te = y[:-MESES_PRUEBA], y[-MESES_PRUEBA:]
    preds = {
        "Ingenuo (último mes)": np.repeat(tr[-1], MESES_PRUEBA),
        "Ingenuo estacional (mismo mes, año previo)": y[-MESES_PRUEBA - 12:-12],
        "Holt-Winters aditivo (tendencia + estacionalidad 12)": ExponentialSmoothing(
            tr, trend="add", seasonal="add", seasonal_periods=12).fit().forecast(MESES_PRUEBA),
    }
    filas = []
    for nombre, p in preds.items():
        err = te - p
        filas.append({"modelo": nombre, "MAE": _r(np.abs(err).mean(), 3),
                      "RMSE": _r(np.sqrt((err ** 2).mean()), 3),
                      "MAPE_%": _r(100 * np.abs(err / te).mean(), 2)})
    filas.sort(key=lambda f: f["MAE"])
    mejor, base = filas[0], next(f for f in filas if f["modelo"].startswith("Ingenuo (último"))
    return {"clave": "prediccion_mensual", "payload": {
        "tipo": "tabla",
        "titulo": f"Pronóstico de consumo mensual: prueba en los últimos {MESES_PRUEBA} meses",
        "filas": filas,
        "conclusion": (f"Con entrenamiento hasta {s.index[-MESES_PRUEBA - 1]} y prueba "
                       f"{s.index[-MESES_PRUEBA]}–{s.index[-1]}, el mejor es «{mejor['modelo']}» "
                       f"(MAE {mejor['MAE']} m³ contra {base['MAE']} del ingenuo): modelar la "
                       "estacionalidad es lo que reduce el error."),
        "fuente": FUENTE,
    }}


def rolling_diario(h: pd.Series) -> dict:
    d = h.resample("D").sum()
    r7 = d.rolling(7, min_periods=7).mean()
    return {"clave": "consumo_diario_movil", "payload": {
        "tipo": "linea",
        "titulo": "Consumo diario de las 40 tomas con telemetría y media móvil de 7 días",
        "x": {"etiqueta": "Día", "valores": [str(i.date()) for i in d.index]},
        "y": {"etiqueta": "Volumen (m³/día)"},
        "series": [{"nombre": "Diario", "valores": list(d.to_numpy())},
                   {"nombre": "Media móvil 7 días", "valores": list(r7.to_numpy())}],
        "conclusion": (f"La media móvil pasa de {_r(r7.dropna().iloc[0])} a "
                       f"{_r(r7.dropna().iloc[-1])} m³/día entre el inicio y el fin del periodo; "
                       "la ventana de 7 días quita el ruido día a día y deja ver el cambio de nivel."),
        "fuente": FUENTE,
    }}


def autocorrelacion(h: pd.Series) -> dict:
    rezagos = [1, 2, 3, 6, 12, 24, 48, 72, 168]
    a = acf(h.to_numpy(), nlags=max(rezagos), fft=True)
    banda = 1.96 / np.sqrt(len(h))
    filas = [{"rezago_h": k, "autocorrelacion": _r(a[k], 3)} for k in rezagos]
    return {"clave": "autocorrelacion_rezagos", "payload": {
        "tipo": "barras",
        "titulo": "Autocorrelación del consumo horario por rezago",
        "x": {"etiqueta": "Rezago (horas)", "valores": [str(k) for k in rezagos]},
        "y": {"etiqueta": "Autocorrelación"},
        "series": [{"nombre": "ACF", "valores": [f["autocorrelacion"] for f in filas]}],
        "filas": filas,
        "conclusion": (f"El rezago de 24 h ({_r(a[24], 3)}) y el de 168 h ({_r(a[168], 3)}) son "
                       f"mucho mayores que el de 12 h ({_r(a[12], 3)}): el consumo se repite cada "
                       f"día. Banda de significancia ±{_r(banda, 3)}. Estos rezagos son candidatos "
                       "a variables (bloque E)."),
        "fuente": FUENTE,
    }}


def cambio_regimen(h: pd.Series) -> tuple[dict, pd.Timestamp]:
    """Un punto de cambio en la media (mínimo SSE de dos segmentos) + prueba de Welch."""
    d = h.resample("D").sum()
    x = d.to_numpy()
    minimo = 14
    sse = [((x[:k] - x[:k].mean()) ** 2).sum() + ((x[k:] - x[k:].mean()) ** 2).sum()
           for k in range(minimo, len(x) - minimo)]
    k = minimo + int(np.argmin(sse))
    antes, despues = x[:k], x[k:]
    t, p = stats.ttest_ind(antes, despues, equal_var=False)
    fecha = d.index[k]
    return {"clave": "cambio_regimen", "payload": {
        "tipo": "tabla",
        "titulo": "Cambio de régimen en el consumo diario (un punto de cambio en la media)",
        "filas": [
            {"indicador": "Fecha del cambio", "valor": str(fecha.date())},
            {"indicador": "Media antes (m³/día)", "valor": _r(antes.mean(), 3)},
            {"indicador": "Media después (m³/día)", "valor": _r(despues.mean(), 3)},
            {"indicador": "Cambio relativo (%)", "valor": _r(100 * (despues.mean() / antes.mean() - 1))},
            {"indicador": "t de Welch", "valor": _r(t, 3)},
            {"indicador": "valor p", "valor": float(f"{p:.3g}")},
        ],
        "conclusion": (f"H0: la media diaria es igual antes y después de {fecha.date()}. "
                       f"p = {p:.3g} {'< 0.05: se rechaza H0' if p < 0.05 else '≥ 0.05: no se rechaza H0'}; "
                       f"el consumo {'sube' if despues.mean() > antes.mean() else 'baja'} "
                       f"{_r(abs(100 * (despues.mean() / antes.mean() - 1)))} %. El total mezcla "
                       "estacionalidad y fugas: un cambio en el agregado no dice qué tomas lo causan; "
                       "eso lo resuelve el análisis por toma con Wavelets."),
        "fuente": FUENTE,
    }}, fecha


# ============================================================ O. Fourier
def espectro(h: pd.Series) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = h.to_numpy() - h.mean()
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), d=1.0)  # ciclos por hora
    return f, X, np.abs(X) ** 2


def picos(f: np.ndarray, P: np.ndarray, n: int = 5) -> list[int]:
    idx = [i for i in np.argsort(P)[::-1] if f[i] > 0]
    elegidos: list[int] = []
    for i in idx:  # evita contar dos veces el mismo pico (fugas espectrales vecinas)
        if all(abs(i - j) > 2 for j in elegidos):
            elegidos.append(i)
        if len(elegidos) == n:
            break
    return elegidos


def fourier(h: pd.Series) -> list[dict]:
    f, X, P = espectro(h)
    total = P[1:].sum()
    top = picos(f, P)
    filas = [{"frecuencia_ciclos_por_hora": _r(f[i], 5), "ciclos_por_dia": _r(24 * f[i], 3),
              "periodo_horas": _r(1 / f[i], 2), "energia_%": _r(100 * P[i] / total, 2)} for i in top]
    armonicos = [i for i in range(1, len(f)) if abs((24 * f[i]) - round(24 * f[i])) < 1e-9
                 and 1 <= round(24 * f[i]) <= 6]
    e_diaria = 100 * P[armonicos].sum() / total

    # Espectro para graficar en eje de frecuencia lineal: de 0.1 a 6 ciclos por día
    # (periodos de 10 días a 4 h); el periodo de cada pico está en la tabla.
    m = (24 * f >= 0.1) & (24 * f <= 6)
    cpd, pot = 24 * f[m], 100 * P[m] / total

    # Filtro: se conservan solo el nivel medio y los K picos (y su conjugado implícito en rfft)
    K = 6
    keep = np.zeros_like(X)
    keep[0] = X[0]
    for i in picos(f, P, K):
        keep[i] = X[i]
    rec = np.fft.irfft(keep, n=len(h)) + h.mean()
    r2 = 1 - ((h.to_numpy() - rec) ** 2).sum() / ((h.to_numpy() - h.mean()) ** 2).sum()
    semana = slice(0, 168)

    return [
        {"clave": "espectro", "payload": {
            "tipo": "linea",
            "titulo": "Espectro de potencia del consumo horario (FFT)",
            "x": {"etiqueta": "Frecuencia (ciclos por día)", "valores": [_r(c, 3) for c in cpd]},
            "y": {"etiqueta": "Energía (% del total)"},
            "series": [{"nombre": "Potencia", "valores": list(pot)}],
            "conclusion": (f"El pico dominante está en {filas[0]['ciclos_por_dia']} ciclo(s) por día, "
                           f"es decir, un periodo de 24/{filas[0]['ciclos_por_dia']} = "
                           f"{filas[0]['periodo_horas']} h ({filas[0]['energia_%']} % de la energía). "
                           "Un pico espectral indica una periodicidad, no su causa."),
            "fuente": FUENTE,
        }},
        {"clave": "frecuencias_dominantes", "payload": {
            "tipo": "tabla",
            "titulo": "Frecuencias dominantes y su periodo",
            "filas": filas,
            "conclusion": (f"Periodo = 1/frecuencia. El ciclo diario y sus armónicos (24, 12, 8, 6 h…) "
                           f"concentran {_r(e_diaria)} % de la energía: el patrón es un día con dos "
                           "picos de uso (mañana y tarde), lo que sugiere planear presión y "
                           "bombeo por franja horaria."),
            "fuente": FUENTE,
        }},
        {"clave": "reconstruccion_filtrada", "payload": {
            "tipo": "linea",
            "titulo": f"Filtrado: reconstrucción con {K} frecuencias (primera semana)",
            "x": {"etiqueta": "Hora", "valores": [str(t) for t in h.index[semana]]},
            "y": {"etiqueta": "Volumen (m³/h)"},
            "series": [{"nombre": "Original", "valores": list(h.to_numpy()[semana])},
                       {"nombre": f"Reconstruida ({K} picos)", "valores": list(rec[semana])}],
            "conclusion": (f"Con solo {K} de {len(f) - 1} frecuencias la señal reconstruida explica "
                           f"R² = {_r(r2, 3)} de la variación horaria: el resto es ruido y cambios "
                           "de nivel que la FFT no localiza en el tiempo (por eso se usan Wavelets)."),
            "fuente": FUENTE,
        }},
    ]


# ============================================================ P. Wavelets
def energia_relativa(x: np.ndarray) -> dict[str, float]:
    c = pywt.wavedec(x, WAVELET, level=NIVEL, mode="periodization")
    nombres = [f"A{NIVEL}"] + [f"D{NIVEL - i}" for i in range(NIVEL)]
    e = np.array([(ci ** 2).sum() for ci in c])
    return dict(zip(nombres, e / e.sum()))


def puntaje_swt(x: np.ndarray) -> np.ndarray:
    """Energía de la aproximación A5 / energía de los detalles D1–D5 en una ventana móvil.

    Una fuga agrega un flujo constante: sube el nivel base (A5) sin aumentar la
    variación de los ciclos (detalles), así que el cociente crece. Se normaliza
    con la mediana del periodo de referencia de la propia toma.
    """
    co = pywt.swt(x, WAVELET, level=NIVEL, trim_approx=True, norm=True)  # [cA5, cD5 … cD1]
    a = pd.Series(co[0] ** 2).rolling(VENTANA_H).mean()
    d = pd.Series(sum(c ** 2 for c in co[1:])).rolling(VENTANA_H).mean()
    r = (a / d).to_numpy()
    ref = r[VENTANA_H:DIAS_REFERENCIA * 24]
    return r / np.nanmedian(ref)


def puntaje_nocturno(x: np.ndarray, ts: pd.DatetimeIndex) -> np.ndarray:
    """Método clásico: flujo mínimo nocturno (2–4 h) del día, relativo a la referencia."""
    s = pd.Series(x, index=ts)
    noche = s[s.index.hour.isin(HORAS_NOCHE)].resample("D").mean()
    rel = noche / noche.iloc[:DIAS_REFERENCIA].median()
    # se asigna al día siguiente para no usar horas futuras dentro del mismo día
    return rel.shift(1).reindex(ts.floor("D")).to_numpy()


def _alarma(score: np.ndarray, umbral: float) -> np.ndarray:
    sobre = np.nan_to_num(score, nan=0.0) > umbral
    run = np.zeros(len(sobre), dtype=int)
    for i in range(len(sobre)):
        run[i] = run[i - 1] + 1 if sobre[i] and i else int(sobre[i])
    return run >= HORAS_SOSTENIDAS


def evaluar(tele: pd.DataFrame, metodo: str, factor: float = 1.0) -> tuple[dict, pd.DataFrame]:
    puntajes, etiquetas, tiempos = {}, {}, {}
    for tid, g in tele.groupby("id_toma"):
        x = g["volumen_m3"].to_numpy(dtype=float).copy()
        ts = pd.DatetimeIndex(g["marca_tiempo"])
        puntajes[tid] = puntaje_swt(x) if metodo == "wavelet" else puntaje_nocturno(x, ts)
        etiquetas[tid] = g["tiene_fuga"].to_numpy(dtype=bool)
        tiempos[tid] = ts
    ref_h = DIAS_REFERENCIA * 24
    referencia = np.concatenate([s[:ref_h][~np.isnan(s[:ref_h])] for s in puntajes.values()])
    umbral = factor * float(np.percentile(referencia, PERCENTIL_UMBRAL))

    filas, tp_h, fp_h, fn_h = [], 0, 0, 0
    for tid, s in puntajes.items():
        al, y = _alarma(s, umbral), etiquetas[tid]
        al[:ref_h] = False  # la referencia no se evalúa
        yv = y.copy()
        yv[:ref_h] = False
        tp_h += int((al & yv).sum()); fp_h += int((al & ~yv).sum()); fn_h += int((~al & yv).sum())
        inicio_real = tiempos[tid][y.argmax()] if y.any() else pd.NaT
        inicio_det = tiempos[tid][al.argmax()] if al.any() else pd.NaT
        # En una toma con fuga, cuenta como acierto la primera alarma DESPUÉS del inicio real;
        # una alarma previa al inicio ya se contó como falsa en las métricas por hora.
        if y.any():
            post = al & (np.arange(len(al)) >= y.argmax())
            detectada = bool(post.any())
            inicio_det = tiempos[tid][post.argmax()] if detectada else pd.NaT
        else:
            detectada = bool(al.any())
        filas.append({"id_toma": tid, "fuga_real": bool(y.any()), "detectada": detectada,
                      "inicio_real": inicio_real, "inicio_detectado": inicio_det,
                      "puntaje_max": float(np.nanmax(s[ref_h:])),
                      "retraso_h": (inicio_det - inicio_real).total_seconds() / 3600
                      if (pd.notna(inicio_real) and pd.notna(inicio_det)) else np.nan})
    df = pd.DataFrame(filas)
    tp = int((df.fuga_real & df.detectada).sum()); fp = int((~df.fuga_real & df.detectada).sum())
    fn = int((df.fuga_real & ~df.detectada).sum())
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    ret = df.loc[df.fuga_real & df.detectada, "retraso_h"]
    m = {"metodo": metodo, "umbral": umbral, "tp": tp, "fp": fp, "fn": fn,
         "precision": prec, "recall": rec, "f1": f1,
         "retraso_mediano_h": float(ret.median()) if len(ret) else np.nan,
         "precision_horas": tp_h / (tp_h + fp_h) if tp_h + fp_h else np.nan,
         "recall_horas": tp_h / (tp_h + fn_h) if tp_h + fn_h else np.nan}
    return m, df


def wavelets(tele: pd.DataFrame, quejas: pd.DataFrame) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    # --- energía por nivel (tiene_fuga solo para describir los grupos, no entra al cálculo)
    en = []
    for tid, g in tele.groupby("id_toma"):
        e = energia_relativa(g["volumen_m3"].to_numpy(dtype=float).copy())
        e["id_toma"], e["grupo"] = tid, "con fuga" if g["tiene_fuga"].any() else "sin fuga"
        en.append(e)
    en = pd.DataFrame(en)
    niveles = [f"D{i}" for i in range(1, NIVEL + 1)] + [f"A{NIVEL}"]
    medias = en.groupby("grupo")[niveles].mean() * 100

    # --- ejemplo: descomposición y reconstrucción perfecta de la toma con más consumo de fuga
    fugas = tele[tele["tiene_fuga"]].groupby("id_toma").size()
    ejemplo = fugas.idxmax()
    g = tele[tele["id_toma"] == ejemplo]
    x = g["volumen_m3"].to_numpy(dtype=float).copy()
    c = pywt.wavedec(x, WAVELET, level=NIVEL, mode="periodization")
    rec = pywt.waverec(c, WAVELET, mode="periodization")
    err = float(np.max(np.abs(rec - x)))
    aprox = pywt.waverec([c[0]] + [np.zeros_like(ci) for ci in c[1:]], WAVELET, mode="periodization")
    diario = pd.DataFrame({"x": x, "a": aprox}, index=pd.DatetimeIndex(g["marca_tiempo"])).resample("D").mean()
    inicio = g.loc[g["tiene_fuga"], "marca_tiempo"].min()

    # --- detección y comparación contra el método clásico
    mw, dw = evaluar(tele, "wavelet")
    mn, _ = evaluar(tele, "nocturno")
    sens = [evaluar(tele, "wavelet", fct)[0] | {"factor": fct} for fct in (0.8, 1.0, 1.2, 1.5)]

    def fila(m: dict, nombre: str) -> dict:
        return {"metodo": nombre, "umbral": _r(m["umbral"], 3), "VP": m["tp"], "FP": m["fp"],
                "FN": m["fn"], "precision": _r(m["precision"], 3), "recall": _r(m["recall"], 3),
                "F1": _r(m["f1"], 3), "retraso_mediano_h": _r(m["retraso_mediano_h"], 1),
                "precision_por_hora": _r(m["precision_horas"], 3),
                "recall_por_hora": _r(m["recall_horas"], 3)}

    comp = [fila(mw, f"Wavelet SWT {WAVELET} (A{NIVEL}/detalles)"),
            fila(mn, "Flujo mínimo nocturno 2–4 h (clásico)")]

    # --- anomalías contra quejas de la misma toma (validación cruzada con otra fuente)
    det = dw[dw.detectada].copy()
    q = quejas[quejas["id_toma"].isin(det["id_toma"])]
    q = q.merge(det[["id_toma", "inicio_detectado"]], on="id_toma")
    q = q[q["fecha_reporte"] >= q["inicio_detectado"] - pd.Timedelta(days=7)]
    con_queja_fuga = q[q["categoria"].isin(["fuga_toma", "fuga_calle"])]["id_toma"].nunique()

    payloads = [
        {"clave": "energia_por_nivel", "payload": {
            "tipo": "barras",
            "titulo": f"Energía relativa por nivel de la DWT ({WAVELET}, {NIVEL} niveles)",
            "x": {"etiqueta": "Nivel (escala)", "valores": [f"{n} · {ESCALAS[n]}" for n in niveles]},
            "y": {"etiqueta": "Energía (% del total de la toma)"},
            "series": [{"nombre": grp, "valores": list(medias.loc[grp, niveles])} for grp in medias.index],
            "filas": [{"grupo": grp, **{n: _r(medias.loc[grp, n]) for n in niveles}} for grp in medias.index],
            "conclusion": (f"Se eligió {WAVELET} porque su soporte corto localiza el inicio de una fuga "
                           f"y sus 4 momentos nulos separan el nivel base de los ciclos. En tomas con fuga, "
                           f"A{NIVEL} concentra {_r(medias.loc['con fuga', f'A{NIVEL}'])} % de la energía contra "
                           f"{_r(medias.loc['sin fuga', f'A{NIVEL}'])} % sin fuga: la fuga vive en la escala "
                           "larga, no en el ciclo diario (D4). La etiqueta solo se usa para comparar grupos."),
            "fuente": FUENTE,
        }},
        {"clave": "descomposicion_ejemplo", "payload": {
            "tipo": "linea",
            "titulo": f"Toma {ejemplo}: señal y aproximación A{NIVEL} (promedio diario)",
            "x": {"etiqueta": "Día", "valores": [str(i.date()) for i in diario.index]},
            "y": {"etiqueta": "Volumen (m³/h)"},
            "series": [{"nombre": "Señal", "valores": list(diario["x"])},
                       {"nombre": f"Aproximación A{NIVEL}", "valores": list(diario["a"])}],
            "conclusion": (f"La aproximación A{NIVEL} quita los ciclos de menos de ~64 h y deja ver el "
                           f"salto de nivel que empieza el {inicio.date()} (fuga simulada). "
                           f"Reconstruir con todos los niveles devuelve la señal con error máximo "
                           f"{err:.1e} m³/h: la DWT no pierde información."),
            "fuente": FUENTE,
        }},
        {"clave": "deteccion_fugas", "payload": {
            "tipo": "tabla",
            "titulo": "Detección de fugas: Wavelets contra flujo mínimo nocturno",
            "filas": comp,
            "conclusion": (f"Umbral fijado sin etiquetas (percentil {PERCENTIL_UMBRAL} del periodo de "
                           f"referencia) y alarma con {HORAS_SOSTENIDAS} h seguidas. Wavelets: "
                           f"{mw['tp']} de {mw['tp'] + mw['fn']} fugas, {mw['fp']} falsas alarmas, retraso "
                           f"mediano {_r(mw['retraso_mediano_h'], 1)} h. Nocturno: {mn['tp']} de "
                           f"{mn['tp'] + mn['fn']}, {mn['fp']} falsas, {_r(mn['retraso_mediano_h'], 1)} h. "
                           f"Gana {'el flujo nocturno' if mn['f1'] > mw['f1'] else 'Wavelets'} en F1: "
                           "para una fuga constante, la hora de menor uso es la señal más limpia; "
                           "Wavelets aporta la descomposición por escala y variables para modelos. "
                           "tiene_fuga solo mide el acierto; nunca entra al detector."),
            "fuente": FUENTE,
        }},
        {"clave": "sensibilidad_umbral", "payload": {
            "tipo": "tabla",
            "titulo": "Sensibilidad del detector Wavelet al umbral",
            "filas": [{"factor_umbral": s["factor"], "umbral": _r(s["umbral"], 3), "VP": s["tp"],
                       "FP": s["fp"], "FN": s["fn"], "F1": _r(s["f1"], 3),
                       "retraso_mediano_h": _r(s["retraso_mediano_h"], 1)} for s in sens],
            "conclusion": ("Un umbral más bajo detecta antes pero arriesga falsas alarmas; uno más alto "
                           "las evita pero tarda más. La tabla muestra qué tan estable es el resultado "
                           "sin elegir el umbral con las etiquetas."),
            "fuente": FUENTE,
        }},
        {"clave": "anomalias_vs_quejas", "payload": {
            "tipo": "metrica",
            "titulo": "Anomalías detectadas contra quejas de fuga",
            "filas": [{"indicador": "Tomas con alarma", "valor": int(len(det))},
                      {"indicador": "…con queja de fuga desde 7 días antes de la alarma",
                       "valor": int(con_queja_fuga)}],
            "conclusion": (f"{con_queja_fuga} de {len(det)} tomas con alarma tienen una queja de fuga "
                           "cercana: en esta simulación las quejas no bastan para encontrar fugas, y la "
                           "telemetría sí las señala. Cada alarma requiere inspección antes de actuar."),
            "fuente": FUENTE,
        }},
    ]
    features = en.drop(columns="grupo").rename(columns={n: f"energia_{n}" for n in niveles})
    return payloads, dw, features


# ============================================================ orquestación
def ejecutar() -> dict:
    np.random.seed(SEMILLA)
    datos = cargar()
    mensual = serie_mensual(datos["dataset"])
    horaria = serie_horaria_total(datos["telemetria"])

    cambio, _ = cambio_regimen(horaria)
    series = [descomposicion(mensual), prediccion_mensual(mensual), rolling_diario(horaria),
              autocorrelacion(horaria), cambio]
    wav, deteccion, features = wavelets(datos["telemetria"], datos["quejas"])

    anomalias = deteccion[deteccion.detectada].assign(
        ts=lambda d: d["inicio_detectado"], nivel_wavelet=NIVEL, score=lambda d: d["puntaje_max"],
        tipo="fuga_probable")[["id_toma", "ts", "nivel_wavelet", "score", "tipo", "fuga_real"]]

    largas = pd.concat([
        pd.DataFrame({"serie": "consumo_horario_telemetria", "ts": horaria.index, "valor": horaria.to_numpy()}),
        pd.DataFrame({"serie": "consumo_diario_telemetria", "ts": horaria.resample("D").sum().index,
                      "valor": horaria.resample("D").sum().to_numpy()}),
        pd.DataFrame({"serie": "consumo_mensual_promedio", "ts": mensual.index.to_timestamp(),
                      "valor": mensual.to_numpy()}),
    ], ignore_index=True)
    return {"series": series, "fourier": fourier(horaria), "wavelets": wav,
            "anomalias": anomalias, "series_largas": largas, "features": features}


def sql_tablas(series_largas: pd.DataFrame, anomalias: pd.DataFrame, version: str = "v1") -> str:
    """SQL idempotente para analitica.series y analitica.anomalias (sin credenciales en el repo)."""
    nombres = ", ".join(f"'{s}'" for s in sorted(series_largas["serie"].unique()))
    vs = ",\n".join(f"('{f.serie}','{pd.Timestamp(f.ts).isoformat()}'::timestamptz,{float(f.valor):.6g})"
                    for f in series_largas.itertuples())
    va = ",\n".join(f"('{f.id_toma}','{pd.Timestamp(f.ts).isoformat()}'::timestamptz,{int(f.nivel_wavelet)},"
                    f"{float(f.score):.6g},'{f.tipo}',{str(bool(f.fuga_real)).lower()},'{version}')"
                    for f in anomalias.itertuples())
    return (f"begin;\ndelete from analitica.series where serie in ({nombres});\n"
            f"insert into analitica.series (serie, ts, valor) values\n{vs};\n"
            f"delete from analitica.anomalias where version = '{version}' and tipo = 'fuga_probable';\n"
            f"insert into analitica.anomalias (id_toma, ts, nivel_wavelet, score, tipo, fuga_real, version) values\n{va};\n"
            "commit;\n")
