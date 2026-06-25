"""
Métricas de desempeño descriptivas (para el panel Overview).
============================================================

Funciones puras que calculan métricas a partir de una serie de precios de cierre.
NO usan red (reciben los precios ya descargados) y NO son recomendaciones: describen
el comportamiento histórico del activo (retornos por ventana, volatilidad, drawdown,
beta vs un benchmark, posición respecto al rango de 52 semanas).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Días de mercado aproximados por ventana.
_VENTANAS = {
    "1 mes": 21,
    "3 meses": 63,
    "6 meses": 126,
    "1 año": 252,
}
_DIAS_ANIO = 252


def _retorno_ventana(close: pd.Series, dias: int) -> float | None:
    """Retorno simple acumulado en las últimas `dias` ruedas (None si no alcanza)."""
    if len(close) <= dias:
        return None
    return float(close.iloc[-1] / close.iloc[-1 - dias] - 1.0)


def _retorno_ytd(close: pd.Series) -> float | None:
    """Retorno desde el primer cierre del año en curso (según la última fecha)."""
    if close.empty:
        return None
    ultimo = close.index[-1]
    inicio_anio = close[close.index >= pd.Timestamp(year=ultimo.year, month=1, day=1)]
    if len(inicio_anio) < 2:
        return None
    return float(close.iloc[-1] / inicio_anio.iloc[0] - 1.0)


def _volatilidad_anual(close: pd.Series) -> float | None:
    """Volatilidad anualizada (desvío de retornos log diarios * sqrt(252))."""
    r = np.log(close / close.shift(1)).dropna()
    if len(r) < 20:
        return None
    return float(r.std() * np.sqrt(_DIAS_ANIO))


def _max_drawdown(close: pd.Series) -> float | None:
    """Máxima caída desde un pico (negativo, ej. -0.35 = -35%)."""
    if close.empty:
        return None
    pico = close.cummax()
    dd = close / pico - 1.0
    return float(dd.min())


def _beta(close: pd.Series, bench: pd.Series | None) -> float | None:
    """Beta de los retornos diarios del activo vs el benchmark (cov/var)."""
    if bench is None or bench.empty:
        return None
    ra = np.log(close / close.shift(1)).dropna()
    rb = np.log(bench / bench.shift(1)).dropna()
    al = pd.concat([ra, rb], axis=1, keys=["a", "b"]).dropna()
    if len(al) < 30 or al["b"].var() == 0:
        return None
    cov = al["a"].cov(al["b"])
    return float(cov / al["b"].var())


def performance_metrics(close: pd.Series, bench_close: pd.Series | None = None) -> dict:
    """Calcula el set de métricas descriptivas de un activo.

    Parameters
    ----------
    close : serie de cierres del activo (DatetimeIndex ordenado).
    bench_close : cierres del benchmark (ej. SPY) para la beta. Opcional.

    Returns
    -------
    dict con: retornos por ventana, 'YTD', 'volatilidad_anual', 'max_drawdown',
    'beta', 'precio', 'max_52s', 'min_52s', 'dist_max_52s' (distancia % al máximo).
    Los valores son None cuando no hay datos suficientes.
    """
    close = close.astype(float).sort_index()
    out: dict[str, float | None] = {}

    for etiqueta, dias in _VENTANAS.items():
        out[f"retorno_{etiqueta}"] = _retorno_ventana(close, dias)
    out["retorno_YTD"] = _retorno_ytd(close)

    out["volatilidad_anual"] = _volatilidad_anual(close)
    out["max_drawdown"] = _max_drawdown(close)
    out["beta"] = _beta(close, bench_close)

    out["precio"] = float(close.iloc[-1]) if not close.empty else None

    # Rango de 52 semanas calculado de los precios (más robusto que el campo del proveedor).
    ult_52 = close.iloc[-_DIAS_ANIO:] if len(close) >= 2 else close
    if not ult_52.empty:
        hi, lo = float(ult_52.max()), float(ult_52.min())
        out["max_52s"] = hi
        out["min_52s"] = lo
        out["dist_max_52s"] = float(close.iloc[-1] / hi - 1.0) if hi else None
    else:
        out["max_52s"] = out["min_52s"] = out["dist_max_52s"] = None

    return out
