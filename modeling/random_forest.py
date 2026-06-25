"""
Método 3: RandomForest + SHAP (desempate por bagging).
======================================================

Tercer método, pensado como DESEMPATE entre Lasso (lineal) y XGBoost (boosting).

RandomForest es un ensemble por *bagging*: entrena muchos árboles sobre remuestreos
y promedia. Su sesgo inductivo es distinto al del boosting (que ajusta árboles en
secuencia corrigiendo el error previo) y, por supuesto, al del modelo lineal. Por eso
su "voto" es relativamente independiente: cuando Lasso y XGBoost discrepan sobre una
variable, RandomForest aporta una tercera lectura desde otra familia de modelos.

Como es un modelo de árbol, la atribución se hace con el MISMO SHAP que XGBoost
(`modeling.shap_attrib.signed_shap_importance`):
- "peso" = |SHAP| medio de la variable.
- "signo" = dirección dominante del efecto (correlación feature ↔ valor SHAP).
"""

from __future__ import annotations

import pandas as pd

from modeling.results import ValidationReport, VariableWeight
from modeling.shap_attrib import signed_shap_importance
from modeling.stability import weight_stability
from modeling.validation import walk_forward_rmse


def make_rf() -> "RandomForestRegressor":  # noqa: F821 (tipo perezoso)
    """RandomForest con hiperparámetros conservadores para retornos diarios ruidosos.

    - `max_features='sqrt'` decorrelaciona los árboles (clave del bagging).
    - `min_samples_leaf=5` y `max_depth=6` frenan el sobreajuste al ruido diario.
    - `n_jobs=1`: el bootstrap de estabilidad ya corre muchos fits en serie.
    """
    from sklearn.ensemble import RandomForestRegressor

    return RandomForestRegressor(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=5,
        max_features="sqrt",
        random_state=0,
        n_jobs=1,
    )


def fit_rf_shap(X: pd.DataFrame, y: pd.Series) -> tuple[list[VariableWeight], ValidationReport]:
    """Ajusta RandomForest, calcula atribución SHAP, estabilidad y validación OOS."""
    columns = list(X.columns)

    # --- Ajuste completo + SHAP ------------------------------------------
    model = make_rf()
    model.fit(X.values, y.values)
    signed = signed_shap_importance(model, X)

    # --- Estabilidad por bootstrap (sobre la importancia SHAP) -----------
    def coef_fn(X_sub: pd.DataFrame, y_sub: pd.Series) -> dict[str, float]:
        m = make_rf()
        m.fit(X_sub.values, y_sub.values)
        return signed_shap_importance(m, X_sub)

    estab = weight_stability(coef_fn, X, y, n_resamples=15)  # RF+SHAP es caro: menos resamples

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
                metodo="random_forest",
            )
        )

    # --- Validación OOS ---------------------------------------------------
    val = walk_forward_rmse(make_rf, X, y)
    reporte = ValidationReport(
        modelo="random_forest",
        metrica=val["metrica"],
        error_modelo=val["error_modelo"],
        error_baseline_cero=val["error_baseline_cero"],
        error_baseline_rezago=val["error_baseline_rezago"],
        aporta_sobre_baseline=val["aporta_sobre_baseline"],
        n_splits=val["n_splits"],
        nota="Bagging (RandomForest); importancia = |SHAP| medio, signo = dirección dominante.",
    )

    return pesos, reporte
