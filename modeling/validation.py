"""
Validación walk-forward (out-of-sample) contra baselines naive.
===============================================================

NUNCA reportamos error in-sample (sería autoengaño). Usamos validación walk-forward:
entrenamos con el pasado y evaluamos en el futuro inmediato, repetidamente.

Comparamos contra dos baselines naive honestos:
- predecir SIEMPRE retorno cero (la media de los retornos diarios ≈ 0),
- predecir el retorno del día anterior (persistencia / rezago).

Si el modelo no le gana al baseline, lo decimos claramente: significa que las
asociaciones encontradas tienen poco poder predictivo fuera de muestra.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import TimeSeriesSplit


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def walk_forward_rmse(
    model_factory,
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 5,
) -> dict:
    """Evalúa un modelo con TimeSeriesSplit y lo compara con baselines.

    Parameters
    ----------
    model_factory : callable sin args que devuelve un estimador sklearn-like NUEVO
        (sin entrenar). Se reentrena en cada fold para no filtrar información.
    X, y : dataset alineado.
    n_splits : cantidad de cortes walk-forward.

    Returns
    -------
    dict con RMSE del modelo y de cada baseline, y si aporta sobre el mejor baseline.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)

    err_modelo: list[float] = []
    err_cero: list[float] = []
    err_rezago: list[float] = []

    X_np = X.values
    y_np = y.values

    for train_idx, test_idx in tscv.split(X_np):
        X_tr, X_te = X_np[train_idx], X_np[test_idx]
        y_tr, y_te = y_np[train_idx], y_np[test_idx]

        # Modelo (reentrenado por fold).
        model = model_factory()
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        err_modelo.append(_rmse(y_te, pred))

        # Baseline 1: predecir cero.
        err_cero.append(_rmse(y_te, np.zeros_like(y_te)))

        # Baseline 2: predecir el retorno previo (persistencia).
        # Para el primer punto del test usamos el último del train.
        prev = np.concatenate([[y_tr[-1]], y_te[:-1]])
        err_rezago.append(_rmse(y_te, prev))

    rmse_modelo = float(np.mean(err_modelo))
    rmse_cero = float(np.mean(err_cero))
    rmse_rezago = float(np.mean(err_rezago))
    mejor_baseline = min(rmse_cero, rmse_rezago)

    return {
        "metrica": "RMSE",
        "error_modelo": rmse_modelo,
        "error_baseline_cero": rmse_cero,
        "error_baseline_rezago": rmse_rezago,
        "aporta_sobre_baseline": rmse_modelo < mejor_baseline,
        "n_splits": n_splits,
    }
