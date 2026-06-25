"""
Cálculo de retornos logarítmicos diarios.
==========================================

Trabajamos con retornos log (no precios nominales) porque:
- son aproximadamente aditivos en el tiempo,
- estabilizan la varianza,
- y centran el análisis en *movimientos* (que es lo que queremos explicar).

El target del modelo es el retorno log diario del activo objetivo.
Los features incluyen los retornos log de los activos de contexto.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(close: pd.Series) -> pd.Series:
    """Retornos logarítmicos diarios a partir de una serie de cierres.

    r_t = ln(P_t / P_{t-1})

    La primera observación queda NaN (no hay día previo) y se descarta.
    """
    close = close.astype(float).sort_index()
    r = np.log(close / close.shift(1))
    r = r.replace([np.inf, -np.inf], np.nan).dropna()
    return r


def returns_from_price_df(df: pd.DataFrame, price_col: str = "close") -> pd.Series:
    """Atajo: retornos log desde un DataFrame de precios (usa la columna `close`)."""
    if price_col not in df.columns:
        raise KeyError(f"No encuentro la columna '{price_col}' en el DataFrame de precios.")
    return log_returns(df[price_col])
