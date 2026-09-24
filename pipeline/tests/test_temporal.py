"""Pruebas de T-06 (series, Fourier y Wavelets) con señales sintéticas: no leen los CSV."""
import numpy as np
import pandas as pd
import pywt

from pipeline.src.signals import temporal as T


def _serie_horaria(dias=120, fuga_desde=None, fuga=0.02, semilla=42):
    rng = np.random.default_rng(semilla)
    ts = pd.date_range("2026-05-05", periods=dias * 24, freq="h")
    base = 0.03 + 0.02 * np.sin(2 * np.pi * np.arange(len(ts)) / 24)
    x = np.clip(base + rng.normal(0, 0.002, len(ts)), 1e-4, None)
    y = np.zeros(len(ts), dtype=bool)
    if fuga_desde is not None:
        y[fuga_desde * 24:] = True
        x[y] += fuga
    return ts, x, y


def test_fft_encuentra_ciclo_de_24h():
    ts, x, _ = _serie_horaria()
    f, _, P = T.espectro(pd.Series(x, index=ts))
    i = T.picos(f, P, 1)[0]
    assert abs(1 / f[i] - 24) < 0.5


def test_dwt_reconstruccion_perfecta():
    _, x, _ = _serie_horaria()
    c = pywt.wavedec(x, T.WAVELET, level=T.NIVEL, mode="periodization")
    assert np.max(np.abs(pywt.waverec(c, T.WAVELET, mode="periodization") - x)) < 1e-10


def test_energia_relativa_suma_uno():
    _, x, _ = _serie_horaria()
    e = T.energia_relativa(x)
    assert abs(sum(e.values()) - 1) < 1e-9 and set(e) == {"A5", "D1", "D2", "D3", "D4", "D5"}


def test_detector_no_usa_la_etiqueta_y_detecta_fuga():
    filas = []
    for i, desde in enumerate([None, None, 60, 80]):
        ts, x, y = _serie_horaria(fuga_desde=desde, semilla=i)
        filas.append(pd.DataFrame({"id_toma": f"T{i}", "marca_tiempo": ts, "volumen_m3": x, "tiene_fuga": y}))
    tele = pd.concat(filas, ignore_index=True)
    # los puntajes solo reciben el volumen (y la hora): la etiqueta no puede entrar
    import inspect
    assert list(inspect.signature(T.puntaje_swt).parameters) == ["x"]
    assert list(inspect.signature(T.puntaje_nocturno).parameters) == ["x", "ts"]
    for metodo in ("wavelet", "nocturno"):
        m, df = T.evaluar(tele, metodo)
        assert m["recall"] == 1.0, metodo
        assert (df.loc[df.fuga_real, "retraso_h"] >= 0).all()


def test_alarma_exige_horas_seguidas():
    s = np.array([2.0] * (T.HORAS_SOSTENIDAS - 1) + [0.0] + [2.0] * T.HORAS_SOSTENIDAS)
    al = T._alarma(s, 1.0)
    assert not al[: T.HORAS_SOSTENIDAS].any() and al[-1]
