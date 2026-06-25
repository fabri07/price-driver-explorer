"""
Método 1: Regresión Lasso (L1) sobre features estandarizados.
=============================================================

El Lasso da coeficientes interpretables con signo y magnitud (los "pesos"), y al
penalizar L1 lleva a cero las variables irrelevantes — selección automática. Como
estandarizamos los features (media 0, desvío 1), los coeficientes son comparables
entre sí en magnitud.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LassoCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from modeling.results import ValidationReport, VariableWeight
from modeling.stability import weight_stability
from modeling.validation import walk_forward_rmse


def make_lasso_pipeline() -> Pipeline:
    """Pipeline estándar: estandarizar + LassoCV (alpha por validación cruzada)."""
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            # LassoCV elige alpha por CV interna; cv temporal-agnóstico acá porque
            # la validación OOS honesta se hace aparte en validation.py.
            ("lasso", LassoCV(cv=5, max_iter=10000, n_jobs=None, random_state=0)),
        ]
    )


def _coefs_from_pipeline(pipe: Pipeline, columns: list[str]) -> dict[str, float]:
    """Extrae el dict {variable -> coeficiente} de un pipeline Lasso ya ajustado."""
    lasso = pipe.named_steps["lasso"]
    return {col: float(c) for col, c in zip(columns, lasso.coef_)}


def fit_lasso(X: pd.DataFrame, y: pd.Series) -> tuple[list[VariableWeight], ValidationReport]:
    """Ajusta Lasso, mide estabilidad y valida OOS.

    Returns
    -------
    (pesos, reporte_validacion)
    """
    columns = list(X.columns)

    # --- Ajuste completo (para los pesos reportados) ---------------------
    pipe = make_lasso_pipeline()
    pipe.fit(X.values, y.values)
    coefs = _coefs_from_pipeline(pipe, columns)

    # --- Estabilidad por bootstrap ---------------------------------------
    def coef_fn(X_sub: pd.DataFrame, y_sub: pd.Series) -> dict[str, float]:
        p = make_lasso_pipeline()
        p.fit(X_sub.values, y_sub.values)
        return _coefs_from_pipeline(p, list(X_sub.columns))

    estab = weight_stability(coef_fn, X, y)

    # --- Construir VariableWeight (solo coeficientes no nulos) -----------
    pesos: list[VariableWeight] = []
    for col in columns:
        coef = coefs.get(col, 0.0)
        if abs(coef) < 1e-8:
            continue  # Lasso lo descartó: irrelevante
        pesos.append(
            VariableWeight(
                variable=col,
                peso=abs(coef),
                signo="+" if coef >= 0 else "-",
                estabilidad=estab.get(col, {}).get("estabilidad", 0.0),
                metodo="lasso",
            )
        )

    # --- Validación OOS ---------------------------------------------------
    val = walk_forward_rmse(make_lasso_pipeline, X, y)
    reporte = ValidationReport(
        modelo="lasso",
        metrica=val["metrica"],
        error_modelo=val["error_modelo"],
        error_baseline_cero=val["error_baseline_cero"],
        error_baseline_rezago=val["error_baseline_rezago"],
        aporta_sobre_baseline=val["aporta_sobre_baseline"],
        n_splits=val["n_splits"],
        nota=(
            "Coeficientes sobre features estandarizados; el Lasso descarta lo "
            "irrelevante llevándolo a cero."
        ),
    )

    return pesos, reporte
