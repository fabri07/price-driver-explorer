"""
Atribución SHAP con signo — compartida por los modelos de árbol.
================================================================

Tanto XGBoost (boosting) como RandomForest (bagging) son modelos de árbol y usan
el mismo `shap.TreeExplainer`. Esta función centraliza el cálculo:

- "peso" = |SHAP| medio de la variable (magnitud de la importancia).
- "signo" = correlación entre el valor del feature y su contribución SHAP, que
  aproxima si —cuando la variable sube— empuja el retorno hacia arriba o abajo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def signed_shap_importance(model, X: pd.DataFrame) -> dict[str, float]:
    """Importancia |SHAP| media con signo, por variable, para un modelo de árbol ya ajustado.

    Devuelve {variable -> valor_con_signo} donde la magnitud es |SHAP| medio y el
    signo refleja la dirección dominante del efecto.
    """
    import shap

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X.values)  # (n_obs, n_features) en regresión
    # Algunos modelos/versiones devuelven lista (un array por salida); para regresión
    # de una sola salida tomamos el primero.
    if isinstance(shap_values, list):
        shap_values = shap_values[0]

    out: dict[str, float] = {}
    for j, col in enumerate(X.columns):
        sv = shap_values[:, j]
        magnitud = float(np.mean(np.abs(sv)))
        feat = X[col].values
        if np.std(feat) > 1e-12 and np.std(sv) > 1e-12:
            corr = float(np.corrcoef(feat, sv)[0, 1])
        else:
            corr = 0.0
        out[col] = magnitud if corr >= 0 else -magnitud
    return out
