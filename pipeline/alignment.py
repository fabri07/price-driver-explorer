"""
Limpieza y alineación de calendarios de mercado.
================================================

Funciones de saneamiento aplicadas antes del modelado:
- alineación al calendario del activo objetivo (referencia de días de mercado),
- manejo de feriados / NaNs,
- recorte (winsorización) de outliers de retornos con criterio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize(serie: pd.Series, lower_q: float = 0.005, upper_q: float = 0.995) -> pd.Series:
    """Recorta outliers llevando los extremos a los cuantiles dados.

    No elimina filas (preserva el largo de la serie); solo acota valores extremos
    para que un día de retorno gigantesco no domine la regresión. Por defecto recorta
    el 0.5% de cada cola.
    """
    if serie.empty:
        return serie
    lo = serie.quantile(lower_q)
    hi = serie.quantile(upper_q)
    return serie.clip(lower=lo, upper=hi)


def align_features_to_target(
    target: pd.Series,
    feature_frames: dict[str, pd.Series],
    macro_frames: dict[str, pd.Series],
    max_ffill_days: int = 3,
) -> pd.DataFrame:
    """Construye una matriz alineada al calendario del target.

    Parameters
    ----------
    target : retornos log del activo objetivo (define el calendario de mercado).
    feature_frames : dict {nombre_legible -> serie de retornos de un activo de contexto}.
    macro_frames : dict {nombre_legible -> serie macro YA alineada anti look-ahead}.
    max_ffill_days : feriados/datos faltantes de activos se rellenan hasta N días.

    Returns
    -------
    DataFrame con índice = calendario del target y una columna por feature.
    El target NO se incluye (se devuelve aparte por el dataset builder).
    """
    market_calendar = target.index

    columnas: dict[str, pd.Series] = {}

    # Retornos de activos de contexto: reindexar al calendario del target.
    # Si un par no cotizó un día puntual (feriado distinto), ffill acotado evita huecos.
    for nombre, serie in feature_frames.items():
        s = serie.reindex(market_calendar)
        s = s.ffill(limit=max_ffill_days)
        columnas[nombre] = s

    # Macro ya viene alineada anti look-ahead; solo reindexamos por las dudas.
    for nombre, serie in macro_frames.items():
        columnas[nombre] = serie.reindex(market_calendar)

    X = pd.DataFrame(columnas, index=market_calendar)
    return X


def drop_sparse_columns(X: pd.DataFrame, min_valid_ratio: float = 0.6) -> pd.DataFrame:
    """Descarta columnas con demasiados NaN (datos insuficientes para modelar)."""
    keep = [c for c in X.columns if X[c].notna().mean() >= min_valid_ratio]
    return X[keep]


def finalize_dataset(X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Alinea X e y, descarta filas con NaN remanentes y devuelve el par limpio.

    Tras forward-fills acotados pueden quedar NaN al inicio (ej. macro no publicada
    todavía). Esas filas se eliminan para no inyectar imputaciones arbitrarias.
    """
    df = X.copy()
    df["__target__"] = y
    df = df.replace([np.inf, -np.inf], np.nan).dropna()

    y_clean = df.pop("__target__")
    return df, y_clean
