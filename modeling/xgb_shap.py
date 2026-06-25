"""
Método 2: XGBoost + SHAP para atribución no lineal.
===================================================

El Lasso captura relaciones lineales. XGBoost captura no-linealidades e interacciones;
SHAP descompone la predicción en contribuciones por variable, comparables entre sí.

- "peso" = |SHAP| medio de la variable (importancia direccionalmente agnóstica).
- "signo" = signo de la correlación entre el valor SHAP de la variable y su valor
  (aproxima si, cuando la variable sube, empuja el retorno hacia arriba o abajo).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from modeling.results import ValidationReport, VariableWeight
from modeling.stability import weight_stability
from modeling.validation import walk_forward_rmse

# Nota: xgboost y shap se importan de forma PEREZOSA dentro de las funciones, para
# que importar este módulo (y modeling.engine) no falle si no están instalados.
# Así el camino solo-Lasso funciona aunque falte xgboost. (from __future__ import
# annotations hace que las anotaciones de tipo no se evalúen en runtime.)


def make_xgb() -> "XGBRegressor":  # noqa: F821 (tipo perezoso)
    """XGBoost con hiperparámetros conservadores (regularizado, esqueleto no tuneado)."""
    try:
        from xgboost import XGBRegressor
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "xgboost no está instalado. Ejecutá: pip install -r requirements.txt"
        ) from exc

    return XGBRegressor(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=0,
        n_jobs=1,  # 1 hilo por modelo: el bootstrap ya corre muchos fits
        verbosity=0,
    )


def _shap_signed_importance(model: XGBRegressor, X: pd.DataFrame) -> dict[str, float]:
    """Importancia |SHAP| media con signo, por variable.

    Devuelve {variable -> valor_con_signo} donde la magnitud es |SHAP| medio y el
    signo refleja la dirección dominante del efecto.
    """
    import shap

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X.values)  # (n_obs, n_features)

    out: dict[str, float] = {}
    for j, col in enumerate(X.columns):
        sv = shap_values[:, j]
        magnitud = float(np.mean(np.abs(sv)))
        # Signo: correlación entre el valor del feature y su contribución SHAP.
        feat = X[col].values
        if np.std(feat) > 1e-12 and np.std(sv) > 1e-12:
            corr = float(np.corrcoef(feat, sv)[0, 1])
        else:
            corr = 0.0
        out[col] = magnitud if corr >= 0 else -magnitud
    return out


def fit_xgb_shap(X: pd.DataFrame, y: pd.Series) -> tuple[list[VariableWeight], ValidationReport]:
    """Ajusta XGBoost, calcula atribución SHAP, estabilidad y validación OOS."""
    columns = list(X.columns)

    # --- Ajuste completo + SHAP ------------------------------------------
    model = make_xgb()
    model.fit(X.values, y.values)
    signed = _shap_signed_importance(model, X)

    # --- Estabilidad por bootstrap (sobre la importancia SHAP) -----------
    def coef_fn(X_sub: pd.DataFrame, y_sub: pd.Series) -> dict[str, float]:
        m = make_xgb()
        m.fit(X_sub.values, y_sub.values)
        return _shap_signed_importance(m, X_sub)

    estab = weight_stability(coef_fn, X, y, n_resamples=15)  # menos resamples: XGB es caro

    # --- VariableWeight ---------------------------------------------------
    pesos: list[VariableWeight] = []
    for col in columns:
        val = signed.get(col, 0.0)
        if abs(val) < 1e-8:
            continue
        pesos.append(
            VariableWeight(
                variable=col,
                peso=abs(val),
                signo="+" if val >= 0 else "-",
                estabilidad=estab.get(col, {}).get("estabilidad", 0.0),
                metodo="xgboost_shap",
            )
        )

    # --- Validación OOS ---------------------------------------------------
    val = walk_forward_rmse(make_xgb, X, y)
    reporte = ValidationReport(
        modelo="xgboost_shap",
        metrica=val["metrica"],
        error_modelo=val["error_modelo"],
        error_baseline_cero=val["error_baseline_cero"],
        error_baseline_rezago=val["error_baseline_rezago"],
        aporta_sobre_baseline=val["aporta_sobre_baseline"],
        n_splits=val["n_splits"],
        nota="Importancia = |SHAP| medio; el signo aproxima la dirección del efecto.",
    )

    return pesos, reporte
